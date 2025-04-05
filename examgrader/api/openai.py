"""Module for interacting with the OpenAI API."""

import logging
import re
import time
import random
from openai import OpenAI
from openai import RateLimitError, APIError, APITimeoutError, APIConnectionError

logger = logging.getLogger(__name__)

class OpenAIAPI:
    """Handles all interactions with the OpenAI API for grading."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key)
    
    def grade_answer(self, prompt: str, model_name: str = "o3-mini") -> tuple:
        """Call OpenAI API to grade an answer.
        
        Args:
            prompt: The grading prompt containing question, correct answer, and student answer
            
        Returns:
            Tuple of (score, reason)
        """
        try:
            system_message = """You are an expert exam grader. Your task is to grade student answers based on the provided rubric criteria.
Follow these guidelines:
1. Carefully read and understand the rubric criteria for each question
2. Evaluate the student's answer against each criterion in the rubric
3. Assign points based on how well the student meets each criterion
4. Provide a detailed explanation for the points awarded for each criterion
5. Ensure the total score does not exceed the maximum points specified
6. Be objective and consistent in your grading

You MUST respond in EXACTLY this format:
得分：<score>
理由：<breif explanation of points awarded for each criterion>

The explanation should be clear and brief, explaining how many points were awarded for each criterion and why."""

            completion = self.client.chat.completions.create(
                model=model_name,
                #reasoning_effort = "high",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
            )

            reply = completion.choices[0].message.content
                # Retrieve token usage details
            token_usage = completion.usage
            logger.debug(f"Token usage: {token_usage}")
            logger.debug(f"Total tokens: {token_usage.total_tokens}")
            logger.debug(f"Prompt tokens: {token_usage.prompt_tokens}")
            logger.debug(f"Completion tokens: {token_usage.completion_tokens}")

            logger.debug(f"OpenAI API response: {reply}")
            
            score_match = re.search(r'得分：(\d+)', reply)
            reason_match = re.search(r'理由：([\s\S]*?)(?=\n\n|$)', reply)  # Updated pattern to capture multiline reason
            
            score = int(score_match.group(1)) if score_match else 0
            reason = reason_match.group(1).strip() if reason_match else "未提供理由"

            logger.debug(f"Extracted score: {score}, reason: {reason}")

            return score, reason
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return 0, f"API error: {str(e)}"
            
    def generate_rubric(self, prompt: str, max_retries: int = 3, model_name: str = "o3-mini", reasoning_effort: str = "high") -> str:
        """Call OpenAI API to generate a rubric for a question with retry logic.
        
        Args:
            prompt: The rubric generation prompt containing question details and score
            max_retries: Maximum number of retry attempts for API errors
            
        Returns:
            String containing the generated rubric
        """
        retries = 0
        backoff_time = 1  # Initial backoff time in seconds
        
        while retries <= max_retries:
            try:
                completion = self.client.chat.completions.create(
                    model=model_name,  
                    reasoning_effort = reasoning_effort,
                    messages=[{"role": "user", "content": prompt}],
                )
                
                rubric = completion.choices[0].message.content
                return rubric.strip()
                
            except (RateLimitError, APIError, APITimeoutError, APIConnectionError) as e:
                retries += 1
                if retries > max_retries:
                    logger.error(f"Max retries exceeded for OpenAI API call: {e}")
                    return f"Failed to generate rubric after {max_retries} attempts: {str(e)}"
                
                # Add jitter to backoff time to prevent all threads retrying simultaneously
                jitter = random.uniform(0, 0.5)
                sleep_time = backoff_time + jitter
                
                logger.warning(f"OpenAI API error: {e}. Retrying in {sleep_time:.2f} seconds (attempt {retries}/{max_retries})")
                time.sleep(sleep_time)
                
                # Exponential backoff
                backoff_time *= 2
                
            except Exception as e:
                logger.error(f"Unexpected error calling OpenAI API for rubric generation: {e}")
                return f"Failed to generate rubric: {str(e)}"
