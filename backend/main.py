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

app = FastAPI()

logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def ocr_pdf(pdf_bytes: bytes):
    """Perform OCR on a non-searchable PDF, returning normalized coordinates [0..1]."""
    ocr_results = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                img_page = page.to_image(resolution=200)
                img = img_page.original
                img_width, img_height = img.size

                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

                for i in range(len(data["text"])):
                    text = data["text"][i].strip()
                    if text:
                        left = data["left"][i]
                        top = data["top"][i]
                        width = data["width"][i]
                        height = data["height"][i]

                        # Normalize
                        x0 = left / img_width
                        y0 = top / img_height
                        x1 = (left + width) / img_width
                        y1 = (top + height) / img_height

                        ocr_results.append({
                            "text": text,
                            "bbox": [x0, y0, x1, y1],
                            "page_num": page.page_number
                        })
    except Exception as e:
        logging.error(f"OCR Error: {str(e)}")
    return ocr_results

@app.post("/extract")
async def extract_text(request: ExtractRequest):
    try:
        logging.info(f"Received request for URL: {request.pdf_url}")

        response = requests.get(str(request.pdf_url), timeout=30)
        response.raise_for_status()
        pdf_bytes = response.content

        # Attempt searchable text extraction
        result = process_searchable_pdf(pdf_bytes)

        if not result:
            # Fallback to OCR
            result = ocr_pdf(pdf_bytes)

        return {"extracted_data": result}

    except Exception as e:
        logging.error(f"Processing Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
