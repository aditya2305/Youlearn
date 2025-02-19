# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import requests
import pdfplumber
import pytesseract
from PIL import Image
import io
import logging
from PIL import ImageEnhance
from concurrent.futures import ThreadPoolExecutor
import asyncio
from functools import partial
import time
import httpx

app = FastAPI()

logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add timeout and processing status tracking
PROCESSING_TIMEOUT = 75  # 75 seconds max processing time
MAX_WORKERS = 4  # Limit concurrent processing
CHUNK_SIZE = 50  # Process 50 pages at a time
MAX_PAGES = 1500  # Maximum pages allowed

class ProcessingStatus:
    def __init__(self):
        self.start_time = time.time()
        self.processed_pages = 0
        self.total_pages = 0

class ExtractRequest(BaseModel):
    pdf_url: HttpUrl

def process_searchable_pdf(pdf_bytes: bytes):
    """Extract searchable text from a PDF and return normalized coordinates [0..1]."""
    text_with_bboxes = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_width = page.width
            page_height = page.height

            words = page.extract_words()
            for w in words:
                # Convert bounding box to normalized values
                x0 = w["x0"] / page_width
                y0 = w["top"] / page_height
                x1 = w["x1"] / page_width
                y1 = w["bottom"] / page_height

                text_with_bboxes.append({
                    "text": w["text"],
                    "bbox": [x0, y0, x1, y1],
                    "page_num": page.page_number  # pdfplumber page_number is 1-based
                })
    return text_with_bboxes

def process_image_for_ocr(img):
    """Preprocess image for better OCR results"""
    # Convert to grayscale if not already
    if img.mode != 'L':
        img = img.convert('L')
    # Increase contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2)
    return img

def ocr_pdf(pdf_bytes: bytes):
    """Perform OCR on a non-searchable PDF, returning normalized coordinates [0..1]."""
    ocr_results = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                # Increased resolution for better accuracy
                img_page = page.to_image(resolution=300)
                img = img_page.original
                img = process_image_for_ocr(img)
                img_width, img_height = img.size

                # Add language hints and improve config
                custom_config = r'--oem 3 --psm 6 -l eng+fra+deu'
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=custom_config)

                for i in range(len(data["text"])):
                    text = data["text"][i].strip()
                    if text:
                        left = data["left"][i]
                        top = data["top"][i]
                        width = data["width"][i]
                        height = data["height"][i]

                        x0 = left / img_width
                        y0 = top / img_height
                        x1 = (left + width) / img_width
                        y1 = (top + height) / img_height

                        ocr_results.append({
                            "text": text,
                            "bbox": [x0, y0, x1, y1],
                            "page_num": page.page_number,
                            "confidence": data["conf"][i]  # Add confidence score
                        })
    except Exception as e:
        logging.error(f"OCR Error: {str(e)}")
    return ocr_results

def process_page(page, process_type="searchable"):
    """Process a single page with timeout control"""
    try:
        if process_type == "searchable":
            page_width = page.width
            page_height = page.height
            words = page.extract_words()
            return [{
                "text": w["text"],
                "bbox": [
                    w["x0"] / page_width,
                    w["top"] / page_height,
                    w["x1"] / page_width,
                    w["bottom"] / page_height
                ],
                "page_num": page.page_number
            } for w in words]
        else:  # OCR
            img_page = page.to_image(resolution=300)
            img = process_image_for_ocr(img_page.original)
            return perform_ocr_on_image(img, page.page_number)
    except Exception as e:
        logging.error(f"Page processing error: {str(e)}")
        return []

def perform_ocr_on_image(img, page_number):
    """Perform OCR on a single image"""
    try:
        img_width, img_height = img.size
        custom_config = r'--oem 3 --psm 6 -l eng+fra+deu'
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=custom_config)
        
        results = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if text:
                left = data["left"][i]
                top = data["top"][i]
                width = data["width"][i]
                height = data["height"][i]

                x0 = left / img_width
                y0 = top / img_height
                x1 = (left + width) / img_width
                y1 = (top + height) / img_height

                results.append({
                    "text": text,
                    "bbox": [x0, y0, x1, y1],
                    "page_num": page_number,
                    "confidence": data["conf"][i]
                })
        return results
    except Exception as e:
        logging.error(f"OCR Error on image: {str(e)}")
        return []

async def process_pdf_with_timeout(pdf_bytes: bytes):
    """Process PDF with timeout and parallel processing"""
    start_time = time.time()
    text_with_bboxes = []
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)
            
            if total_pages > MAX_PAGES:
                raise HTTPException(
                    status_code=400,
                    detail=f"PDF has too many pages ({total_pages}). Maximum allowed is {MAX_PAGES}"
                )

            # Process pages in chunks
            for chunk_start in range(0, total_pages, CHUNK_SIZE):
                if time.time() - start_time > PROCESSING_TIMEOUT:
                    raise TimeoutError("Processing timeout exceeded")
                
                chunk_end = min(chunk_start + CHUNK_SIZE, total_pages)
                chunk_pages = pdf.pages[chunk_start:chunk_end]
                
                # Process chunk with parallel execution
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    loop = asyncio.get_event_loop()
                    tasks = []
                    
                    for page in chunk_pages:
                        task = loop.run_in_executor(
                            executor,
                            partial(process_page, page, "searchable")
                        )
                        tasks.append(task)
                    
                    chunk_results = await asyncio.gather(*tasks)
                    chunk_text = [item for sublist in chunk_results for item in sublist]
                    
                    if chunk_text:  # If searchable text found
                        text_with_bboxes.extend(chunk_text)
                    else:  # Try OCR for this chunk
                        ocr_tasks = []
                        for page in chunk_pages:
                            task = loop.run_in_executor(
                                executor,
                                partial(process_page, page, "ocr")
                            )
                            ocr_tasks.append(task)
                        
                        ocr_results = await asyncio.gather(*ocr_tasks)
                        text_with_bboxes.extend([
                            item for sublist in ocr_results for item in sublist
                        ])

    except TimeoutError:
        logging.error("PDF processing timeout")
        raise HTTPException(status_code=408, detail="Processing timeout exceeded")
    except Exception as e:
        logging.error(f"PDF processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    return text_with_bboxes

@app.post("/extract")
async def extract_text(request: ExtractRequest):
    try:
        logging.info(f"Received request for URL: {request.pdf_url}")
        
        # Download PDF with timeout
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    str(request.pdf_url),
                    timeout=30.0
                )
                response.raise_for_status()
                pdf_bytes = response.content
            except Exception as e:
                logging.error(f"PDF download error: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to download PDF: {str(e)}"
                )

        # Process PDF with timeout
        try:
            result = await process_pdf_with_timeout(pdf_bytes)
        except Exception as e:
            logging.error(f"PDF processing error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process PDF: {str(e)}"
            )
        
        if not result:
            raise HTTPException(
                status_code=422,
                detail="No text could be extracted from the PDF"
            )

        return {"extracted_data": result}

    except TimeoutError:
        raise HTTPException(status_code=408, detail="Processing timeout exceeded")
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
