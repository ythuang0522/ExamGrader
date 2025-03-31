"""Module for detecting jailbreak attempts in student exam answers."""

import logging
import json
from typing import Dict, Any, Optional, Tuple, List

from examgrader.api.gemini import GeminiAPI
from examgrader.utils.prompts import PromptManager

logger = logging.getLogger(__name__)

class JailbreakDetector:
    """Detects jailbreak attempts in student exam answers."""
    
    def __init__(self, gemini_api_key: str):
        """Initialize the jailbreak detector.
        
        Args:
            gemini_api_key: API key for Gemini
        """
        self.gemini_api = GeminiAPI(gemini_api_key)
        
    def detect_jailbreaks(self, student_answers: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Detect jailbreak attempts in student answers.
        
        Args:
            student_answers: Dictionary mapping question numbers to answer data
            
        Returns:
            Dictionary with global jailbreak detection results
        """
        # Concatenate all answers with clear question markers
        combined_text = ""
        for q_num, answer_data in student_answers.items():
            formatted_text = self._format_answer_with_media(answer_data)
            
            # Skip empty or very short answers
            if not formatted_text:
                continue
                
            combined_text += f"\nAnswer for Question {q_num}:\n{formatted_text}\n"
        
        # If no valid answers to analyze, return early
        if not combined_text:
            return {
                "safety_status": "SAFE",
                "details": "No valid answers to analyze"
            }
            
        # Get jailbreak detection results for all answers at once
        detection_result = self._check_for_jailbreak(combined_text)
                    
        # Return the global detection result
        return detection_result
                
    def _check_for_jailbreak(self, text: str) -> Dict[str, str]:
        """Check if text contains jailbreak attempts.
        
        Args:
            text: Text to check for jailbreak attempts
            
        Returns:
            Dictionary with detection results
        """
        # Get the jailbreak detection prompt
        prompt = PromptManager.get_jailbreak_detection_prompt()
        
        # Add the text to check to the prompt
        full_prompt = f"{prompt}\n\nUser-submitted answer:\n{text}"
        
        # Get the detection results from Gemini
        result = self.gemini_api.generate_content(full_prompt)
        
        if not result:
            return {
                "safety_status": "ERROR",
                "details": "Failed to analyze with Gemini API"
            }
            
        # Parse the response to extract the results
        # Expected format: SAFETY_STATUS: [SAFE/UNSAFE] / DETAILS: [...] / CONCERNS: [...]
        parsed_result = {
            "safety_status": "UNKNOWN",
            "details": "",
        }
                
        try:
            lines = result.strip().split('\n')
            current_section = None
            details_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith("SAFETY_STATUS:"):
                    # Extract just the status word, ignoring brackets and other characters
                    status_text = line.replace("SAFETY_STATUS:", "").strip()
                    # Remove any brackets, spaces, and get just the status word
                    parsed_result["safety_status"] = status_text.strip('[]').strip()
                    current_section = "safety_status"
                elif line.startswith("DETAILS:"):
                    current_section = "details"
                elif current_section == "details":
                    details_lines.append(line)
            
            # Join all details lines with newlines
            parsed_result["details"] = "\n".join(details_lines)
            
            return parsed_result
            
        except Exception as e:
            logger.error(f"Error parsing jailbreak detection result: {str(e)}")
            return {
                "safety_status": "ERROR",
                "details": f"Error parsing results: {str(e)}",
            }
    
    def _format_answer_with_media(self, answer_data: Dict[str, Any]) -> str:
        """Format answer text by replacing [TABLE] and [FIGURE] placeholders with actual content.
        
        Args:
            answer_data: Dictionary containing text, tables, and figures
            
        Returns:
            Formatted answer text with tables and figures inserted
        """
        if not answer_data:
            return 'N/A'
            
        formatted_text = answer_data['text']
        
        # Replace [TABLE] placeholders with table content
        for table in answer_data.get('tables', []):
            # If table is a string, use it directly; otherwise use to_markdown()
            table_md = table if isinstance(table, str) else table.to_markdown()
            formatted_text = formatted_text.replace('[TABLE]', table_md, 1)
            
        # Replace [FIGURE] placeholders with figure descriptions
        for figure in answer_data.get('figures', []):
            formatted_text = formatted_text.replace('[FIGURE]', f"[Figure: {figure}]", 1)
            
        return formatted_text 