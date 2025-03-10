# ExamGrader

ExamGrader is a Python application that uses AI to automatically extract questions and answers from PDF files and grade student answers against correct answers.

## Features

- Extract questions and answers from PDF files using Gemini API
- Parse question scores, tables, and figures
- Grade student answers against correct answers using OpenAI API
- Automatically generate detailed grading rubrics for each question
- Support parallel processing for faster grading and rubric generation
- Generate detailed grading reports with scores, rubrics, and reasons
- Save intermediate JSON files for parsed questions and answers
- Support for loading pre-parsed JSON files to skip extraction step
- Robust error handling and retry mechanisms for API calls

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
python run.py -q <questions_file> -c <correct_answers_file> -s <student_answers_file> [-o <output_file>] [--workers N] [--force-rubrics] [--debug]
```

The application supports both raw input files (PDF) and pre-parsed JSON files. When using JSON files, the extraction and parsing steps are skipped, making the process faster. JSON files are automatically detected by their `.json` extension.

### Arguments

- `-q, --questions-file`: Path to the questions file (PDF or JSON)
- `-c, --correct-answers-file`: Path to the correct answers file (PDF or JSON)
- `-s, --student-answers-file`: Path to the student answers file (PDF or JSON)
- `-o, --output-file`: Optional: Path to save grading results (defaults to student_file_results.txt)
- `--workers`: Optional: Number of worker threads for parallel processing (default: 8)
- `--force-rubrics`: Optional: Force regeneration of rubrics even if they already exist
- `--gemini-api-key`: Gemini API key (overrides GEMINI_API_KEY in .env)
- `--openai-api-key`: OpenAI API key (overrides OPENAI_API_KEY in .env)
- `--debug`: Enable debug logging

### Input File Types

The application accepts two types of input files:
1. **PDF Files**: Requires Gemini API key for extraction
2. **JSON Files**: Pre-parsed files from previous runs (fastest option)

When using JSON files, they must be in the format produced by the application's save_intermediate_json function. This is useful for:
- Rerunning grading with different parameters without re-extracting content
- Testing and debugging without API calls
- Manually reviewing and adjusting parsed content

### Rubric Generation

The application now automatically generates detailed grading rubrics for each question using OpenAI API. The rubrics:
- Break down the total points into specific scoring criteria
- Provide clear guidelines for full, partial, and no credit
- Focus on key concepts and skills being tested
- Are saved with the questions in the intermediate JSON files

You can force regeneration of rubrics using the `--force-rubrics` flag, which is useful when:
- You want to improve existing rubrics
- The question content has been updated
- Previous rubric generation failed

## Project Structure

```
examgrader/
├── api/                   # API client modules
│   ├── gemini.py          # Gemini API client
│   └── openai.py          # OpenAI API client with retry logic
├── extractors/            # PDF extraction modules
│   ├── base.py            # Base PDF extractor
│   ├── questions.py       # Question extractor
│   └── answers.py         # Answer extractor
├── utils/                 # Utility modules
│   ├── prompts.py         # AI prompt templates
│   ├── parsers.py         # File parsing utilities with OOP design
│   └── file_utils.py      # File operation utilities
├── grader.py              # Exam grading logic with rubric support
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