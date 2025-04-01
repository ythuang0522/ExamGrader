from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import json
import threading
from typing import Dict, Any
import logging
from dotenv import load_dotenv
from examgrader.grader import ExamGrader
from examgrader.api.openai import OpenAIAPI
from examgrader.api.gemini import GeminiAPI
from examgrader.utils.parsers import parse_questions, parse_answers
from examgrader.utils.jailbreak_detector import JailbreakDetector

# Get the directory containing this file and project root
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file in project root
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# Initialize Flask app with correct template and static folders
app = Flask(__name__,
           template_folder=os.path.join(current_dir, 'web/templates'),
           static_folder=os.path.join(current_dir, 'web/static'))

# Configure upload directory in the current directory
app.config['UPLOAD_FOLDER'] = os.path.join(current_dir, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max file size (increased for PDFs)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store grading progress
grading_progress = {
    'total_questions': 0,
    'graded_questions': 0,
    'current_status': '',
    'is_complete': False,
    'results': None,
    'jailbreak_check': {
        'status': None,  # 'pending', 'running', 'complete'
        'results': None,
        'has_jailbreak': False
    }
}

def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'json', 'pdf'}

def process_file(file, file_key):
    """Process uploaded file and return extracted data"""
    if not file or not allowed_file(file.filename):
        raise ValueError(f'Invalid file format for {file_key}')
        
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    try:
        if filename.lower().endswith('.json'):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        elif filename.lower().endswith('.pdf'):
            update_progress(f"Processing PDF file: {filename}...")
            
            # Get API keys
            gemini_api_key = os.getenv('GEMINI_API_KEY')
            openai_api_key = os.getenv('OPENAI_API_KEY')
            
            if not openai_api_key and not gemini_api_key:
                raise ValueError("Either OpenAI API key or Gemini API key must be provided in environment variables")
            
            # Process files based on type
            if file_key == 'questions':
                questions, _ = parse_questions(filepath, gemini_api_key, openai_api_key)
                return questions
            else:
                # For both correct_answers and student_answers
                is_correct_answer = (file_key == 'correct_answers')
                answers, _ = parse_answers(filepath, gemini_api_key, is_correct_answer=is_correct_answer)
                return answers
    finally:
        # Clean up
        if os.path.exists(filepath):
            os.remove(filepath)

def update_progress(status: str, questions_graded: int = None, total_questions: int = None):
    """Update the grading progress"""
    global grading_progress
    grading_progress['current_status'] = status
    if questions_graded is not None:
        grading_progress['graded_questions'] = questions_graded
    if total_questions is not None:
        grading_progress['total_questions'] = total_questions

def grade_exam_async(questions: Dict[str, Any], correct_answers: Dict[str, Any], 
                    student_answers: Dict[str, Any]):
    """Run grading process asynchronously"""
    global grading_progress
    
    try:
        update_progress("Initializing grader...", 0, len(questions))
        api_key = os.getenv('OPENAI_API_KEY')
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        logger.info(f"Loading API keys from environment: OpenAI {'Found' if api_key else 'Not found'}, Gemini {'Found' if gemini_api_key else 'Not found'}")
        if not api_key or not gemini_api_key:
            logger.error(f"Environment file path: {env_path}")
            raise ValueError("Both OpenAI API key and Gemini API key must be provided in environment variables")
            
        # Initialize APIs
        openai_api = OpenAIAPI(api_key=api_key)
        grader = ExamGrader(openai_api)
        
        # Check for jailbreak attempts
        update_progress("Checking for jailbreak attempts...")
        grading_progress['jailbreak_check']['status'] = 'running'
        
        detector = JailbreakDetector(gemini_api_key)
        jailbreak_results = detector.detect_jailbreaks(student_answers)
        grading_progress['jailbreak_check']['results'] = jailbreak_results
        grading_progress['jailbreak_check']['has_jailbreak'] = jailbreak_results.get("safety_status") == "UNSAFE"
        grading_progress['jailbreak_check']['status'] = 'complete'
        
        if grading_progress['jailbreak_check']['has_jailbreak']:
            logger.warning("⚠️ JAILBREAK ATTEMPTS DETECTED in student answers!")
            update_progress("Jailbreak detected. Assigning zero scores...")
            
            # Create results with zero scores
            results = {}
            valid_questions = [q_id for q_id in questions if q_id in correct_answers]
            max_possible = sum(int(questions[q_id]['score']) for q_id in valid_questions)
            
            for q_id in valid_questions:
                question = questions[q_id]
                correct_answer_text = correct_answers[q_id]['text']
                student_answer_text = student_answers.get(q_id, {}).get('text', "No student answer provided")
                
                results[q_id] = {
                    'question': question['text'],
                    'correct_answer': correct_answer_text,
                    'student_answer': student_answer_text,
                    'score': 0,
                    'max_score': int(question['score']),
                    'reason': 'Grading skipped due to jailbreak detection'
                }
            
            # Store results
            grading_progress['results'] = {
                'question_results': results,
                'total_score': 0,
                'max_possible': max_possible,
                'jailbreak_detected': True
            }
            update_progress("Grading complete (jailbreak detected)!", len(questions))
            grading_progress['is_complete'] = True
            return
        
        # Proceed with normal grading if no jailbreak detected
        def progress_callback(q_num):
            update_progress(f"Grading question {q_num}...", 
                          grading_progress['graded_questions'] + 1)
            
        update_progress("Starting grading process...")
        results, total_score, max_possible = grader.grade_exam(
            questions, correct_answers, student_answers
        )
        
        # Store results
        grading_progress['results'] = {
            'question_results': results,
            'total_score': total_score,
            'max_possible': max_possible,
            'jailbreak_detected': False
        }
        update_progress("Grading complete!", len(questions))
        grading_progress['is_complete'] = True
        
    except Exception as e:
        logger.error(f"Error during grading: {str(e)}")
        update_progress(f"Error: {str(e)}")
        grading_progress['is_complete'] = True

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads and start grading process"""
    global grading_progress
    
    # Reset progress
    grading_progress = {
        'total_questions': 0,
        'graded_questions': 0,
        'current_status': '',
        'is_complete': False,
        'results': None,
        'jailbreak_check': {
            'status': None,  # 'pending', 'running', 'complete'
            'results': None,
            'has_jailbreak': False
        }
    }
    
    try:
        # Check if all required files are present
        if not all(x in request.files for x in ['questions', 'correct_answers', 'student_answers']):
            return jsonify({'error': 'Missing required files'}), 400
            
        files = {}
        for file_key in ['questions', 'correct_answers', 'student_answers']:
            try:
                files[file_key] = process_file(request.files[file_key], file_key)
            except Exception as e:
                return jsonify({'error': f'Error processing {file_key}: {str(e)}'}), 400
        
        # Start grading process in background
        thread = threading.Thread(
            target=grade_exam_async,
            args=(files['questions'], files['correct_answers'], files['student_answers'])
        )
        thread.start()
        
        return jsonify({'message': 'Grading process started'})
        
    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/progress')
def get_progress():
    """Get current grading progress"""
    return jsonify(grading_progress)

@app.route('/check-jailbreak', methods=['POST'])
def check_jailbreak():
    """Handle jailbreak detection request"""
    global grading_progress
    
    try:
        # Check if student answers are present
        if 'student_answers' not in request.files:
            return jsonify({'error': 'Missing student answers file'}), 400
            
        # Process student answers
        student_answers = process_file(request.files['student_answers'], 'student_answers')
        
        # Get Gemini API key
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("Gemini API key not found in environment variables")
            
        # Initialize detector and run check
        detector = JailbreakDetector(gemini_api_key)
        results = detector.detect_jailbreaks(student_answers)
        
        return jsonify({
            'status': 'success',
            'results': results,
            'has_jailbreak': results.get("safety_status") == "UNSAFE"
        })
        
    except Exception as e:
        logger.error(f"Error during jailbreak detection: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 