# ExamGrader

ExamGrader is a Python application that uses generative AI to automatically extract handwritten questions and answers from PDF files and grade student answers against reference answers and question-associated rubrics using generative AI.

## Features

- Extract handwritten answers for multiple questions and subproblems in a single file
- Parse question scores, tables, and figures in the question and answer files
- Generate detailed grading reports with scores and reasons according to question-associated rubrics
- Built-in jailbreak detection to identify potential AI prompt attacks in student answers
- Automatic partitioning of multi-student answers into individual files for batch processing

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

## Command Line Usage

Run the application with the following command:

```bash
python run.py -q <questions_file> -c <correct_answers_file> -s <student_answers_file> [-o <output_file>] [-r <rounds>] [--workers N] [--debug]
```

### Input Files

The application accepts questions, reference answers, and student's answers as input, which can be PDF or JSON. The exam questions should be numbered 1, 2, 3, and each question can have subparts labeled (a), (b), (c). For example: 1, 2, 3(a), 3(b), 4a, 4b, ...

Example files:
- Questions: [Homework1_2025.pdf](Data/Homework1_2025.pdf)
- Student or reference answers (single studnet): [411000001_範例.pdf](Data/411000001_範例.pdf)

1. **PDF Files**: When processing answer PDF files, the app will automatically extract and parition answers into questions and subproblems (e.g., 1, 2, 3a, 3b, ...). The app will additionally generate rubrics for each question in the ```-q questions_file```. 
2. **JSON Files**: Pre-parsed, intermediate files produced by the app from previous runs. When using JSON files, existing, questions, rubrics and answers are directly extracted. This is useful for:
- Manually reviewing and adjusting parsed content (e.g., rubrics)
- Consistent grading without re-extracting and parsing content

### Output Files

The application generates several types of output files during the grading process:

1. **Grading Results (`.txt`)**
   - Default filename: `{student_filename}_results.txt` (e.g., [411000001_範例_results.txt](Data/411000001_範例_results.txt))
   - Contains detailed grading report including:
     - Total score and maximum possible score
     - Per-question breakdown with:
       - Question text
       - Grading rubric (if available)
       - Student's answer
       - Correct answer
       - Score and explanation

2. **Intermediate JSON Files**
   - Generated during PDF processing:
     - `{filename}_questions_with_rubrics.json`: Questions with AI-generated rubrics (e.g., [Homework1_2025_questions_rubrics.json](Data/Homework1_2025_questions_with_rubrics.json))
     - `{filename}_correct_answers.json`: Extracted correct answers
     - `{filename}_student_answers.json`: Extracted student answers (e.g., [411000001_範例_student_answers.json](Data/411000001_範例_student_answers.json))

### Supported Input Files for Student Answers

The application supports three types of student answer inputs:

1. **Single Student PDF**
   - A PDF file containing answers from a single student
   - Processed directly without any splitting
   - Example: `python run.py -q questions.pdf -c answers.pdf -s student1.pdf`

2. **Directory of Student PDFs**
   - A directory containing multiple PDF files, one for each student
   - All PDFs in the directory are processed in batch
   - Example: `python run.py -q questions.pdf -c answers.pdf -s student_answers/`

3. **Multi-Student PDF**
   - A single PDF file containing answers from multiple students, assuming the starting page of each student will contain student ID (e.g., 411110001) and student name (e.g., 黃耀廷) at the top-left corner.
   - Automatically split into individual student PDFs using the `-m` flag
   - Example: `python run.py -q questions.pdf -c answers.pdf -s all_students.pdf -m`
   - The system will:
     - Split the PDF into individual student files
     - Create a new directory with the split files
     - Process each student's answers separately
     - Generate individual grading reports for each student

### Rubric Generation and Management

The application automatically generates detailed grading rubrics for each question when processing PDF files using OpenAI API. The rubrics:
- Break down the total points into specific scoring criteria
- Provide clear guidelines for full, partial, and no credit
- Focus on key concepts and skills being tested
- Are saved with the questions in the intermediate JSON files

We recommend to generate the rubtics only once, revise them if necessary, and load the revised rubrics (```-q questions_file```) for grading. This allows you to:
- Preserve carefully crafted rubrics across multiple grading sessions
- Manually adjust rubrics if needed

### Multiple Grading Rounds

The application supports running multiple grading rounds when grading each student's answers to compensate the randomness nature of LLM:
- Each round generates a separate result file
- The system keeps track of the best score across all rounds
- Final results are based on the round that achieved the highest score
- Useful for handling variations in AI model responses

To use three rounds of grading:
```bash
python run.py -q questions.pdf -c answers.pdf -s student.pdf -r 3
```

### Arguments

- `-q, --questions-file`: Path to the questions file (PDF or JSON)
- `-c, --correct-answers-file`: Path to the correct answers file (PDF or JSON)
- `-s, --student-answers-file`: Path to student answers file or directory containing multiple PDF files
- `-o, --output-file`: Optional: Path to save grading results (defaults to student_file_results.txt)
- `-r, --rounds`: Optional: Number of grading rounds to run (default: 1)
- `--workers`: Optional: Number of worker threads for parallel processing (default: 12)
- `--gemini-api-key`: Gemini API key (overrides GEMINI_API_KEY in .env)
- `--openai-api-key`: OpenAI API key (overrides OPENAI_API_KEY in .env)
- `--debug`: Enable debug logging
- `--disable-jailbreak-check`: Optional: Disable jailbreak detection (enabled by default)
- `-m, --split-multi-student-pdf`: Optional: Split a multi-student PDF into individual files
- `--gemini-model`: Optional: Gemini model to use (default: gemini-2.5-pro-exp-03-25)


## Web Interface

Start the web interface with:

```bash
python run.py --web [--host HOST] [--port PORT]
```

By default, the web interface runs at http://127.0.0.1:5000. You can specify a different host and port using the optional arguments.

The application supports both raw input files (PDF) and pre-parsed JSON files. When using JSON files, the extraction and parsing steps are skipped, making the process faster. JSON files are automatically detected by their `.json` extension.

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
│   ├── jailbreak_detector.py # Jailbreak detection module
│   ├── pdf_partitioner.py # Multi-student PDF partitioning module
│   └── file_utils.py      # File operation utilities
├── web/                   # Web application components
│   ├── templates/         # HTML templates for web interface
│   │   ├── base.html      # Base template with common layout
│   │   └── index.html     # Main upload and results page
│   └── static/            # Static assets (CSS, JS, images)
│       ├── css/           # Stylesheet files
│       └── js/            # JavaScript files
├── uploads/               # Temporary storage for uploaded files
├── grader.py              # Exam grading logic with rubric support
├── web.py                 # Web application implementation
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