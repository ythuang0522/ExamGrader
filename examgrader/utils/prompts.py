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
        1. Look for question numbers (題號) including:
           - Simple numbers (e.g., 4, 5)
           - Numbers with subproblem letters (e.g., 2a, 2b, 2c)
           - Numbers at the start of paragraphs or sections
           - If you see a lone subproblem letter (e.g., 'a', 'b', 'c') and the previous page had question N, 
             assume this is subproblem of question N (e.g., if previous page had question 5, then 'd' becomes '5d')
        2. Extract the complete text of the answer, including:
           - Text in any language (Chinese, English, etc.)
           - Mathematical formulas and equations, paying special attention to:
             * Exponents (use ^ symbol, e.g., 2^n, 2^(k+1))
             * Fractions (use LaTeX-style notation, e.g., n/(2^(k+1)))
             * Subscripts (use _, e.g., a_1)
             * Mathematical operators (×, ÷, ±, ≤, ≥, ≠, etc.)
             * Keep mathematical expressions in-line with text
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
        - For answer continuations:
          * If the page begins with text without any question number or subproblem letter,
            and you know the previous page ended with question N subproblem X, format it as:
            題號：NX（續）
            <continuing answer text>
          * For example, if the previous page ended with question 5c, format the continuation as:
            題號：5c（續）
          * ALWAYS capture text at the top of the page, even if it's just a few lines
          * IMPORTANT: If there is ANY text at the top of the page before a new question number appears,
            treat that text as a continuation from the previous question and subproblem
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
關於表格比較的特別說明：
- 表格的格式可能略有不同，但內容正確即可
- 表格中的數字可能會有小數點或千位符的差異，只要數值正確即可
- 表格單元格中的文字可能有空格或大小寫的差異，只要內容基本相同即可
- 重點在於表格傳達的信息是否正確，而非表格的確切格式
""" if has_tables else ""
        
        prompt = f"""
以下是題目與標準答案：
題目：{question_text}

標準答案：{correct_text}

學生答案：{student_text}
{table_instructions}
評分規則：
- 如果學生答案與標準答案重點上完全相同，給10分。
- 如果學生答案與標準答案重點上大部分相同，給8分。
- 如果學生答案與標準答案重點上少部分相同，給4分。
- 如果學生答案與標準答案重點上完全不同，給0分。
- 若此題答案有證明(如證明時間複雜度)，請先考量此題目是否可能有多種證明方式。若有多種證明方式，學生答案之證明過程無需與標準答案證明過程完全一致，針對學生答案證明之合理性給與適當分數。

請參考題目說明與標準答案，抓出答題重點，依據上述規則給出分數，並說明詳細理由，並以以下格式回應：
得分：<分數>
理由：<理由>
"""
        return prompt
