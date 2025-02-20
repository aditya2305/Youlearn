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
from concurrent.futures import ProcessPoolExecutor
import asyncio
from functools import partial
import time
import httpx
from fastapi.responses import StreamingResponse
import multiprocessing
import json
import os

# Only set fork method if we're not in a container
if os.environ.get('DOCKER_CONTAINER') != 'true':
    multiprocessing.set_start_method("fork", force=True)

app = FastAPI()

logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Adjust processing parameters for speed
PROCESSING_TIMEOUT = 75  # Maximum 75 seconds
MAX_WORKERS = min(int(os.getenv('WORKERS', '2')), 4)  # Limit max workers
CHUNK_SIZE = 5  # Reduce chunk size for better stability
BATCH_SIZE = 25  # Smaller batch size for more frequent updates
MAX_PAGES = 2000

class ProcessingStatus:
    def __init__(self):
        self.start_time = time.time()
        self.processed_pages = 0
        self.total_pages = 0

class ExtractRequest(BaseModel):
    pdf_url: HttpUrl

# Global variable in the worker to hold the opened PDF
global_pdf = None

def init_worker(pdf_bytes):
    """
    Initializer for each worker process: open the PDF and monkey-patch the
    cached method to allow pickling.
    """
    # Remove the lru_cache wrapper from the _get_text_layout method.
    # This avoids the pickle error when using the multiprocessing spawn method.
    from pdfplumber.page import Page
    if hasattr(Page._get_text_layout, "__wrapped__"):
        Page._get_text_layout = Page._get_text_layout.__wrapped__
    global global_pdf
    global_pdf = pdfplumber.open(io.BytesIO(pdf_bytes))

def process_page_worker(page_index, process_type):
    """Worker function: get page by index from the global PDF and process it."""
    global global_pdf
    try:
        page = global_pdf.pages[page_index]
        return process_page(page, process_type)
    except Exception as e:
        logging.error(f"Error processing page {page_index}: {str(e)}")
        return []

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
    """Process a single page with timeout control.
    This function will be called in a separate process.
    """
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
        else:  # OCR path
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
    start_time = time.time()
    text_with_bboxes = []
    current_batch = []
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf_temp:
            total_pages = len(pdf_temp.pages)
            if total_pages > MAX_PAGES:
                raise HTTPException(
                    status_code=400,
                    detail=f"PDF has too many pages ({total_pages}). Maximum allowed is {MAX_PAGES}"
                )
            
            # Send initial progress
            yield (json.dumps({
                "type": "progress",
                "total_pages": total_pages,
                "processed_pages": 0
            }) + "\n").encode("utf-8")

            # Use a smaller number of workers
            with ProcessPoolExecutor(max_workers=MAX_WORKERS, initializer=init_worker, initargs=(pdf_bytes,)) as executor:
                loop = asyncio.get_event_loop()
                tasks = []
                
                # Process in smaller chunks
                for chunk_start in range(0, total_pages, CHUNK_SIZE):
                    if time.time() - start_time > PROCESSING_TIMEOUT:
                        break

                    chunk_end = min(chunk_start + CHUNK_SIZE, total_pages)
                    chunk_tasks = [
                        loop.run_in_executor(executor, process_page_worker, page_index, "searchable")
                        for page_index in range(chunk_start, chunk_end)
                    ]
                    
                    # Process each chunk immediately
                    chunk_results = await asyncio.gather(*chunk_tasks)
                    for result in chunk_results:
                        current_batch.extend(result)
                        if len(current_batch) >= BATCH_SIZE:
                            yield (json.dumps({
                                "type": "data",
                                "extracted_data": current_batch,
                                "is_complete": False
                            }) + "\n").encode("utf-8")
                            text_with_bboxes.extend(current_batch)
                            current_batch = []

                # Send final batch
                if current_batch:
                    yield (json.dumps({
                        "type": "data",
                        "extracted_data": current_batch,
                        "is_complete": False
                    }) + "\n").encode("utf-8")
                    text_with_bboxes.extend(current_batch)

                # Final completion message
                yield (json.dumps({
                    "type": "data",
                    "extracted_data": [],
                    "is_complete": True
                }) + "\n").encode("utf-8")

    except TimeoutError:
        yield (json.dumps({
            "type": "data",
            "extracted_data": text_with_bboxes,
            "is_complete": True
        }) + "\n").encode("utf-8")
    except Exception as e:
        logging.error(f"PDF processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract")
async def extract_text(request: ExtractRequest):
    try:
        logging.info(f"Received request for URL: {request.pdf_url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                str(request.pdf_url), 
                timeout=60.0  # Increase timeout for large files
            )
            response.raise_for_status()
            pdf_bytes = response.content

        # Stream partial results back as they become available
        return StreamingResponse(
            process_pdf_with_timeout(pdf_bytes),
            media_type="application/json"
        )

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
