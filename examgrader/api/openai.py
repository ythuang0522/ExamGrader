"""Module for interacting with the OpenAI API."""

import logging
import time
import random
from openai import OpenAI
from openai import RateLimitError, APIError, APITimeoutError, APIConnectionError

logger = logging.getLogger(__name__)

class OpenAIAPI:
    """Handles core OpenAI API interactions."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key)
    
    def call_api(
        self, 
        user_prompt: str,
        system_prompt: str = "",
        model_name: str = "o3-mini",
        reasoning_effort: str = "medium",
        max_retries: int = 3
    ) -> str:
        """Core method for making OpenAI API calls with retry logic.
        
        Args:
            user_prompt: The user message containing the specific task
            system_prompt: The system message defining AI's role and behavior (optional)
            model_name: Name of the model to use
            reasoning_effort: Level of reasoning effort ("auto", "low", "high")
            max_retries: Maximum number of retry attempts
            
        Returns:
            The model's response text
            
        Raises:
            Exception: If API call fails after max retries
        """
        retries = 0
        backoff_time = 1  # Initial backoff time in seconds
        
        while retries <= max_retries:
            try:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": user_prompt})
                
                completion = self.client.chat.completions.create(
                    model=model_name,
                    reasoning_effort=reasoning_effort,
                    messages=messages,
                )
                
                response = completion.choices[0].message.content
                
                # Log token usage if available
                if hasattr(completion, 'usage'):
                    logger.debug(f"Token usage: {completion.usage}")
                    logger.debug(f"Total tokens: {completion.usage.total_tokens}")
                    logger.debug(f"Prompt tokens: {completion.usage.prompt_tokens}")
                    logger.debug(f"Completion tokens: {completion.usage.completion_tokens}")
                
                return response.strip()
                
            except (RateLimitError, APIError, APITimeoutError, APIConnectionError) as e:
                retries += 1
                if retries > max_retries:
                    logger.error(f"Max retries exceeded for OpenAI API call: {e}")
                    raise Exception(f"Failed after {max_retries} attempts: {str(e)}")
                
                # Add jitter to backoff time
                jitter = random.uniform(0, 0.5)
                sleep_time = backoff_time + jitter
                
                logger.warning(f"OpenAI API error: {e}. Retrying in {sleep_time:.2f} seconds (attempt {retries}/{max_retries})")
                time.sleep(sleep_time)
                
                # Exponential backoff
                backoff_time *= 2
            
            except Exception as e:
                logger.error(f"Unexpected error calling OpenAI API: {e}")
                raise
