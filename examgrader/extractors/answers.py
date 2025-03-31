"""Module for extracting answers from PDF files."""

import re
import logging
from examgrader.extractors.base import BasePDFExtractor
from examgrader.utils.prompts import PromptManager

logger = logging.getLogger(__name__)

class QuestionNumberValidator:
    """Validates and corrects question numbers based on expected patterns."""
    
    # Common character confusion pairs for correction
    CONFUSION_PAIRS = {
        '6': 'b', 'b': '6',
        '5': 'S', 'S': '5',
        '(': 'C', 'C': '(',
        ')': 'c', 'c': ')',
        '0': 'O', 'O': '0',
        '1': 'I', 'I': '1',
        '8': 'B', 'B': '8',
    }
    
    def __init__(self):
        """Initialize the validator."""
        self.last_main_number = None
        self.last_subproblem = None
    
    def update_last_reference(self, main_number, subproblem):
        """Update the reference values for last question number and subproblem."""
        self.last_main_number = main_number
        self.last_subproblem = subproblem
    
    def validate_and_correct(self, current_text):
        """Validate the question numbers in text and correct if necessary.
        
        Args:
            current_text: The text containing question numbers to validate
            
        Returns:
            Corrected text with valid question numbers
        """
        if not current_text or not self.last_main_number:
            return current_text
            
        # Process each 題號 in the text
        corrected_text = current_text
        
        # Find all question numbers in the text
        matches = list(re.finditer(r'題號：(\d+)(.*?)(?=\n|題號：|$)', corrected_text))
        
        for match in matches:
            original_match = match.group(0)
            main_number = match.group(1)
            subproblem = match.group(2)
            
            corrected_number, corrected_subproblem = self._check_and_correct(
                main_number, subproblem
            )
            
            # Check if an actual correction was made (values changed)
            values_changed = (corrected_number != main_number or corrected_subproblem != subproblem)
            
            # Check if this is a valid sequential progression (such as 5b to 6)
            is_valid_progression = (
                self.last_subproblem and 
                main_number != self.last_main_number and
                main_number.isdigit() and 
                self.last_main_number.isdigit() and
                int(main_number) == int(self.last_main_number) + 1
            )
            
            if values_changed and not is_valid_progression:
                # Construct the corrected 題號 format
                corrected_marker = f"題號：{corrected_number}"
                if corrected_subproblem:
                    corrected_marker += corrected_subproblem
                
                # Replace the original with the corrected version
                logger.info(f"\nCorrecting question number from {original_match} to {corrected_marker}\n")
                corrected_text = corrected_text.replace(original_match, corrected_marker)
                
                # Update the reference values after making a correction
                self.update_last_reference(corrected_number, corrected_subproblem)
            else:
                # Even if no correction was needed, update the reference values
                self.update_last_reference(main_number, subproblem)
        
        return corrected_text
    
    def _check_and_correct(self, main_number, subproblem):
        """Check if the question number follows expected patterns and correct if needed.
        
        Args:
            main_number: The main question number
            subproblem: The subproblem letter/identifier
            
        Returns:
            Tuple of (corrected_main_number, corrected_subproblem)
        """
        # Convert to strings for consistency
        main_number = str(main_number) if main_number else None
        subproblem = str(subproblem) if subproblem else None
        
        # Default to the original values
        corrected_main = main_number
        corrected_sub = subproblem
        
        #logger.info(f"Checking and correcting question number {main_number} and subproblem {subproblem}")
        #logger.info(f"Last main number: {self.last_main_number}, Last subproblem: {self.last_subproblem}")

        # Case 1: Expected sequential main question (1,2,3...)
        if self.last_subproblem is None and int(main_number) > int(self.last_main_number) + 1:
            # Check if it might be a character confusion - main number jumps too far
            expected_next_number = str(int(self.last_main_number) + 1)
            
            # First check if the main_number contains the expected number
            if self._check_character_match(main_number, expected_next_number):
                corrected_main = expected_next_number
        
        # Case 2: Current has same main number but subproblem doesn't follow sequence
        elif main_number == self.last_main_number and subproblem:
            expected_next_subproblem = self._get_next_subproblem(self.last_subproblem)
            logger.info(f"Expected next subproblem: {expected_next_subproblem}")
            
            if subproblem != expected_next_subproblem and expected_next_subproblem:
                # Check if expected subproblem character is in the confusion pairs
                if self._check_character_match(subproblem, expected_next_subproblem):
                    corrected_sub = expected_next_subproblem
        
        # Case 3: We expected a subproblem but got a new main number
        elif self.last_subproblem and main_number != self.last_main_number:
            # Check if this is a valid sequential progression (e.g., 5b to 6)
            if main_number.isdigit() and int(main_number) == int(self.last_main_number) + 1:
                # This is a valid new question number, not a confused subproblem
                pass
            # Only correct if it's not a natural progression and could be a confused character
            elif main_number in self.CONFUSION_PAIRS and self.CONFUSION_PAIRS[main_number].lower() in "abcdefghijklmnopqrstuvwxyz":
                corrected_main = self.last_main_number
                corrected_sub = self.CONFUSION_PAIRS[main_number]
        
        return corrected_main, corrected_sub
    
    def _get_next_subproblem(self, current_subproblem):
        """Determine the expected next subproblem letter based on current."""
        if not current_subproblem:
            return "a"
            
        # Handle potential formatting differences
        cleaned_subproblem = current_subproblem.lower().replace("(", "").replace(")", "").replace("（續）", "")
        
        if cleaned_subproblem in "abcdefghijklmnopqrstuvwxyz":
            next_letter_index = ord(cleaned_subproblem) - ord('a') + 1
            if next_letter_index < 26:
                return chr(ord('a') + next_letter_index)
        return None
    
    def _check_character_match(self, text, expected_char):
        """Checking commonly confused characters.
        
        Args:
            text: The text to check
            expected_char: expected character to match
            
        Returns:
            If expected_char is provided, returns True if any character in text 
            matches or could be substituted to match the expected character.
        """
            
        # If expected_char is provided, we're checking if any substitution would match it
        if expected_char:
            # Direct match for characters that are in our confusion pairs
            if expected_char in text and expected_char in self.CONFUSION_PAIRS:
                return True
                
            # Check if any character in text could be substituted to match expected
            for char in text:
                if char in self.CONFUSION_PAIRS and self.CONFUSION_PAIRS[char] == expected_char:
                    return True
                    
            # Check if expected_char's confusion pair appears in text
            if expected_char in self.CONFUSION_PAIRS and self.CONFUSION_PAIRS[expected_char] in text:
                return True
                
            return False
                
        return False

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
        self.validator = QuestionNumberValidator()  # Initialize validator
    
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
                context_prompt += f"it likely belongs to question {self.last_question_number}"
                if self.last_subproblem:
                    context_prompt += f"{self.last_subproblem}"
                context_prompt += ". "
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
                context_prompt += f" AND answers for new questions."
            
            logger.info("\n" + context_prompt + "\n")
            full_prompt = PromptManager.get_answer_extraction_prompt() + "\n" + context_prompt
            
            text = self.gemini_api.generate_content(full_prompt, image)

            logger.info("\n" + text + "\n")

            if text:
                # If no question number is found in the response and we have last_question_number,
                # it might mean the model missed the continuation - add a simple check
                if self.last_question_number and not re.search(r'題號：', text[:500]):
                    # Add continuity marker if the model didn't add one
                    continuation_marker = f"題號：{self.last_question_number}"
                    if self.last_subproblem:
                        continuation_marker += f"{self.last_subproblem}"
                    continuation_marker += "（續）"
                    text = f"{continuation_marker}\n" + text
                
                # Validate and correct question numbers in the text
                self.validator.update_last_reference(self.last_question_number, self.last_subproblem)
                text = self.validator.validate_and_correct(text)
                
                # Update last question number and subproblem based on the response
                # Only look for main question numbers (not continuations)
                question_matches = re.finditer(r'題號：(\d+)([a-zA-Z])?(?!（續）)', text)
                for match in question_matches:
                    self.last_question_number = match.group(1)
                    self.last_subproblem = match.group(2) if match.group(2) else None
                
                all_text += text + "\n"
                
        return all_text
