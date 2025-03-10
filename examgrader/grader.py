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
        """Grade a single question with thread safety.
        
        Returns:
            Tuple of (score for this question, max possible score for this question)
        """
        # Handle parent questions
        if self._is_parent_question(q_num, questions):
            if not processed_parents.get(q_num, False):  # Thread-safe dictionary access
                self._verify_subproblem_scores(q_num, questions)
                processed_parents[q_num] = True  # Thread-safe dictionary update
                logger.info(f"Verified scores for parent question {q_num}")
            return 0, 0

        # Grade the question
        max_score = int(question_data['score'])
        correct_ans = correct_answers.get(q_num, {
            'text': "無標準答案",
            'tables': [],
            'figures': []
        })
        student_ans = student_answers.get(q_num, {
            'text': "無學生答案",
            'tables': [],
            'figures': []
        })

        prompt = PromptManager.get_grading_prompt(question_data, correct_ans, student_ans)
        score, reason = self.openai_api.grade_answer(prompt)
        
        adjusted_score = (score / 10) * max_score

        # No lock needed for results as each thread writes to a different key
        results[q_num] = {
            'score': adjusted_score,
            'max_score': max_score,
            'reason': reason,
            'question_data': question_data,
            'correct_answer': correct_ans,
            'student_answer': student_ans
        }
            
        logger.info(f"Question {q_num}: {adjusted_score}/{max_score} - {reason}")
        return adjusted_score, max_score

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
    
    def save_results(self, results: Dict[str, Any], total_score: float, output_file: str) -> None:
        """Save grading results to a file.
        
        Args:
            results: Dictionary of grading results
            total_score: Total score achieved
            output_file: Path to save the results
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                for q_num, result in results.items():
                    f.write(f"\n題號 {q_num}:\n")
                    
                    # Write question content
                    question_data = result['question_data']
                    f.write(f"題目內容：{question_data['text']}\n")
                    if question_data.get('tables'):
                        f.write("題目表格：\n")
                        for table in question_data['tables']:
                            table_md = table if isinstance(table, str) else table.to_markdown()
                            f.write(table_md + "\n")
                    if question_data.get('figures'):
                        f.write("題目圖形：\n")
                        for figure in question_data['figures']:
                            f.write(f"[{figure}]\n")
                            
                    # Write correct answer
                    correct_ans = result['correct_answer']
                    f.write(f"\n標準答案：{correct_ans['text']}\n")
                    if correct_ans.get('tables'):
                        f.write("標準答案表格：\n")
                        for table in correct_ans['tables']:
                            table_md = table if isinstance(table, str) else table.to_markdown()
                            f.write(table_md + "\n")
                    if correct_ans.get('figures'):
                        f.write("標準答案圖形：\n")
                        for figure in correct_ans['figures']:
                            f.write(f"[{figure}]\n")
                            
                    # Write student answer
                    student_ans = result['student_answer']
                    f.write(f"\n學生答案：{student_ans['text']}\n")
                    if student_ans.get('tables'):
                        f.write("學生答案表格：\n")
                        for table in student_ans['tables']:
                            table_md = table if isinstance(table, str) else table.to_markdown()
                            f.write(table_md + "\n")
                    if student_ans.get('figures'):
                        f.write("學生答案圖形：\n")
                        for figure in student_ans['figures']:
                            f.write(f"[{figure}]\n")
                    
                    f.write(f"\n得分：{result['score']}/{result['max_score']}\n")
                    f.write(f"理由：{result['reason']}\n")
                    f.write("\n" + "="*50 + "\n")  # Separator between questions
                
                f.write(f"\n總分：{total_score}\n")
            logger.info(f"Results saved to {output_file}")
        except Exception as e:
            logger.error(f"Error saving results to {output_file}: {e}")
