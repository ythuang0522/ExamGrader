"""Module for interacting with the Gemini API."""

import logging
import time
from typing import Optional
from PIL import Image
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class GeminiAPI:
    """Handles all interactions with the Gemini API for text extraction."""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash-preview-04-17"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
    
    @staticmethod
    def should_retry_error(exception):
        """Determine if we should retry based on the exception"""
        if hasattr(exception, 'error'):
            error_dict = getattr(exception, 'error')
            if isinstance(error_dict, dict):
                # Check for rate limit or resource exhaustion
                status = error_dict.get('status', '')
                code = error_dict.get('code', 0)
                return (status == 'RESOURCE_EXHAUSTED' or  # API has reached its usage limits
                       code == 429 or  # HTTP 429 Too Many Requests - rate limiting
                       'quota' in error_dict.get('message', '').lower())  # Quota exceeded message
        return False

    @retry(
        stop=stop_after_attempt(5),  # Increase max attempts
        wait=wait_exponential(multiplier=2, min=4, max=60),  # Longer backoff
        retry=should_retry_error,  # Custom retry condition
        retry_error_callback=lambda retry_state: logger.warning(
            f"Retry {retry_state.attempt_number} failed with error: {retry_state.outcome.exception()}"
        )
    )
    def generate_content(self, prompt: str, image: Optional[Image.Image] = None, model_name: Optional[str] = None, thinking_budget: Optional[int] = None) -> Optional[str]:
        """Generate content using Gemini API with enhanced retry mechanism.
        
        Args:
            prompt: The text prompt to send to Gemini
            image: Optional image to include in the request
            model_name: Optional model name to override the default
            
        Returns:
            Generated text response or None if all retries fail
            
        Raises:
            Exception: If all retries fail and the error is not retryable
        """
        try:
            contents = [prompt]
            if image:
                contents.append(image)

            logger.debug(f"Contents: {contents}")
                        
            response = self.client.models.generate_content(
                model=model_name or self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget)
                ),
            )
            
            if not response.text:
                logger.warning("Gemini API returned empty response")
                return None
                
            logger.debug(f"Gemini API usage metadata: {response.usage_metadata}")

            return response.text
            
        except Exception as e:
            if self.should_retry_error(e):
                logger.warning(f"Retryable error occurred: {str(e)}")
                raise  # Let the retry decorator handle it
            else:
                logger.error(f"Non-retryable Gemini API error: {str(e)}")
                raise  # Propagate non-retryable errors
