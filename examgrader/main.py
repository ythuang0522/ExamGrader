"""Main entry point for the ExamGrader application."""

import argparse
import logging
import os
from enum import Enum
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor

from examgrader.api.gemini import GeminiAPI
from examgrader.api.openai import OpenAIAPI
from examgrader.utils.parsers import parse_questions, parse_answers
from examgrader.utils.jailbreak_detector import JailbreakDetector
from examgrader.utils.pdf_partitioner import partition_multi_student_pdf
from examgrader.grader import ExamGrader

logger = logging.getLogger(__name__)

class InputType(Enum):
    """Enum representing the different input types for exam grading."""
    SINGLE_PDF = 1
    DIRECTORY_OF_PDFS = 2
    MULTI_STUDENT_PDF = 3


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Grade exam answers using AI')
    
    # Required arguments
    parser.add_argument('-q', '--questions-file', required=True, 
                       help='Path to the questions file')
    parser.add_argument('-c', '--correct-answers-file', required=True, 
                       help='Path to the correct answers file')
    parser.add_argument('-s', '--student-answers-file', required=True, 
                       help='Path to student answers file or directory containing multiple PDF files')
    
    # Optional arguments
    parser.add_argument('-o', '--output-file', 
                       help='Optional: Path to save grading results (defaults to student_file_results.txt)')
    parser.add_argument('-r', '--rounds', type=int, default=1, 
                       help='Number of grading rounds to run (default: 1)')
    parser.add_argument('-t', '--workers', type=int, default=12, 
                       help='Number of worker threads for parallel processing (default: 12)')
    
    # API keys
    parser.add_argument('--gemini-api-key', 
                       help='Google Gemini API key (overrides GEMINI_API_KEY in .env)')
    parser.add_argument('--openai-api-key', 
                       help='OpenAI API key (overrides OPENAI_API_KEY in .env)')
    
    # Multi-student PDF handling
    parser.add_argument('-m', '--split-multi-student-pdf', action='store_true',
                       help='Split a multi-student PDF into individual files')
    
    # Model configuration
    parser.add_argument('--gemini-model', type=str, 
                       default="gemini-2.5-flash-preview-04-17",
                       help='Gemini model to use (default: gemini-2.5-flash-preview-04-17)')
    parser.add_argument('--openai-model', type=str,
                       default="o4-mini",
                       help='OpenAI model to use (default: o4-mini)')
    
    # Debug and safety options
    parser.add_argument('--debug', action='store_true', 
                       help='Enable debug logging')
    parser.add_argument('--enable-jailbreak-check', action='store_true', 
                       help='Enable jailbreak detection (disabled by default)')
    
    return parser.parse_args()


def setup_logging(debug: bool) -> None:
    """
    Set up logging configuration.
    
    Args:
        debug: Whether to enable debug logging
    """
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set debug level for all examgrader modules
    for logger_name in logging.root.manager.loggerDict:
        if logger_name.startswith('examgrader'):
            logging.getLogger(logger_name).setLevel(log_level)
    
    logger.info(f"Logging level set to: {logging.getLevelName(log_level)}")


def determine_input_type(args) -> InputType:
    """
    Determine the input type based on the command line arguments.
    
    Args:
        args: Command line arguments
        
    Returns:
        InputType enum indicating the type of input
    """
    student_path = Path(args.student_answers_file)
    
    if args.split_multi_student_pdf:
        return InputType.MULTI_STUDENT_PDF
    elif student_path.is_dir():
        return InputType.DIRECTORY_OF_PDFS
    else:
        return InputType.SINGLE_PDF


def split_multi_student_pdf(args, gemini_api) -> str:
    """
    Handle multi-student PDF by splitting it into individual PDFs.
    
    Args:
        args: Command line arguments
        gemini_api: Initialized Gemini API client
        
    Returns:
        Path to directory containing split PDFs
    """
    student_path = Path(args.student_answers_file)
    
    # Create a default output directory next to the student file
    output_dir = student_path.parent / f"{student_path.stem}_split"
    
    logger.info(f"Splitting multi-student PDF: {student_path}")
    
    try:
        split_pdfs = partition_multi_student_pdf(
            student_path, 
            output_dir, 
            gemini_api, 
            max_workers=args.workers
        )
        logger.info(f"Created {len(split_pdfs)} individual student PDFs in {output_dir}")
        
        if not split_pdfs:
            logger.warning("No student PDFs were created. Check if the PDF contains student information.")
            return str(student_path)
            
        return str(output_dir)
    except Exception as e:
        logger.error(f"Error splitting multi-student PDF: {e}")
        # Fall back to processing the original PDF
        logger.warning("Falling back to processing the original PDF without splitting")
        return str(student_path)


def parse_questions_and_answers(questions_path: Path, correct_answers_path: Path, 
                     gemini_api: GeminiAPI, openai_api: OpenAIAPI, max_workers: int) -> Tuple[Dict, Dict]:
    """
    Parse question and answer files.
    
    Args:
        questions_path: Path to questions file
        correct_answers_path: Path to correct answers file
        gemini_api: Initialized GeminiAPI client
        openai_api: Initialized OpenAIAPI client
        max_workers: Maximum worker threads
        
    Returns:
        Tuple of (questions dict, correct answers dict)
    """
    # Verify files exist
    if not questions_path.exists():
        raise FileNotFoundError(f"Questions file not found: {questions_path}")
    
    if not correct_answers_path.exists():
        raise FileNotFoundError(f"Correct answers file not found: {correct_answers_path}")
    
    # Process questions file
    logger.info(f"Parsing questions from {questions_path}")
    questions, questions_json = parse_questions(
        str(questions_path),  # Convert Path to string
        gemini_api=gemini_api,
        openai_api=openai_api,
        max_workers=max_workers
    )
    
    # Process correct answers file
    logger.info(f"Parsing correct answers from {correct_answers_path}")
    correct_answers, correct_json = parse_answers(
        str(correct_answers_path),  # Convert Path to string
        gemini_api=gemini_api,
        is_correct_answer=True, 
        questions_dict=questions
    )
    
    return questions, correct_answers


def process_directory_of_pdfs(directory_path: Path, questions: Dict, correct_answers: Dict, 
                             grader: ExamGrader, args, gemini_api: GeminiAPI) -> None:
    """
    Process all PDF files in a directory.
    
    Args:
        directory_path: Path to directory containing PDFs
        questions: Questions dictionary
        correct_answers: Correct answers dictionary
        grader: ExamGrader instance
        args: Command line arguments
        gemini_api: Initialized GeminiAPI client
    """
    pdf_files = sorted(directory_path.glob('*.pdf'))
    
    if not pdf_files:
        logger.warning(f"No PDF files found in directory: {directory_path}")
        return
        
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    # Process files in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = []
        for student_file in pdf_files:
            logger.info(f"\nProcessing student file: {student_file}")
            # Clear output file for each student to generate unique output
            current_args = args
            current_args.output_file = None
            # Submit each student file for processing
            future = executor.submit(
                process_single_student_pdf,
                student_file,
                questions,
                correct_answers,
                grader,
                current_args,
                gemini_api
            )
            futures.append(future)
        
        # Wait for all futures to complete
        for future in futures:
            try:
                future.result()  # This will raise any exceptions that occurred
            except Exception as e:
                logger.error(f"Error processing student file: {e}")


def process_single_student_pdf(student_path: Path, questions: Dict, correct_answers: Dict, 
                              grader: ExamGrader, args, gemini_api: GeminiAPI) -> None:
    """
    Process a single student PDF file.
    
    Args:
        student_path: Path to student PDF
        questions: Questions dictionary
        correct_answers: Correct answers dictionary
        grader: ExamGrader instance
        args: Command line arguments
        gemini_api: Initialized GeminiAPI client
    """
    if not student_path.exists():
        logger.error(f"Student file not found: {student_path}")
        return
        
    # Set default output file if not specified
    if not args.output_file:
        output_file = str(student_path.parent / f"{student_path.stem}_results.txt")
    else:
        output_file = args.output_file
            
    # Parse student answers
    logger.info(f"Parsing student answers from {student_path}")
    student_answers, student_json = parse_answers(
        str(student_path),  # Convert Path to string
        gemini_api=gemini_api,
        is_correct_answer=False, 
        questions_dict=questions
    )
    logger.info(f"Saved parsed student answers to {student_json}")

    # Check for jailbreak attempts if enabled
    if not args.enable_jailbreak_check:
        if has_jailbreak_attempt(student_path, student_answers, output_file, grader, gemini_api):
            logger.warning(f"Jailbreak attempt detected in {student_path}. Aborting grading.")
            return

    # Grade the exam
    grade_exam(student_path, student_answers, questions, correct_answers, output_file, grader, args.rounds)


def has_jailbreak_attempt(student_path: Path, student_answers: Dict, 
                        output_file: str, grader: ExamGrader, gemini_api: GeminiAPI) -> bool:
    """
    Check if the student file contains jailbreak attempts.
    
    Args:
        student_path: Path to student PDF
        student_answers: Student answers dictionary
        output_file: Output file for results
        grader: ExamGrader instance
        gemini_api: Initialized GeminiAPI client
        
    Returns:
        True if a jailbreak attempt is detected, False otherwise
    """
    logger.info(f"Checking student answers for jailbreak attempts")
    detector = JailbreakDetector(gemini_api)
    
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
        
        # Create simplified results template with fixed max score
        results = {
            'jailbreak': {
                'question': 'Security Check',
                'correct_answer': 'N/A',
                'student_answer': 'N/A',
                'score': 0,
                'max_score': 100,
                'reason': f'Grading aborted due to jailbreak attempt. See {jailbreak_output} for details.'
            }
        }
        
        # Save results using the existing grader method
        grader.save_results(results, 0, 100, output_file)
        logger.info(f"Zero score report saved to {output_file}")
        return True
        
    return False


def grade_exam(student_path: Path, student_answers: Dict, questions: Dict, 
             correct_answers: Dict, output_file: str, grader: ExamGrader, rounds: int) -> None:
    """
    Grade a student's exam using the ExamGrader class.
    
    Args:
        student_path: Path to student PDF
        student_answers: Student answers dictionary
        questions: Questions dictionary
        correct_answers: Correct answers dictionary
        output_file: Output file for results
        grader: ExamGrader instance
        rounds: Number of grading rounds
    """
    logger.info(f"Grading {student_path} with {rounds} round(s)")
    
    # Use the output file path without extension as prefix for round results
    output_prefix = str(Path(output_file).with_suffix(''))
    
    try:
        if rounds > 1:
            # Use multiple rounds grading
            results, total_score, max_possible = grader.grade_exam_multiple_rounds(
                questions, correct_answers, student_answers,
                num_rounds=rounds,
                output_prefix=output_prefix
            )
        else:
            # Use single round grading
            results, total_score, max_possible = grader.grade_exam(
                questions, correct_answers, student_answers
            )
            
        # Save final results
        grader.save_results(results, total_score, max_possible, output_file)
        logger.info(f"Grading complete. Results saved to {output_file}")
        logger.info(f"Total score: {total_score}/{max_possible}")
        
    except Exception as e:
        logger.error(f"Error during grading: {e}")
        # Write error message to output file
        with open(output_file, 'w') as f:
            f.write(f"Error grading exam: {str(e)}\n")
        raise


def main():
    """Main entry point."""
    args = parse_args()
    
    # Set up logging
    setup_logging(args.debug)
    
    try:
        # Load environment variables from .env file
        load_dotenv()
        
        # Set up API keys with priority to command line arguments
        gemini_api_key = args.gemini_api_key or os.getenv('GEMINI_API_KEY')
        openai_api_key = args.openai_api_key or os.getenv('OPENAI_API_KEY')

        if not openai_api_key and not gemini_api_key:
            raise ValueError("OpenAI API and Gemini API key must be provided either via --openai-api-key or OPENAI_API_KEY in .env")
            
        # Set up API clients
        gemini_api = GeminiAPI(gemini_api_key, model_name=args.gemini_model)
        openai_api = OpenAIAPI(openai_api_key, model_name=args.openai_model)
        
        # Initialize grader
        grader = ExamGrader(openai_api, max_workers=args.workers)
        
        # Determine input type
        input_type = determine_input_type(args)
        
        # Convert file paths to Path objects
        questions_path = Path(args.questions_file).resolve()
        correct_answers_path = Path(args.correct_answers_file).resolve()
        
        # Parse questions and correct answers
        questions, correct_answers = parse_questions_and_answers(
            questions_path, correct_answers_path, gemini_api, openai_api, args.workers
        )
        
        # Process student answers based on input type
        if input_type == InputType.MULTI_STUDENT_PDF:
            # split multi-student PDF, returns path to directory of split PDFs
            output_dir = split_multi_student_pdf(args, gemini_api)

            # If in debug mode, stop after splitting the PDF
            if args.debug:
                logger.debug("Debug mode: Stopping after PDF split")
                return 0
            # Update student path to the split directory and continue with directory processing
            args.student_answers_file = output_dir
            process_directory_of_pdfs(Path(output_dir), questions, correct_answers, grader, args, gemini_api)
            
        elif input_type == InputType.DIRECTORY_OF_PDFS:
            # Process all PDFs in the directory
            process_directory_of_pdfs(Path(args.student_answers_file), questions, correct_answers, 
                                     grader, args, gemini_api)
            
        else:  # InputType.SINGLE_PDF
            # Process a single student PDF
            process_single_student_pdf(Path(args.student_answers_file), questions, correct_answers, 
                                      grader, args, gemini_api)
        
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return 1
        
    return 0


if __name__ == "__main__":
    exit(main())
