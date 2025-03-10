"""Main entry point for the ExamGrader application."""

import argparse
import logging
import os
from dotenv import load_dotenv
from pathlib import Path

from examgrader.api.gemini import GeminiAPI
from examgrader.api.openai import OpenAIAPI
from examgrader.utils.parsers import parse_questions, parse_answers
from examgrader.grader import ExamGrader

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the command-line interface."""
    # Load environment variables from .env file
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Grade exam answers using AI')
    parser.add_argument('-q', '--questions-file', required=True, help='Path to the questions file')
    parser.add_argument('-c', '--correct-answers-file', required=True, help='Path to the correct answers file')
    parser.add_argument('-s', '--student-answers-file', required=True, help='Path to the student answers file')
    parser.add_argument('-o', '--output-file', help='Optional: Path to save grading results (defaults to student_file_results.txt)')
    parser.add_argument('--gemini-api-key', help='Gemini API key (overrides GEMINI_API_KEY in .env)')
    parser.add_argument('--openai-api-key', help='OpenAI API key (overrides OPENAI_API_KEY in .env)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()

    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Derive output filename from student answers file if not specified
    if not args.output_file:
        student_path = Path(args.student_answers_file)
        args.output_file = str(student_path.parent / f"{student_path.stem}_results.txt")

    # Set up API keys with priority to command line arguments
    gemini_api_key = args.gemini_api_key or os.getenv('GEMINI_API_KEY')
    openai_api_key = args.openai_api_key or os.getenv('OPENAI_API_KEY')

    if not openai_api_key and not gemini_api_key:
        raise ValueError("OpenAI API and Gemini API key must be provided either via --openai-api-key or OPENAI_API_KEY in .env")

    # Process files with PDF support
    logger.info(f"Parsing questions from {args.questions_file}")
    questions, questions_json = parse_questions(args.questions_file, gemini_api_key)
    logger.info(f"Saved parsed questions to {questions_json}")
    
    logger.info(f"Parsing correct answers from {args.correct_answers_file}")
    correct_answers, correct_json = parse_answers(args.correct_answers_file, gemini_api_key, is_correct_answer=True)
    logger.info(f"Saved parsed correct answers to {correct_json}")
    
    logger.info(f"Parsing student answers from {args.student_answers_file}")
    student_answers, student_json = parse_answers(args.student_answers_file, gemini_api_key, is_correct_answer=False)
    logger.info(f"Saved parsed student answers to {student_json}")

    # Grade exam and save results
    logger.info("Grading exam")

    # Initialize APIs
    openai_api = OpenAIAPI(openai_api_key)

    grader = ExamGrader(openai_api)
    results, total_score, max_possible_score = grader.grade_exam(questions, correct_answers, student_answers)
    
    logger.info(f"Saving results to {args.output_file}")
    grader.save_results(results, total_score, args.output_file)
    
    logger.info(f"Grading complete. Total score: {total_score}/{max_possible_score}")

if __name__ == '__main__':
    main()
