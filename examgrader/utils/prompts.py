"""Module containing prompt templates for AI interactions."""

from typing import Dict, Any

class PromptManager:
    """Manages prompts for different types of extractions and grading"""
    
    @staticmethod
    def get_answer_extraction_prompt() -> str:
        """Get prompt for extracting answers from pages"""
        return """Analyze this exam page which contains answers of one or multiple questions.
        IMPORTANT: Make sure to extract ALL text on the page, regardless of language or format.

        For EACH answer on the page:
        1. Look for question numbers (題號) on the left side of the page including:
           - Simple numbers (e.g., 4, 5)
           - Numbers with subproblem letters (e.g., 2a, 2b, 2c)
           - Numbers at the start of paragraphs or sections
        2. Extract the complete text of the answer for each question, including:
           - Text in any language (Chinese, English, etc.)
           - Mathematical formulas and equations, paying special attention to:
             * Exponents and fractions (use LaTeX-style notation, e.g., n/(2^(k+1)))
             * Subscripts (use _, e.g., a_1)
             * Mathematical operators (×, ÷, ±, ≤, ≥, ≠, etc.)
             * Never split equations across multiple lines
             * Never insert random spaces or newlines within equations
             * Keep all mathematical expressions inline with text
           - Technical explanations
           - Theoretical discussions
        3. If the answer contains a table:
           - Extract the table in markdown format
           - Format it as: <TABLE>
             | Header1 | Header2 | Header3 |
             |---------|---------|---------|
             | Data1   | Data2   | Data3   |
             </TABLE>
        4. If the answer contains a figure:
           - Describe the figure's contents as detailed as possible
           - Format it as: <FIGURE>figure description here</FIGURE>
        5. Format each answer as:
        題號：<number><letter if subproblem>
        <answer text including any table or figure markup>
        
        IMPORTANT GUIDELINES:
        - Pay special attention to any text at the top of the page without a question number or subproblem letter - this could be a continuation from previous page
        - Do not skip any question numbers or any text segments
        - Include complete explanations and technical details
        - Preserve the original language mix (Chinese/English) as it appears
        - Separate different answers with newlines
        - For subproblems:
          * If you see a lone letter (a, b, c, d) and previous answers were from question N,
            prefix it with N (e.g., 'd' becomes 'Nd')
          * Keep track of the main question number across pages
          * Ensure consistent subproblem labeling
        """
    
    @staticmethod
    def get_question_extraction_prompt() -> str:
        """Get prompt for extracting questions from pages"""
        return """Analyze this exam page and extract all questions including subproblems and their corresponding scores.
        For each question or subproblem:
        1. Identify the question number (題號) including subproblem letters (e.g., 2a, 2b)
        2. **Identify the score (配分)** which will appear after the question number or subproblem letter in parentheses. 
            e.g. 2. (10) Problem description here
            e.g., 2a (10) Subproblem description here
            e.g., (a) (10) Subproblem description here
        3. Extract the complete content of the question or subproblem without the score and % symbols. 
        4. When extracting mathematical formulas and equations:
           - Use LaTeX-style formatting
           - Keep equations on a single line without random newlines
           - Preserve all parentheses and brackets exactly as shown
           - Pay special attention to:
             * Recurrence relations (e.g., T(n) = 2T(n/4) + T(2n/3) + cn)
             * Summations (e.g., \sum_{i=1}^n x_i^2)
             * Fractions (e.g., n/2, a/b)
             * Exponents (e.g., 2^n, x^2)
             * Mathematical operators (×, ÷, ±, ≤, ≥, ≠)
             * Subscripts (e.g., a_1, x_i)
           - Never split equations across multiple lines
           - Never insert random spaces or newlines within equations
           - Keep all mathematical expressions inline with text
        5. If the question or subproblem contains a table:
           - Extract the table in markdown format
           - Format it as: <TABLE>
             | Header1 | Header2 | Header3 |
             |---------|---------|---------|
             | Data1   | Data2   | Data3   |
             </TABLE>
        6. If the question or subproblem contains a figure:
           - Describe the figure's contents as detailed as possible
           - Format it as: <FIGURE>figure description here</FIGURE>
        7. Format the output as:
        題號：<number><letter if subproblem>
        配分：<score>
        <content including any table or figure markup>"""

    @staticmethod
    def get_grading_prompt(question_data: Dict[str, Any], correct_ans: Dict[str, Any], student_ans: Dict[str, Any]) -> str:
        """Get prompt for grading an answer
        
        Args:
            question_data: Dictionary with question information
            correct_ans: Dictionary with correct answer information
            student_ans: Dictionary with student answer information
            
        Returns:
            Formatted grading prompt
        """
        # Format the question text with any tables or figures
        question_text = question_data['text']
        for table in question_data.get('tables', []):
            # If table is a string, use it directly; otherwise use to_markdown()
            table_md = table if isinstance(table, str) else table.to_markdown()
            question_text = question_text.replace('[TABLE]', table_md, 1)
        for figure in question_data.get('figures', []):
            question_text = question_text.replace('[FIGURE]', f"[Figure: {figure}]", 1)
            
        # Format the correct answer text with any tables or figures
        correct_text = correct_ans['text']
        for table in correct_ans.get('tables', []):
            # If table is a string, use it directly; otherwise use to_markdown()
            table_md = table if isinstance(table, str) else table.to_markdown()
            correct_text = correct_text.replace('[TABLE]', table_md, 1)
        for figure in correct_ans.get('figures', []):
            correct_text = correct_text.replace('[FIGURE]', f"[Figure: {figure}]", 1)
            
        # Format the student answer text with any tables or figures
        student_text = student_ans['text']
        for table in student_ans.get('tables', []):
            # If table is a string, use it directly; otherwise use to_markdown()
            table_md = table if isinstance(table, str) else table.to_markdown()
            student_text = student_text.replace('[TABLE]', table_md, 1)
        for figure in student_ans.get('figures', []):
            student_text = student_text.replace('[FIGURE]', f"[Figure: {figure}]", 1)
        
        has_tables = (
            len(correct_ans.get('tables', [])) > 0 or 
            len(student_ans.get('tables', [])) > 0
        )
        
        table_instructions = """
**表格評分的特別說明**
- 學生答案表格格式和參考答案表格格式通常不同，只要內容基本相同即可
- 重點在於學生答案的表格要傳達的信息，是否和參考答案的表格要傳達的信息一樣，而非表格的格式
""" if has_tables else ""

        # Get the rubric for this question
        rubric = question_data.get('rubric', '')
        if not rubric or rubric.startswith('Failed to generate rubric'):
            # If no rubric is available, raise an error
            raise ValueError("No rubric available for grading. A rubric is required for grading.")
        
        scoring_rules = f"""**Rubric評分標準**
{rubric}

**注意事項**
- 根據以上Rubric評分標準給分，總分為{question_data['score']}分
- 可以給予部分分數，但不能超過各項Rubric評分標準的分數上限
- 若學生的答案和參考答案不同但合理，可獨立根據其方法的正確性和完整性評分
- 簡短說明每一個Rubric評分項目的評分理由，無得分也請說明"""
        
        prompt = f"""
以下是題目與參考答案：
**題目** 
{question_text}

**參考答案**
{correct_text}

**學生答案**
{student_text}

{table_instructions}

{scoring_rules}

請根據以上題目，參考答案，和Rubric評分標準評分，以下面格式回應：
得分：<分數>
理由：<請簡短說明每一個Rubric評分項目的評分理由>
"""
        return prompt

    @staticmethod
    def get_rubric_generation_prompt(question_text: str, tables: list, figures: list, score: int) -> str:
        """Get prompt for generating a rubric for a question
        
        Args:
            question_text: The text of the question
            tables: List of tables in the question
            figures: List of figures in the question
            score: The total score for the question
            
        Returns:
            Formatted rubric generation prompt
        """
        # Format the question text with any tables or figures
        formatted_question = question_text
        for table in tables:
            # If table is a string, use it directly; otherwise use to_markdown()
            table_md = table if isinstance(table, str) else table.to_markdown()
            formatted_question = formatted_question.replace('[TABLE]', table_md, 1)
        for figure in figures:
            formatted_question = formatted_question.replace('[FIGURE]', f"[Figure: {figure}]", 1)
            
        return f"""Create a detailed grading rubric for the following exam question worth {score} points.
        
Question:
{formatted_question}

Your task is to create a clear, fair, and comprehensive rubric that:
1. Breaks down the total {score} points into specific scoring criteria
2. Allocates points to different aspects of the expected answer
3. Provides clear guidelines for what constitutes full, partial, or no credit
4. Focuses on the key concepts and skills being tested on the question

Format the rubric as a list of criteria with point allocations in markdown format. But no more than 3 criteria. For example:
- Correct identification of X (3 pts)
- Proper explanation of Y (4 pts)
- Complete implementation of Z (3 pts)

只需用繁體中文輸出rubric評分規格, 不要輸出其他文字.
"""
