"""Module for interacting with the OpenAI API."""

import logging
import re
from openai import OpenAI

logger = logging.getLogger(__name__)

class OpenAIAPI:
    """Handles all interactions with the OpenAI API for grading."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key)
    
    def grade_answer(self, prompt: str) -> tuple:
        """Call OpenAI API to grade an answer.
        
        Args:
            prompt: The grading prompt containing question, correct answer, and student answer
            
        Returns:
            Tuple of (score, reason)
        """
        try:
            completion = self.client.chat.completions.create(
                model='o3-mini',
                messages=[{"role": "user", "content": prompt}],
            )

            reply = completion.choices[0].message.content
            
            score_match = re.search(r'得分：(\d+)', reply)
            reason_match = re.search(r'理由：(.*)', reply)
            
            score = int(score_match.group(1)) if score_match else 0
            reason = reason_match.group(1).strip() if reason_match else "未提供理由"

            return score, reason
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return 0, f"API error: {str(e)}"
