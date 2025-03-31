"""Main entry point for the ExamGrader application."""

import argparse
import logging
import os
from dotenv import load_dotenv
from pathlib import Path

from examgrader.api.gemini import GeminiAPI
from examgrader.api.openai import OpenAIAPI
from examgrader.utils.parsers import parse_questions, parse_answers
from examgrader.utils.jailbreak_detector import JailbreakDetector
from examgrader.grader import ExamGrader

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_student_answers(student_path: Path, questions: dict, correct_answers: dict, 
                          grader: ExamGrader, args, gemini_api_key: str) -> None:
    """Process a single student's answers file.
    
    Args:
        student_path: Path to the student answers file
        questions: Dictionary of question data
        correct_answers: Dictionary of correct answers
        grader: Initialized ExamGrader instance
        args: Command line arguments
        gemini_api_key: API key for Gemini
    """
    # Generate output filename based on student filename if not specified
    if not args.output_file:
        output_file = str(student_path.parent / f"{student_path.stem}_results.txt")
    else:
        output_file = args.output_file
        
    # Parse student answers
    logger.info(f"Parsing student answers from {student_path}")
    student_answers, student_json = parse_answers(
        str(student_path), gemini_api_key, is_correct_answer=False
    )
    logger.info(f"Saved parsed student answers to {student_json}")

    # Check for jailbreak attempts (always active)
    logger.info(f"Checking student answers for jailbreak attempts")
    detector = JailbreakDetector(gemini_api_key)
    
    # Detect jailbreaks directly in the parsed answers
    jailbreak_results = detector.detect_jailbreaks(student_answers)
    logger.info(f"Jailbreak results: {jailbreak_results}")
    
    # Check if unsafe content was detected
    has_jailbreak = jailbreak_results.get("safety_status") == "UNSAFE"
    
    if has_jailbreak:
        # Save jailbreak detection results
        jailbreak_output = str(student_path.parent / f"{student_path.stem}_jailbreak_results.json")
        with open(jailbreak_output, 'w', encoding='utf-8') as f:
            import json
            json.dump(jailbreak_results, f, ensure_ascii=False, indent=2)
    
        logger.warning(f"⚠️ JAILBREAK ATTEMPTS DETECTED in student answers! See {jailbreak_output} for details")
        
        # Skip grading and assign zero scores
        logger.warning("Skipping grading due to jailbreak detection. Assigning zero scores.")
        
        # Create results with zero scores for all questions with corresponding correct answers
        results = {}
        valid_questions = [q_id for q_id in questions if q_id in correct_answers]
        
        # Calculate total possible score only for valid questions
        max_possible = sum(int(questions[q_id]['score']) for q_id in valid_questions)
        
        for q_id in valid_questions:
            question = questions[q_id]
            correct_answer_text = correct_answers[q_id]['text']
            
            # Check if this question ID exists in student_answers
            student_answer_text = "No student answer provided"
            if q_id in student_answers:
                student_answer_text = student_answers[q_id]['text']
            
            results[q_id] = {
                'question': question['text'],
                'correct_answer': correct_answer_text,
                'student_answer': student_answer_text,
                'score': 0,
                'max_score': int(question['score']),
                'reason': 'Grading skipped due to jailbreak detection'
            }
        
        # Save zero-score results
        logger.info(f"Saving zero-score results to {output_file}")
        grader.save_results(results, 0, max_possible, output_file)
        logger.info(f"Grading skipped. Total score: 0/{max_possible}")
        return

    # Grade exam
    output_prefix = str(Path(output_file).with_suffix(''))
    if args.rounds > 1:
        results, total_score, max_possible = grader.grade_exam_multiple_rounds(
            questions, correct_answers, student_answers,
            num_rounds=args.rounds,
            output_prefix=output_prefix
        )
    else:
        results, total_score, max_possible = grader.grade_exam(
            questions, correct_answers, student_answers
        )

    # Save results
    logger.info(f"Saving results to {output_file}")
    grader.save_results(results, total_score, max_possible, output_file)
    logger.info(f"Grading complete. Total score: {total_score}/{max_possible}")

def main():
    """Main entry point for the command-line interface."""
    # Load environment variables from .env file
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Grade exam answers using AI')
    parser.add_argument('-q', '--questions-file', required=True, help='Path to the questions file')
    parser.add_argument('-c', '--correct-answers-file', required=True, help='Path to the correct answers file')
    parser.add_argument('-s', '--student-answers-file', required=True, 
                       help='Path to student answers file or directory containing multiple PDF files')
    parser.add_argument('-o', '--output-file', help='Optional: Path to save grading results (defaults to student_file_results.txt)')
    parser.add_argument('-r', '--rounds', type=int, default=1, help='Number of grading rounds to run (default: 1)')
    parser.add_argument('--gemini-api-key', help='Gemini API key (overrides GEMINI_API_KEY in .env)')
    parser.add_argument('--openai-api-key', help='OpenAI API key (overrides OPENAI_API_KEY in .env)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--workers', type=int, default=12, help='Number of worker threads for parallel processing (default: 12)')
    
    args = parser.parse_args()

    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Set up API keys with priority to command line arguments
    gemini_api_key = args.gemini_api_key or os.getenv('GEMINI_API_KEY')
    openai_api_key = args.openai_api_key or os.getenv('OPENAI_API_KEY')

    if not openai_api_key and not gemini_api_key:
        raise ValueError("OpenAI API and Gemini API key must be provided either via --openai-api-key or OPENAI_API_KEY in .env")

    # Process files with PDF support
    logger.info(f"Parsing questions from {args.questions_file}")
    questions, questions_json = parse_questions(
        args.questions_file, 
        gemini_api_key, 
        openai_api_key, 
        max_workers=args.workers
    )
    logger.info(f"Saved parsed questions to {questions_json}")
    
    logger.info(f"Parsing correct answers from {args.correct_answers_file}")
    correct_answers, correct_json = parse_answers(args.correct_answers_file, gemini_api_key, is_correct_answer=True)
    logger.info(f"Saved parsed correct answers to {correct_json}")

    # Initialize grader
    openai_api = OpenAIAPI(openai_api_key)
    grader = ExamGrader(openai_api)

    # Process student answers (single file or directory)
    student_path = Path(args.student_answers_file)
    if student_path.is_dir():
        # Process all PDF files in directory
        pdf_files = sorted(student_path.glob('*.pdf'))
        if not pdf_files:
            logger.warning(f"No PDF files found in directory: {student_path}")
            return
            
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        for student_file in pdf_files:
            logger.info(f"\nProcessing student file: {student_file}")
            # Clear output file for each student to generate unique output
            args.output_file = None
            process_student_answers(student_file, questions, correct_answers, grader, args, gemini_api_key)
    else:
        # Process single file
        process_student_answers(student_path, questions, correct_answers, grader, args, gemini_api_key)

if __name__ == '__main__':
    main()
