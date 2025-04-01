"""Module for extracting answers from PDF files."""

import re
import logging
from examgrader.extractors.base import BasePDFExtractor
from examgrader.utils.prompts import PromptManager

logger = logging.getLogger(__name__)

class QuestionNumberValidator:
    """Validates and corrects question numbers based on expected patterns."""
    
    def __init__(self, questions_dict=None):
        """Initialize the validator with a questions dictionary.
        
        Args:
            questions_dict: Dictionary mapping question numbers to subproblems
        """
        self.questions_dict = questions_dict or {}
        self.last_main_number = None
        self.last_subproblem = None
        
        # Create sequential mappings from the dictionary keys
        self.question_sequence = []
        self.subproblem_sequences = {}
        
        if self.questions_dict:
            # Get all question numbers
            all_keys = [str(key) for key in self.questions_dict.keys()]
            
            # Find main questions and their subproblems
            main_questions = set()
            subproblems = {}
            
            for key in all_keys:
                # If the key has a letter at the end, it's a subproblem (like "2a")
                if key and key[-1].isalpha() and key[:-1].isdigit():
                    main_q = key[:-1]  # Extract the main question number
                    main_questions.add(main_q)
                    
                    # Add to subproblems dictionary
                    if main_q not in subproblems:
                        subproblems[main_q] = []
                    subproblems[main_q].append(key[-1])  # Add the letter
                else:
                    # It's a standalone question
                    self.question_sequence.append(key)
            
            # Create subproblem sequences for questions with subproblems
            for main_q in subproblems:
                self.subproblem_sequences[main_q] = sorted(subproblems[main_q])
            
            # Sort the question sequence
            self.question_sequence = sorted(self.question_sequence, key=lambda x: int(x) if x.isdigit() else 0)
                
        logger.debug(f"Question sequence: {self.question_sequence}")
        logger.debug(f"Subproblem sequences: {self.subproblem_sequences}")
    
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
        matches = list(re.finditer(r'題號：(\d+)((?:\([a-zA-Z]\)|\([a-zA-Z]\)\*\*|[a-zA-Z]|\*\*|[a-zA-Z]\*\*|)(?:（續）)?)', corrected_text))
        
        for match in matches:
            original_match = match.group(0)
            main_number = match.group(1)
            subproblem = match.group(2)
            
            logger.debug(f"Checking and correcting: {main_number}{subproblem}")
            corrected_number, corrected_subproblem = self._check_and_correct(
                main_number, subproblem
            )
            logger.debug(f"Corrected: {corrected_number}{corrected_subproblem}")
            
            # Check if an actual correction was made (values changed)
            values_changed = (corrected_number != main_number or corrected_subproblem != subproblem)
            
            if values_changed:
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
        """Check if the question number follows expected patterns based on the dictionary.
        
        Args:
            main_number: The main question number
            subproblem: The subproblem letter/identifier
            
        Returns:
            Tuple of (corrected_main_number, corrected_subproblem)
        """
        # Convert to strings for consistency
        main_number = str(main_number) if main_number else ""
        subproblem = str(subproblem) if subproblem else ""
        
        # Default to the original values
        corrected_main = main_number
        corrected_sub = subproblem
        
        # Clean the subproblem format for processing
        cleaned_subproblem = self._clean_subproblem_format(subproblem)
        
        # If we don't have a questions dictionary or it's empty, just return the original values
        if not self.questions_dict:
            return corrected_main, corrected_sub
            
        # First, validate the main question number
        if main_number not in self.questions_dict:
            # Find the closest valid question number
            corrected_main = self._find_closest_question(main_number)
            
        # Next, validate the subproblem (if any)
        if cleaned_subproblem:
            # Check if this is a valid subproblem for the question
            if corrected_main in self.subproblem_sequences:
                valid_subproblems = self.subproblem_sequences[corrected_main]
                
                # If the cleaned subproblem is not valid for this question
                if cleaned_subproblem not in valid_subproblems:
                    # Find the expected next subproblem
                    if not self.last_subproblem:
                        # If there was no previous subproblem, use the first one
                        expected_sub = valid_subproblems[0] if valid_subproblems else ""
                    else:
                        # Find what should come after the last subproblem
                        expected_sub = self._get_next_valid_subproblem(
                            corrected_main, 
                            self._clean_subproblem_format(self.last_subproblem)
                        )
                    
                    # If we found a valid expected subproblem, use it with standardized format
                    if expected_sub:
                        # Standardize to parentheses format
                        corrected_sub = f"({expected_sub})"
            else:
                # If the question doesn't have subproblems in our dictionary, 
                # we shouldn't have a subproblem here
                corrected_sub = ""
        elif subproblem:
            # Original had formatting but no valid letter/number inside
            corrected_sub = ""
                
        return corrected_main, corrected_sub
    
    def _find_closest_question(self, question_number):
        """Find the closest valid question number in the sequence.
        
        Args:
            question_number: The question number to find the closest match for
            
        Returns:
            The closest valid question number
        """
        if not self.question_sequence:
            return question_number
            
        # If the last question exists and is valid, use it to determine direction
        if self.last_main_number in self.question_sequence:
            last_idx = self.question_sequence.index(self.last_main_number)
            
            # Determine if we should look for the next question
            try:
                if int(question_number) > int(self.last_main_number):
                    # Looking forward
                    if last_idx + 1 < len(self.question_sequence):
                        return self.question_sequence[last_idx + 1]
                    return self.question_sequence[-1]  # Last question if at the end
                else:
                    # Looking backward
                    return self.last_main_number  # Just stick with the last one
            except ValueError:
                # If there was an error converting to int, just use the last question
                return self.last_main_number
        
        # If no reference point, find the closest numerically
        try:
            q_num = int(question_number)
            closest = min(self.question_sequence, key=lambda x: abs(int(x) - q_num))
            return closest
        except (ValueError, TypeError):
            # If there was an error, return the first question
            return self.question_sequence[0] if self.question_sequence else question_number
    
    def _clean_subproblem_format(self, subproblem):
        """Remove formatting from subproblem to get the bare identifier.
        
        Args:
            subproblem: The subproblem string with possible formatting
            
        Returns:
            Cleaned subproblem identifier
        """
        if not subproblem:
            return ""
            
        # Remove parentheses, continuation marker, and asterisks
        cleaned = subproblem.lower()
        cleaned = cleaned.replace("(", "").replace(")", "")
        cleaned = cleaned.replace("（續）", "").replace("**", "")
        
        # Handle special case where it's something like "a)"
        if cleaned and cleaned[0].isalpha():
            return cleaned[0]  # Just return the letter
            
        return cleaned
    
    def _get_next_valid_subproblem(self, question_number, current_subproblem):
        """Get the next valid subproblem for a question.
        
        Args:
            question_number: The question number
            current_subproblem: The current subproblem
            
        Returns:
            The next valid subproblem, or empty string if not found
        """
        if question_number not in self.subproblem_sequences:
            return ""
            
        valid_subs = self.subproblem_sequences[question_number]
        if not valid_subs:
            return ""
            
        # If current subproblem is not in the list, return the first one
        if current_subproblem not in valid_subs:
            return valid_subs[0]
            
        # Find the index of the current subproblem
        current_idx = valid_subs.index(current_subproblem)
        
        # Return the next one if available
        if current_idx + 1 < len(valid_subs):
            return valid_subs[current_idx + 1]
            
        # Otherwise, return the last one
        return valid_subs[-1]

class AnswerExtractor(BasePDFExtractor):
    """Extracts answers from PDF files"""
    
    def __init__(self, pdf_path: str, gemini_api, questions_dict=None):
        """Initialize the answer extractor.
        
        Args:
            pdf_path: Path to the PDF file
            gemini_api: Initialized GeminiAPI instance
            questions_dict: Dictionary mapping question numbers to subproblems
        """
        super().__init__(pdf_path, gemini_api)
        self.last_question_number = '1' # Track the last main question number
        self.last_subproblem = None  # Track the last subproblem letter
        self.validator = QuestionNumberValidator(questions_dict)  # Initialize validator with questions
    
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
            
            logger.debug("\n" + context_prompt + "\n")
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
                question_matches = re.finditer(r'題號：(\d+)((?:\([a-zA-Z]\)|\([a-zA-Z]\)\*\*|[a-zA-Z]|\*\*|[a-zA-Z]\*\*|))(?!（續）)', text)
                for match in question_matches:
                    self.last_question_number = match.group(1)
                    self.last_subproblem = match.group(2) if match.group(2) else None
                    logger.debug(f"Last question number: {self.last_question_number}, Last subproblem: {self.last_subproblem}")
                
                all_text += text + "\n"
                
        return all_text
