# ExamGrader

ExamGrader is a Python application that uses AI to automatically extract questions and answers from PDF files and grade student answers against correct answers.

## Features

- Extract questions and answers from PDF files using Gemini API
- Parse question scores, tables, and figures
- Grade student answers against correct answers using OpenAI API
- Automatically generate detailed grading rubrics for each question
- Generate detailed grading reports with scores, rubrics, and reasons
- Support for multiple grading rounds to ensure fairness
- Batch processing of multiple student answer files
- Web interface for easy file upload and grading management

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

### Command Line Interface

Run the application with the following command:

```bash
python run.py -q <questions_file> -c <correct_answers_file> -s <student_answers_file> [-o <output_file>] [-r <rounds>] [--workers N] [--debug]
```

### Web Interface

Start the web interface with:

```bash
python run.py --web [--host HOST] [--port PORT]
```

By default, the web interface runs at http://127.0.0.1:5000. You can specify a different host and port using the optional arguments.

The application supports both raw input files (PDF) and pre-parsed JSON files. When using JSON files, the extraction and parsing steps are skipped, making the process faster. JSON files are automatically detected by their `.json` extension.

### Arguments

- `-q, --questions-file`: Path to the questions file (PDF or JSON)
- `-c, --correct-answers-file`: Path to the correct answers file (PDF or JSON)
- `-s, --student-answers-file`: Path to student answers file or directory containing multiple PDF files
- `-o, --output-file`: Optional: Path to save grading results (defaults to student_file_results.txt)
- `-r, --rounds`: Optional: Number of grading rounds to run (default: 1)
- `--workers`: Optional: Number of worker threads for parallel processing (default: 8)
- `--gemini-api-key`: Gemini API key (overrides GEMINI_API_KEY in .env)
- `--openai-api-key`: OpenAI API key (overrides OPENAI_API_KEY in .env)
- `--debug`: Enable debug logging

### Multiple Grading Rounds

The application supports running multiple grading rounds for each student's answers to ensure fairness and accuracy. When using multiple rounds:
- Each round generates a separate result file
- The system keeps track of the best score across all rounds
- Final results are based on the round that achieved the highest score
- Useful for handling variations in AI model responses

To use multiple rounds:
```bash
python run.py -q questions.pdf -c answers.pdf -s student.pdf -r 3
```

### Batch Processing

You can process multiple student answer files at once by providing a directory:
```bash
python run.py -q questions.pdf -c answers.pdf -s student_answers_directory/
```

The system will:
- Process all PDF files in the specified directory
- Generate separate result files for each student
- Support multiple rounds per student if specified

### Input File Types

The application accepts two types of input files:
1. **PDF Files**: Requires Gemini API key for extraction. When processing PDF files, the system will automatically generate rubrics for all questions.
2. **JSON Files**: Pre-parsed files from previous runs (fastest option). When using JSON files, existing rubrics are preserved.

When using JSON files, they must be in the format produced by the application's save_intermediate_json function. This is useful for:
- Rerunning grading with different parameters without re-extracting content
- Testing and debugging without API calls
- Manually reviewing and adjusting parsed content

### Rubric Generation

The application automatically generates detailed grading rubrics for each question when processing PDF files using OpenAI API. The rubrics:
- Break down the total points into specific scoring criteria
- Provide clear guidelines for full, partial, and no credit
- Focus on key concepts and skills being tested
- Are saved with the questions in the intermediate JSON files

When loading questions from a JSON file, the system will use the existing rubrics stored in the file. This allows you to:
- Preserve carefully crafted rubrics across multiple grading sessions
- Manually adjust rubrics if needed
- Save time by reusing previously generated rubrics

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
- flask>=2.0.0: Web framework for the interface
- flask-uploads: File upload handling
- tqdm: Progress bar for long-running operations
- werkzeug: WSGI utilities for Flask

## License

MIT 

## Contact

Yao-Ting Hunag (ythuang at ccu.edu.tw)