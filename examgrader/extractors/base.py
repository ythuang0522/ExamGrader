"""Base class for PDF extraction functionality."""

import os
import logging
import fitz  # PyMuPDF
from PIL import Image
import io
from typing import List

from examgrader.api.gemini import GeminiAPI

logger = logging.getLogger(__name__)

class BasePDFExtractor:
    """Base class for PDF extraction functionality"""
    
    def __init__(self, pdf_path: str, gemini_api: GeminiAPI):
        """Initialize the PDF extractor.
        
        Args:
            pdf_path: Path to the PDF file
            gemini_api: Initialized GeminiAPI instance
        """
        self.pdf_path = pdf_path
        self.gemini_api = gemini_api
        
        # Create debug directory relative to the PDF file
        pdf_dir = os.path.dirname(os.path.abspath(pdf_path))
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        self.debug_dir = os.path.join(pdf_dir, "debug_images", pdf_name)
        os.makedirs(self.debug_dir, exist_ok=True)
    
    def pdf_to_images(self, dpi: int = 300) -> List[Image.Image]:
        """Convert PDF pages to PIL Images.
        
        Args:
            dpi: Resolution for page rendering
            
        Returns:
            List of PIL Image objects
        """
        images = []
        pdf_document = None
        
        try:
            pdf_document = fitz.open(self.pdf_path)
            zoom = dpi / 72
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                matrix = fitz.Matrix(zoom, zoom).prerotate(page.rotation or 0)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                img_data = pix.tobytes("jpeg")
                image = Image.open(io.BytesIO(img_data)).convert('RGB')
                
                # Save debug image
                debug_path = os.path.join(
                    self.debug_dir,
                    f"page_{page_num + 1}.jpg"
                )
                image.save(debug_path, "JPEG")
                logger.debug(f"Saved debug image to {debug_path}")
                
                images.append(image)
                    
        except Exception as e:
            logger.error(f"Error converting PDF {self.pdf_path} to images: {e}")
            return []
        finally:
            if pdf_document:
                pdf_document.close()
        return images
