"""Module for grading exam answers."""

import logging
from typing import Dict, Any, Tuple
import re
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import defaultdict

from examgrader.api.openai import OpenAIAPI
from examgrader.utils.prompts import PromptManager

logger = logging.getLogger(__name__)

class ExamGrader:
    """Handles exam grading using OpenAI API"""
    
    def __init__(self, openai_api):
        """Initialize the exam grader.
        
        Args:
            openai_api: Initialized OpenAIAPI instance
        """
        self.openai_api = openai_api
        self._score_lock = threading.Lock()  # Only need lock for accumulating total scores
    
    def _is_parent_question(self, q_num: str, questions: Dict[str, Dict[str, Any]]) -> bool:
        """Check if a question is a parent question by looking for subproblems.
        
        Args:
            q_num: Question number to check
            questions: Dictionary of all questions
            
        Returns:
            bool: True if the question has subproblems, False otherwise
        """
        # Check if there are any questions that start with this q_num followed by a letter
        return any(key.startswith(q_num) and len(key) > len(q_num) and key[len(q_num)].isalpha() 
                  for key in questions.keys())
    
    def _verify_subproblem_scores(self, q_num: str, questions: Dict[str, Dict[str, Any]]) -> None:
        """Verify that subproblem scores sum up to parent question score.
        
        Args:
            q_num: Parent question number
            questions: Dictionary of all questions
        """
        parent_score = int(questions[q_num]['score'])
        subproblem_scores = sum(
            int(q_data['score']) 
            for key, q_data in questions.items() 
            if key.startswith(q_num) and len(key) > len(q_num) and key[len(q_num)].isalpha()
        )
        
        if parent_score != subproblem_scores:
            logger.warning(
                f"Question {q_num}: Parent score ({parent_score}) does not match "
                f"sum of subproblem scores ({subproblem_scores})"
            )
    
    def _grade_question(self, q_num: str, question_data: Dict[str, Any], 
                       questions: Dict[str, Dict[str, Any]],
                       correct_answers: Dict[str, Dict[str, Any]], 
                       student_answers: Dict[str, Dict[str, Any]],
                       results: Dict[str, Any],
                       processed_parents: Dict[str, bool]) -> Tuple[float, float]:
        """Grade a single question.
        
        Args:
            q_num: Question number
            question_data: Question data dictionary
            questions: Dictionary of all questions
            correct_answers: Dictionary of correct answers
            student_answers: Dictionary of student answers
            results: Dictionary to store results
            processed_parents: Dictionary to track processed parent questions
            
        Returns:
            Tuple of (earned score, max score)
        """
        # Skip if this is a parent question with subproblems - we'll grade those individually
        if self._is_parent_question(q_num, questions) and not processed_parents.get(q_num, False):
            processed_parents[q_num] = True
            logger.info(f"Question {q_num} has subproblems, grading those individually")
            return 0, 0
            
        max_score = float(question_data['score'])
        
        # Check if we have both correct and student answers
        if q_num not in correct_answers or q_num not in student_answers:
            logger.warning(f"Missing {'correct' if q_num not in correct_answers else 'student'} answer for question {q_num}")
            results[q_num] = {
                'score': 0,
                'max_score': max_score,
                'reason': f"Missing {'correct' if q_num not in correct_answers else 'student'} answer",
                'question': question_data['text'],
            }
            
            # Format answers with tables and figures if available
            results[q_num]['correct_answer'] = self._format_answer_with_media(correct_answers.get(q_num, {}))
            results[q_num]['student_answer'] = self._format_answer_with_media(student_answers.get(q_num, {}))
            results[q_num]['rubric'] = question_data.get('rubric', 'No rubric available')
            return 0, max_score
            
        # Generate grading prompt
        prompt = PromptManager.get_grading_prompt(
            question_data, correct_answers[q_num], student_answers[q_num]
        )
        
        logger.info(f"Grading prompt: {prompt}")
        
        # Call API to grade
        score, reason = self.openai_api.grade_answer(prompt)
        
        # Ensure score doesn't exceed max
        score = min(score, max_score)
        
        # Store results
        results[q_num] = {
            'score': score,
            'max_score': max_score,
            'reason': reason,
            'question': question_data['text'],
        }
        
        # Format answers with tables and figures if available
        results[q_num]['correct_answer'] = self._format_answer_with_media(correct_answers.get(q_num, {}))
        results[q_num]['student_answer'] = self._format_answer_with_media(student_answers.get(q_num, {}))
        results[q_num]['rubric'] = question_data.get('rubric', 'No rubric available')
        
        logger.info(f"Question {q_num}: {score}/{max_score} - {reason}")
        return score, max_score

    def grade_exam(self, questions: Dict[str, Dict[str, Any]], 
                   correct_answers: Dict[str, Dict[str, Any]], 
                   student_answers: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, Any], float, float]:
        """Grade exam answers using OpenAI in parallel.
        
        Args:
            questions: Dictionary of question data including text, score, tables, and figures
            correct_answers: Dictionary of correct answers with text, tables, and figures
            student_answers: Dictionary of student answers with text, tables, and figures
        
        Returns:
            Tuple of (results dict, total score, max possible score)
        """
        total_score = 0
        max_possible_score = 0
        results = {}
        processed_parents = {}  # Changed from set to dict for thread-safety

        # Sort questions to process in a predictable order
        sorted_questions = sorted(questions.items())
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor() as executor:
            # Submit all grading tasks
            future_to_question = {
                executor.submit(
                    self._grade_question,
                    q_num, question_data, questions, correct_answers, 
                    student_answers, results, processed_parents
                ): q_num 
                for q_num, question_data in sorted_questions
            }
            
            # Collect results as they complete
            for future in future_to_question:
                score, max_score = future.result()
                with self._score_lock:  # Still need lock for accumulating totals
                    total_score += score
                    max_possible_score += max_score

        logger.info(f"Total Score: {total_score}/{max_possible_score}")
        return results, total_score, max_possible_score

    def grade_exam_multiple_rounds(self, questions: Dict[str, Dict[str, Any]], 
                                 correct_answers: Dict[str, Dict[str, Any]], 
                                 student_answers: Dict[str, Dict[str, Any]], 
                                 num_rounds: int = 1,
                                 output_prefix: str = "results") -> Tuple[Dict[str, Any], float, float]:
        """Grade exam answers multiple times and return the best score.
        
        Args:
            questions: Dictionary of question data including text, score, tables, and figures
            correct_answers: Dictionary of correct answers with text, tables, and figures
            student_answers: Dictionary of student answers with text, tables, and figures
            num_rounds: Number of grading rounds to perform (default: 1)
            output_prefix: Prefix for individual round result files (default: "results")
            
        Returns:
            Tuple of (best results dict, best total score, max possible score)
        """
        best_score = 0
        best_results = None
        best_max_possible = 0
        
        logger.info(f"Starting {num_rounds} grading rounds")
        
        for round_num in range(1, num_rounds + 1):
            logger.info(f"Starting grading round {round_num}/{num_rounds}")
            
            # Run single round grading
            results, total_score, max_possible = self.grade_exam(questions, correct_answers, student_answers)
            
            # Save individual round results
            round_output = f"{output_prefix}_r{round_num}.txt"
            self.save_results(results, total_score, max_possible, round_output)
            logger.info(f"Round {round_num} score: {total_score}/{max_possible}")
            
            # Track best score
            if total_score > best_score:
                best_score = total_score
                best_results = results
                best_max_possible = max_possible
                logger.info(f"New best score in round {round_num}: {best_score}/{best_max_possible}")
                
        logger.info(f"Completed {num_rounds} rounds. Best score: {best_score}/{best_max_possible}")
        return best_results, best_score, best_max_possible
    
    def save_results(self, results: Dict[str, Any], total_score: float, max_possible: float, output_file: str) -> None:
        """Save grading results to a file.
        
        Args:
            results: Dictionary of grading results
            total_score: Total score earned
            max_possible: Maximum possible score
            output_file: Path to save results
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"總分: {total_score:.1f}/{max_possible:.1f}\n\n")
            f.write("-" * 80 + "\n\n")
            
            # Sort question numbers naturally
            sorted_questions = sorted(results.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.findall(r'\d+|\D+', x)])
            
            for q_num in sorted_questions:
                result = results[q_num]
                f.write(f"題號: {q_num}\n")
                f.write("\n問題:\n")
                f.write(f"{result['question']}\n\n")
                # Include rubric if available
                if 'rubric' in result and result['rubric'] != 'No rubric available':
                    f.write("\n評分標準:\n")
                    f.write(f"{result['rubric']}\n")
                f.write("\n標準答案:\n")
                f.write(f"{result['correct_answer']}\n\n")
                f.write("學生答案:\n")
                f.write(f"{result['student_answer']}\n\n")
                f.write(f"得分: {result['score']:.1f}/{result['max_score']:.1f}\n")
                f.write(f"\n評分理由: {result['reason']}\n")
                f.write("-" * 80 + "\n\n")
                
        logger.info(f"Saved grading results to {output_file}")

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
