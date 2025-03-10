"""Module for parsing exam data from various sources."""

import re
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from examgrader.api.gemini import GeminiAPI
from examgrader.extractors.questions import QuestionExtractor
from examgrader.extractors.answers import AnswerExtractor

logger = logging.getLogger(__name__)

@dataclass
class MarkdownTable:
    """Class to represent table data in markdown format.
    
    This class intentionally stores tables in their original markdown format
    to allow for less strict comparison between tables when grading.
    """
    markdown: str
    
    def to_markdown(self) -> str:
        """Return the table in markdown format"""
        return self.markdown
    
    @classmethod
    def from_markdown(cls, table_md: str) -> Optional['MarkdownTable']:
        """Create MarkdownTable object from markdown table string."""
        parsed = parse_table(table_md)
        if parsed is None:
            return None
        return cls(markdown=parsed)

def parse_table(table_md: str) -> Optional[str]:
    """Parse markdown table string.
    
    Performs basic validation and returns the raw markdown string.
    Can be used directly or via the MarkdownTable class for object-oriented usage.
    """
    try:
        # Simple validation to ensure it looks like a table
        lines = [line.strip() for line in table_md.strip().split('\n')]
        if len(lines) < 3:  # Need at least header, separator, and one data row
            return None
            
        # Just return the original markdown
        return table_md
    except Exception as e:
        logger.error(f"Error parsing markdown table: {e}")
        return None

def parse_questions(filepath: str, gemini_api_key: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Parse questions from either text file, PDF, or JSON.
    
    Returns a dictionary with question numbers as keys and dictionaries containing:
    - text: question text
    - score: question score
    - tables: list of TableData objects if present
    - figures: list of figure descriptions if present
    
    If a JSON file is provided, it's assumed to be a previously saved intermediate
    result that can be loaded directly without further processing.
    """
    questions = {}  # Initialize questions dictionary
    
    # Check if file is JSON (from save_intermediate_json)
    if filepath.lower().endswith('.json'):
        with open(filepath, 'r', encoding='utf-8') as f:
            questions = json.load(f)
            logger.info(f"Loaded pre-parsed questions from JSON file: {filepath}")
            return questions
            
    # Check if file is PDF
    if filepath.lower().endswith('.pdf'):
        if not gemini_api_key:
            raise ValueError("Gemini API key required for PDF processing")
        
        gemini_api = GeminiAPI(gemini_api_key)
        extractor = QuestionExtractor(filepath, gemini_api)
        content = extractor.extract()
        logger.info("Extracted question content from PDF")
    else:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            logger.info(f"Read question content from text file: {filepath}")
    
    # Parse the content
    sections = re.split(r'題號：(\d+[a-z]?(?:\s*\(續\)?)?)', content)
    
    # Process each section
    for i in range(1, len(sections), 2):
        full_q_number = sections[i].strip()
        q_content = sections[i+1].strip()
        
        # Remove (續) from the question number for storage
        base_q_number = re.sub(r'\s*\(續\)\s*$', '', full_q_number)
        
        # Extract score (only for non-continuation questions)
        score = "0"
        if '(續)' not in full_q_number:
            score_match = re.search(r'配分：(\d+)', q_content)
            score = score_match.group(1) if score_match else "0"
        
        # Remove the score line
        question_text = re.sub(r'配分：\d+\n?', '', q_content).strip()
        
        # Extract tables
        tables = []
        for table_match in re.finditer(r'<TABLE>\s*(.*?)\s*</TABLE>', question_text, re.DOTALL):
            table_data = parse_table(table_match.group(1))
            if table_data:
                tables.append(table_data)
        question_text = re.sub(r'<TABLE>\s*.*?\s*</TABLE>', '[TABLE]', question_text, flags=re.DOTALL)
        
        # Extract figures
        figures = []
        for figure_match in re.finditer(r'<FIGURE>(.*?)</FIGURE>', question_text):
            figures.append(figure_match.group(1).strip())
        question_text = re.sub(r'<FIGURE>.*?</FIGURE>', '[FIGURE]', question_text)
        
        print(question_text)
        if base_q_number in questions:
            # Append content for continuation questions
            questions[base_q_number]['text'] += '\n' + question_text
            questions[base_q_number]['tables'].extend(tables)
            questions[base_q_number]['figures'].extend(figures)
        else:
            # Create new entry for first occurrence
            questions[base_q_number] = {
                'text': question_text,
                'score': score,
                'tables': tables,
                'figures': figures
            }
    
    return questions

def parse_answers(filepath: str, gemini_api_key: Optional[str] = None, is_correct_answer: bool = True) -> Dict[str, Dict[str, Any]]:
    """Parse answers from either text file, PDF, or JSON.
    
    Returns a dictionary with question numbers as keys and dictionaries containing:
    - text: answer text with [TABLE] and [FIGURE] placeholders
    - tables: list of TableData objects if present
    - figures: list of figure descriptions if present
    
    If a JSON file is provided, it's assumed to be a previously saved intermediate
    result that can be loaded directly without further processing.
    """
    answers = {}  # Initialize answers dictionary
    
    # Check if file is JSON (from save_intermediate_json)
    if filepath.lower().endswith('.json'):
        with open(filepath, 'r', encoding='utf-8') as f:
            answers = json.load(f)
            logger.info(f"Loaded pre-parsed {'correct' if is_correct_answer else 'student'} answers from JSON file: {filepath}")
            return answers
            
    # Check if file is PDF
    if filepath.lower().endswith('.pdf'):
        if not gemini_api_key:
            raise ValueError("Gemini API key required for PDF processing")
        
        gemini_api = GeminiAPI(gemini_api_key)
        extractor = AnswerExtractor(filepath, gemini_api)
        content = extractor.extract()
        logger.info(f"Extracted {'correct' if is_correct_answer else 'student'} answer content from PDF")
    else:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            logger.info(f"Read {'correct' if is_correct_answer else 'student'} answer content from text file: {filepath}")
    
    # Parse the content
    sections = re.split(r'題號：(\d+[a-z]?(?:\s*\(續\)?)?)', content)
    
    # Process each section (skipping the first empty section if it exists)
    for i in range(1, len(sections), 2):
        full_q_number = sections[i].strip()
        answer_text = sections[i+1].strip()
        
        # Remove (續) from the question number for storage
        base_q_number = re.sub(r'\s*\(續\)\s*$', '', full_q_number)
        
        # Extract tables
        tables = []
        for table_match in re.finditer(r'<TABLE>\s*(.*?)\s*</TABLE>', answer_text, re.DOTALL):
            table_data = parse_table(table_match.group(1))
            if table_data:
                tables.append(table_data)
        answer_text = re.sub(r'<TABLE>\s*.*?\s*</TABLE>', '[TABLE]', answer_text, flags=re.DOTALL)
        
        # Extract figures
        figures = []
        for figure_match in re.finditer(r'<FIGURE>(.*?)</FIGURE>', answer_text):
            figures.append(figure_match.group(1).strip())
        answer_text = re.sub(r'<FIGURE>.*?</FIGURE>', '[FIGURE]', answer_text)
        
        if base_q_number in answers:
            # Append content for continuation questions
            answers[base_q_number]['text'] += '\n' + answer_text
            answers[base_q_number]['tables'].extend(tables)
            answers[base_q_number]['figures'].extend(figures)
        else:
            # Create new entry for first occurrence
            answers[base_q_number] = {
                'text': answer_text,
                'tables': tables,
                'figures': figures
            }
    
    return answers
