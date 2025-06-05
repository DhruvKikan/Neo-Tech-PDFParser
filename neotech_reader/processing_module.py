import cv2
import numpy as np
import pytesseract
import fitz  # PyMuPDF
import os
import tempfile
import logging
import json
import requests
from typing import Tuple, Optional

# Configure logging
logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

# Hugging Face API configuration
HF_API_TOKEN = "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"  # Replace with your Hugging Face token
# You can get a free token from https://huggingface.co/settings/tokens
HF_API_URL = "https://router.huggingface.co/novita/v3/openai/chat/completions"  # New chat completions API
HF_MODEL = "deepseek/deepseek-v3-0324"  # Model to use for chat completions

def process_document(file_path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Unified function to process both images and PDFs
    Returns: (error, text)
    """
    temp_files = []
    try:
        # Validate file exists
        if not os.path.exists(file_path):
            return "File not found", None

        # Validate file size (max 10MB)
        if os.path.getsize(file_path) > 10 * 1024 * 1024:
            return "File too large (max 10MB)", None

        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.pdf':
            # Process PDF
            doc = fitz.open(file_path)
            text = ""
            for page_num in range(len(doc)):
                try:
                    page = doc[page_num]
                    pix = page.get_pixmap(matrix = fitz.Matrix(2.0, 2.0))
                    img_data = bytes(pix.samples)
                    np_arr = np.frombuffer(img_data, dtype = np.uint8).reshape(pix.height, pix.width, 3)
                    page_text = process_image_array(np_arr)
                    if page_text:
                        text += page_text + "\n"
                except Exception as e:
                    logger.error(f"Error processing PDF page {page_num}: {str(e)}")
                    continue
            doc.close()
            return None, text.strip() if text else None
        else:
            # Process image
            img = cv2.imread(file_path)
            if img is None:
                return "Failed to load image", None
            text = process_image_array(img)
            return None, text.strip() if text else None
            
    except Exception as e:
        logger.error(f"Error processing document {file_path}: {str(e)}")
        return f"Error processing document: {str(e)}", None
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {temp_file}: {str(e)}")

def process_image_array(img: np.ndarray) -> Optional[str]:
    """Helper function to process image array for OCR"""
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        # Perform OCR
        text = pytesseract.image_to_string(gray)
        
        if not text.strip():
            logger.warning("No text was extracted from the image")
            return None
            
        return text
        
    except Exception as e:
        logger.error(f"Error in OCR processing: {str(e)}")
        return None

def extract_structured_data(raw_text: str) -> dict:
    """
    Use Hugging Face API to extract structured data from raw text.
    Returns a dictionary with the extracted information.
    """
    # Create a system prompt and user prompt for CV data extraction
    system_message = """You are an expert CV analyzer and parser. Your task is to extract structured precise information from CVs or resumes.
Extract the following information and format it as valid JSON:
{
    "first_name": "first name of the candidate",
    "middle_name": "middle name of the candidate (if any)",
    "last_name": "last name of the candidate",
    "contact_numbers": ["list of all phone numbers mentioned"],
    "email_ids": ["list of all valid email addresses mentioned"],
    "education": {
        "class_12": "class 12 education details",
        "college": "undergraduate education details",
        "higher_studies": "postgraduate or higher education details (if any)"
    },
    "work_experience": "detailed work experience",
    "skillset": ["list of non-programming and soft skills"],
    "toolset": ["list of technical concepts and tools known"],
    "programming_languages": ["list of programming languages used/known"],
    "projects": [
        {
            "name": "name of project",
            "description": "brief description",
            "tech_stack": ["languages/technologies used"]
        }
    ],
    "certifications": ["list of certificates earned"],
    "relevant_links": {
        "linkedin": "LinkedIn profile URL",
        "github": "GitHub profile URL",
        "portfolio": "portfolio website URL",
        "other": ["list of any other relevant links"]
    }
}
Ensure the output is ONLY valid JSON with NO additional text. Validate all email addresses before including them in the output."""
    
    user_message = f"Extract structured information from this CV:\n\n{raw_text}"
    
    try:
        headers = {
            "Authorization": f"Bearer {HF_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            "model": HF_MODEL,
            "temperature": 0.1,  # Low temperature for more deterministic responses
            "max_tokens": 1000  # Limit response length
        }
        
        logger.info("Sending request to Hugging Face API...")
        response = requests.post(HF_API_URL, headers=headers, json=payload)
        
        if response.status_code != 200:
            logger.error(f"API request failed with status code {response.status_code}")
            logger.error(f"Response content: {response.text}")
            raise Exception(f"API request failed with status code {response.status_code}")
        
        result = response.json()
        logger.info("Received response from API")
        
        # Extract the generated text from the response (chat completion format)
        if "choices" in result and len(result["choices"]) > 0 and "message" in result["choices"][0]:
            generated_text = result["choices"][0]["message"]["content"]
        else:
            logger.error(f"Unexpected API response format: {result}")
            raise Exception("Unexpected API response format")
        
        # Try to find and parse JSON in the generated text
        import re
        json_match = re.search(r'(\{.*\})', generated_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            extracted_data = json.loads(json_str)
        else:
            # If no JSON found, try to parse the entire response
            extracted_data = json.loads(generated_text)
        
        # Ensure all required fields exist with proper types
        default_data = {
            'first_name': '',
            'middle_name': '',
            'last_name': '',
            'contact_numbers': [],
            'email_ids': [],
            'education': {
                'class_12': '',
                'college': '',
                'higher_studies': ''
            },
            'work_experience': '',
            'skillset': [],
            'toolset': [],
            'programming_languages': [],
            'projects': [],
            'certifications': [],
            'relevant_links': {
                'linkedin': '',
                'github': '',
                'portfolio': '',
                'other': []
            }
        }
        
        # Update default_data with extracted values, ensuring proper types
        for key in default_data:
            if key in extracted_data:
                if isinstance(default_data[key], dict):
                    # Ensure dict fields are actually dicts
                    default_data[key] = extracted_data[key] if isinstance(extracted_data[key], dict) else {}
                elif isinstance(default_data[key], list):
                    # Ensure list fields are actually lists
                    default_data[key] = extracted_data[key] if isinstance(extracted_data[key], list) else [extracted_data[key]]
                else:
                    # Ensure string fields are actually strings
                    default_data[key] = str(extracted_data[key]) if extracted_data[key] is not None else ''
        
        logger.info("Successfully extracted and formatted data")
        return default_data
            
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        logger.error(f"Request details: URL={HF_API_URL}, Headers={headers}")
        raise Exception(f"Failed to connect to API: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse API response: {str(e)}")
        logger.error(f"Response content: {response.text if 'response' in locals() else 'No response'}")
        raise Exception(f"Failed to parse API response: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in extract_structured_data: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        raise Exception(f"Failed to extract data: {str(e)}")