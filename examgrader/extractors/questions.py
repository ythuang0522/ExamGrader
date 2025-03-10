"""Module for extracting questions from PDF files."""

import logging
from examgrader.extractors.base import BasePDFExtractor
from examgrader.utils.prompts import PromptManager

logger = logging.getLogger(__name__)

class QuestionExtractor(BasePDFExtractor):
    """Extracts questions from PDF files"""
    
    def extract(self) -> str:
        """Extract questions from PDF pages.
        
        Returns:
            Concatenated string of all extracted questions
        """
        images = self.pdf_to_images()
        all_text = ""
        
        for page_num, image in enumerate(images, 1):
            logger.info(f"Processing page {page_num}/{len(images)} for questions")
            text = self.gemini_api.generate_content(
                PromptManager.get_question_extraction_prompt(), 
                image
            )
            if text:
                all_text += text + "\n"
                
        return all_text
