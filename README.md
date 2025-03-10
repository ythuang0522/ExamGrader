# ExamGrader

ExamGrader is a Python application that uses AI to automatically extract questions and answers from PDF files and grade student answers against correct answers.

## Features

- Extract questions and answers from PDF files using Gemini API
- Parse question scores, tables, and figures
- Grade student answers against correct answers using OpenAI API
- Generate detailed grading reports with scores and reasons
- Save intermediate JSON files for parsed questions and answers

## Installation

Clone the repository and install dependencies:

```bash
git clone <repository-url>
cd ExamGrader
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root with your API keys:

```
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
```

## Usage

Run the application with the following command:

```bash
python run.py -q <questions_file> -c <correct_answers_file> -s <student_answers_file> [-o <output_file>] [--debug]
```

### Arguments

- `-q, --questions-file`: Path to the questions file (PDF or text)
- `-c, --correct-answers-file`: Path to the correct answers file (PDF or text)
- `-s, --student-answers-file`: Path to the student answers file (PDF or text)
- `-o, --output-file`: Optional: Path to save grading results (defaults to student_file_results.txt)
- `--gemini-api-key`: Gemini API key (overrides GEMINI_API_KEY in .env)
- `--openai-api-key`: OpenAI API key (overrides OPENAI_API_KEY in .env)
- `--debug`: Enable debug logging

## Project Structure

```
examgrader/
├── api/                   # API client modules
│   ├── gemini.py          # Gemini API client
│   └── openai.py          # OpenAI API client
├── extractors/            # PDF extraction modules
│   ├── base.py            # Base PDF extractor
│   ├── questions.py       # Question extractor
│   └── answers.py         # Answer extractor
├── utils/                 # Utility modules
│   ├── prompts.py         # AI prompt templates
│   └── parsers.py         # File parsing utilities
├── grader.py              # Exam grading logic
└── main.py                # CLI entry point
Data/                     # Directory for input/output data
```

## Dependencies

- openai>=0.28.0: OpenAI API client
- google-generativeai: Google's Gemini API client
- pillow: Image processing
- pymupdf: PDF processing
- tenacity: Retry mechanism for API calls
- python-dotenv: Environment variable management

## License

MIT 