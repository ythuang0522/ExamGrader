"""Module for extracting answers from PDF files."""

import re
import logging
from examgrader.extractors.base import BasePDFExtractor
from examgrader.utils.prompts import PromptManager

logger = logging.getLogger(__name__)

class AnswerExtractor(BasePDFExtractor):
    """Extracts answers from PDF files"""
    
    def __init__(self, pdf_path: str, gemini_api):
        """Initialize the answer extractor.
        
        Args:
            pdf_path: Path to the PDF file
            gemini_api: Initialized GeminiAPI instance
        """
        super().__init__(pdf_path, gemini_api)
        self.last_question_number = None  # Track the last main question number
        self.last_subproblem = None  # Track the last subproblem letter
    
    def extract(self) -> str:
        """Extract answers from PDF pages.
        
        Returns:
            Concatenated string of all extracted answers
        """
        images = self.pdf_to_images()
        all_text = ""
        
        for page_num, image in enumerate(images, 1):
            logger.info(f"Processing page {page_num}/{len(images)} for answers")
            
            # Add context about previous question number to the prompt
            context_prompt = ""
            if self.last_question_number:
                context_prompt = f"Note: The previous page contained answers for question {self.last_question_number}"
                if self.last_subproblem:
                    context_prompt += f"{self.last_subproblem}"
                context_prompt += ". "
                context_prompt += f"If you see a lone subproblem letter (e.g., 'a', 'b', 'c') without a question number, "
                context_prompt += f"it likely belongs to question {self.last_question_number}. "
                context_prompt += f"If the page begins with text without a question number and subproblem letter,"
                context_prompt += f"treat it as a continuation of question {self.last_question_number}"
                if self.last_subproblem:
                    context_prompt += f"{self.last_subproblem}"
                context_prompt += f" and format it as 題號：{self.last_question_number}"
                if self.last_subproblem:
                    context_prompt += f"{self.last_subproblem}"
                context_prompt += "（續）. "
                context_prompt += f"IMPORTANT: This page may contain BOTH continuation text at the top from question {self.last_question_number}"
                if self.last_subproblem:
                    context_prompt += f"{self.last_subproblem}"
                context_prompt += f" AND new questions."
            
            full_prompt = PromptManager.get_answer_extraction_prompt() + "\n" + context_prompt
            
            text = self.gemini_api.generate_content(full_prompt, image)

            print(text)

            if text:
                # If no question number is found in the response and we have last_question_number,
                # it might mean the model missed the continuation - add a simple check
                if self.last_question_number and not re.search(r'題號：', text[:300]):
                    # Add continuity marker if the model didn't add one
                    continuation_marker = f"題號：{self.last_question_number}"
                    if self.last_subproblem:
                        continuation_marker += f"{self.last_subproblem}"
                    continuation_marker += "（續）"
                    text = f"{continuation_marker}\n" + text
                
                # Update last question number and subproblem based on the response
                # Only look for main question numbers (not continuations)
                question_matches = re.finditer(r'題號：(\d+)([a-z])?(?!（續）)', text)
                for match in question_matches:
                    self.last_question_number = match.group(1)
                    self.last_subproblem = match.group(2) if match.group(2) else None
                
                all_text += text + "\n"
                
        return all_text
