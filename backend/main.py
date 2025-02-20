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

# Set spawn method for multiprocessing in Docker
if os.environ.get('DOCKER_CONTAINER') == 'true':
    multiprocessing.set_start_method('spawn', force=True)
else:
    multiprocessing.set_start_method('fork', force=True)

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

def process_page_worker(args):
    """Worker function that processes a single page"""
    try:
        pdf_bytes, page_num = args
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page = pdf.pages[page_num]
            words = page.extract_words()
            results = []
            
            for word in words:
                x0 = word["x0"] / page.width
                y0 = word["top"] / page.height
                x1 = word["x1"] / page.width
                y1 = word["bottom"] / page.height
                
                results.append({
                    "text": word["text"],
                    "bbox": [x0, y0, x1, y1],
                    "page_num": page_num + 1
                })
            
            return results
    except Exception as e:
        logging.error(f"Error processing page {page_num}: {str(e)}")
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
        logging.info("Starting PDF processing")
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)
            logging.info(f"PDF has {total_pages} pages")
            
            if total_pages > MAX_PAGES:
                raise HTTPException(
                    status_code=400,
                    detail=f"PDF has too many pages ({total_pages}). Maximum allowed is {MAX_PAGES}"
                )
            
            yield (json.dumps({
                "type": "progress",
                "total_pages": total_pages,
                "processed_pages": 0
            }) + "\n").encode("utf-8")

            # Create list of tasks with PDF bytes for each page
            tasks = [(pdf_bytes, page_num) for page_num in range(total_pages)]
            
            # Process in chunks
            for chunk_start in range(0, len(tasks), CHUNK_SIZE):
                if time.time() - start_time > PROCESSING_TIMEOUT:
                    logging.warning("Processing timeout reached")
                    break

                chunk_end = min(chunk_start + CHUNK_SIZE, len(tasks))
                chunk = tasks[chunk_start:chunk_end]
                
                try:
                    # Process chunk using ProcessPoolExecutor
                    with ProcessPoolExecutor(max_workers=2) as executor:
                        results = list(executor.map(process_page_worker, chunk))
                        
                        # Handle results
                        for page_results in results:
                            if page_results:  # Only process if we got results
                                current_batch.extend(page_results)
                                if len(current_batch) >= BATCH_SIZE:
                                    logging.info(f"Sending batch of {len(current_batch)} items")
                                    yield (json.dumps({
                                        "type": "data",
                                        "extracted_data": current_batch,
                                        "is_complete": False
                                    }) + "\n").encode("utf-8")
                                    text_with_bboxes.extend(current_batch)
                                    current_batch = []
                
                except Exception as e:
                    logging.error(f"Error processing chunk: {str(e)}")
                    continue

            # Send remaining batch
            if current_batch:
                logging.info(f"Sending final batch of {len(current_batch)} items")
                yield (json.dumps({
                    "type": "data",
                    "extracted_data": current_batch,
                    "is_complete": False
                }) + "\n").encode("utf-8")
                text_with_bboxes.extend(current_batch)

            logging.info("Processing completed successfully")
            yield (json.dumps({
                "type": "data",
                "extracted_data": [],
                "is_complete": True
            }) + "\n").encode("utf-8")

    except Exception as e:
        logging.error(f"Processing error: {str(e)}", exc_info=True)
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
