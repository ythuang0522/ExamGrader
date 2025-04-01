"""Module for parsing exam data from various sources."""

import re
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from abc import ABC, abstractmethod

from examgrader.api.gemini import GeminiAPI
from examgrader.extractors.questions import QuestionExtractor
from examgrader.extractors.answers import AnswerExtractor
from examgrader.utils.file_utils import save_intermediate_json

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

class BaseParser(ABC):
    """Base class for exam content parsers."""
    
    def __init__(self, filepath: str, gemini_api_key: Optional[str] = None):
        self.filepath = filepath
        self.gemini_api_key = gemini_api_key
        
    def parse(self) -> Tuple[Dict[str, Dict[str, Any]], str]:
        """Main parsing method that handles both JSON and PDF files."""
        content_dict = {}
        
        # Load from JSON if applicable
        if self.filepath.lower().endswith('.json'):
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content_dict = json.load(f)
                logger.info(f"Loaded pre-parsed content from JSON file: {self.filepath}")
                return content_dict, self.filepath
                
        # Handle PDF files
        if self.filepath.lower().endswith('.pdf'):
            if not self.gemini_api_key:
                raise ValueError("Gemini API key required for PDF processing")
            
            content = self._extract_content()
            content_dict = self._parse_content(content)
            json_path = self._save_results(content_dict)
            return content_dict, json_path
            
        raise ValueError(f"Unsupported file format. File must be either PDF or JSON: {self.filepath}")
    
    @abstractmethod
    def _extract_content(self) -> str:
        """Extract content from PDF using appropriate extractor."""
        pass
        
    def _parse_content(self, content: str) -> Dict[str, Dict[str, Any]]:
        """Parse extracted content into structured format."""
        result = {}
        sections = re.split(r'題號：(\d+[a-z]?(?:\s*\(續\)?)?)', content)
        
        for i in range(1, len(sections), 2):
            full_q_number = sections[i].strip()
            section_content = sections[i+1].strip()
            
            # Remove (續) from the question number for storage
            base_q_number = re.sub(r'\s*\(續\)\s*$', '', full_q_number)
            
            # Process section content
            processed_content = self._process_section(base_q_number, full_q_number, section_content)
            
            if base_q_number in result:
                # Append content for continuation questions
                self._merge_continuation(result[base_q_number], processed_content)
            else:
                # Create new entry
                result[base_q_number] = processed_content
                
        return result
    
    def _process_section(self, base_q_number: str, full_q_number: str, content: str) -> Dict[str, Any]:
        """Process individual section content. Override in subclasses."""
        # Extract tables
        tables = []
        processed_content = content
        for table_match in re.finditer(r'<TABLE>\s*(.*?)\s*</TABLE>', content, re.DOTALL):
            table_data = parse_table(table_match.group(1))
            if table_data:
                tables.append(table_data)
        processed_content = re.sub(r'<TABLE>\s*.*?\s*</TABLE>', '[TABLE]', processed_content, flags=re.DOTALL)
        
        # Extract figures
        figures = []
        for figure_match in re.finditer(r'<FIGURE>(.*?)</FIGURE>', processed_content):
            figures.append(figure_match.group(1).strip())
        processed_content = re.sub(r'<FIGURE>.*?</FIGURE>', '[FIGURE]', processed_content)
        
        return {
            'text': processed_content.strip(),
            'tables': tables,
            'figures': figures
        }
    
    def _merge_continuation(self, existing: Dict[str, Any], new: Dict[str, Any]):
        """Merge continuation content with existing content."""
        existing['text'] += '\n' + new['text']
        existing['tables'].extend(new['tables'])
        existing['figures'].extend(new['figures'])
    
    @abstractmethod
    def _save_results(self, content: Dict[str, Dict[str, Any]]) -> str:
        """Save parsed results to JSON file."""
        pass

class RubricGenerator:
    """Class for generating rubrics using OpenAI API."""
    
    def __init__(self, openai_api_key: str, max_workers: int = 5):
        self.openai_api_key = openai_api_key
        self.max_workers = max_workers
        
    def generate_rubrics(self, questions: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Generate rubrics for questions using OpenAI API."""
        from examgrader.api.openai import OpenAIAPI
        from examgrader.utils.prompts import PromptManager
        
        logger.info(f"Generating rubrics for {len(questions)} questions using OpenAI API with {self.max_workers} worker threads...")
        openai_api = OpenAIAPI(self.openai_api_key)
        
        # Generate rubrics in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_question = {
                executor.submit(self._generate_single_rubric, openai_api, q_num, q_data): q_num 
                for q_num, q_data in questions.items()
            }
            
            self._process_rubric_results(questions, future_to_question)
            
        return questions
    
    def _generate_single_rubric(self, openai_api, q_num: str, q_data: Dict[str, Any]) -> Tuple[str, str]:
        """Generate rubric for a single question."""
        from examgrader.utils.prompts import PromptManager
        
        prompt = PromptManager.get_rubric_generation_prompt(
            q_data['text'], 
            q_data['tables'], 
            q_data['figures'], 
            q_data['score']
        )
        
        rubric = openai_api.generate_rubric(prompt)
        logger.info(f"Generated rubric for question {q_num}")
        return q_num, rubric
    
    def _process_rubric_results(self, questions: Dict[str, Dict[str, Any]], future_to_question: Dict):
        """Process results from parallel rubric generation."""
        total_questions = len(future_to_question)
        completed = 0
        start_time = time.time()
        
        logger.info(f"Started parallel rubric generation for {total_questions} questions")
        
        for future in as_completed(future_to_question):
            q_num = future_to_question[future]
            try:
                result_q_num, rubric = future.result()
                questions[result_q_num]['rubric'] = rubric
                completed += 1
                
                self._log_progress(completed, total_questions, start_time)
                    
            except Exception as exc:
                logger.error(f"Question {q_num} generated an exception: {exc}")
                questions[q_num]['rubric'] = f"Failed to generate rubric: {str(exc)}"
                completed += 1
        
        total_time = time.time() - start_time
        logger.info(f"Completed rubric generation for {total_questions} questions in {total_time:.2f} seconds")
    
    def _log_progress(self, completed: int, total: int, start_time: float):
        """Log progress of rubric generation."""
        elapsed = time.time() - start_time
        progress = completed / total
        if completed > 1:  # Avoid division by zero
            estimated_total = elapsed / progress
            remaining = estimated_total - elapsed
            logger.info(f"Progress: {completed}/{total} ({progress:.1%}) - ETA: {remaining:.1f}s")
        else:
            logger.info(f"Progress: {completed}/{total}")

class QuestionParser(BaseParser):
    """Parser for exam questions."""
    
    def __init__(self, filepath: str, gemini_api_key: Optional[str] = None, 
                 openai_api_key: Optional[str] = None, max_workers: int = 5):
        super().__init__(filepath, gemini_api_key)
        self.openai_api_key = openai_api_key
        self.max_workers = max_workers
    
    def _extract_content(self) -> str:
        """Extract content using QuestionExtractor."""
        gemini_api = GeminiAPI(self.gemini_api_key)
        extractor = QuestionExtractor(self.filepath, gemini_api)
        content = extractor.extract()
        logger.info("Extracted question content from PDF")
        return content
    
    def _process_section(self, base_q_number: str, full_q_number: str, content: str) -> Dict[str, Any]:
        """Process question section including score extraction."""
        # Extract score (only for non-continuation questions)
        score = "0"
        if '(續)' not in full_q_number:
            score_match = re.search(r'配分：(\d+)', content)
            score = score_match.group(1) if score_match else "0"
        
        # Remove the score line and process the rest
        content = re.sub(r'配分：\d+\n?', '', content)
        result = super()._process_section(base_q_number, full_q_number, content)
        result['score'] = score
        return result
    
    def _save_results(self, content: Dict[str, Dict[str, Any]]) -> str:
        """Save questions and generate rubrics for PDF files."""
        # Save initial results
        json_path = save_intermediate_json(content, self.filepath, '_questions')
        logger.info(f"Saved parsed questions to {json_path}")
        
        # Generate rubrics if this is a PDF file and OpenAI API key is provided
        if self.filepath.lower().endswith('.pdf') and self.openai_api_key:
            rubric_generator = RubricGenerator(self.openai_api_key, self.max_workers)
            content = rubric_generator.generate_rubrics(content)
            
            # Save updated questions with rubrics
            json_path = save_intermediate_json(content, self.filepath, '_questions_with_rubrics')
            logger.info(f"Saved questions with rubrics to {json_path}")
        
        return json_path

class AnswerParser(BaseParser):
    """Parser for answer files."""
    
    def __init__(self, filepath: str, gemini_api_key: Optional[str] = None, is_correct_answer: bool = True, questions_dict=None):
        super().__init__(filepath, gemini_api_key)
        self.is_correct_answer = is_correct_answer
        self.questions_dict = questions_dict
    
    def _extract_content(self) -> str:
        """Extract content using AnswerExtractor."""
        gemini_api = GeminiAPI(self.gemini_api_key)
        extractor = AnswerExtractor(self.filepath, gemini_api, self.questions_dict)
        content = extractor.extract()
        logger.info("Extracted answer content from PDF")
        return content
    
    def _save_results(self, content: Dict[str, Dict[str, Any]]) -> str:
        """Save parsed answers results to JSON file."""
        type_label = "_correct" if self.is_correct_answer else "_student"
        return save_intermediate_json(content, self.filepath, f"{type_label}_answers")

def parse_questions(filepath: str, gemini_api_key: Optional[str] = None, openai_api_key: Optional[str] = None, 
                   max_workers: int = 5) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """Parse questions from file and generate rubrics if PDF is provided."""
    parser = QuestionParser(filepath, gemini_api_key, openai_api_key, max_workers)
    questions, json_path = parser.parse()        
    return questions, json_path

def parse_answers(filepath: str, gemini_api_key: Optional[str] = None, is_correct_answer: bool = True, 
                 questions_dict=None) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """Parse answers from file."""
    parser = AnswerParser(filepath, gemini_api_key, is_correct_answer, questions_dict)
    answers, json_path = parser.parse()
    return answers, json_path
