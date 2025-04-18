"""Module for partitioning multi-student PDFs into individual files."""

import logging
import io
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from PIL import Image

import fitz  # PyMuPDF
from examgrader.utils.prompts import PromptManager
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

def analyze_multi_student_pdf(pdf_path: Path, gemini_api, max_workers: int = 4) -> List[Dict]:
    """
    Analyze PDF with Gemini Vision to identify student sections.
    
    Args:
        pdf_path: Path to multi-student PDF
        gemini_api: Initialized Gemini API client
        max_workers: Maximum number of worker threads for parallel processing (default: 4)
    
    Returns:
        List of dicts: [
            {'student_id': 'S12345', 'name': 'John Doe', 'start_page': 0},
            {'student_id': 'S67890', 'name': 'Jane Smith', 'start_page': 4},
            ...
        ]
    """
    # 1. Open PDF with PyMuPDF
    doc = fitz.open(pdf_path)
    
    # 2. Render pages as images for Gemini Vision API
    image_data_list = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Scale factor for better resolution
        image_bytes = pix.tobytes("png")
        image_data_list.append({
            "image_bytes": image_bytes, 
            "page_num": page_num
        })
        
    # 3. Process pages in parallel using a thread pool
    # Using a dictionary with page numbers as keys to avoid synchronization issues
    results_by_page = {}
    
    def process_page(page_data):
        page_num = page_data["page_num"]
        result = analyze_pdf_page(page_data, gemini_api, pdf_path)
        
        # Store result in the dictionary - thread-safe since each thread processes a different page
        if result:
            results_by_page[page_num] = result[0]  # Each page has at most one student record
            logger.info(f"Found student info on page {page_num}: {result}")
        
        return result
    
    # Determine appropriate number of worker threads based on input and PDF size
    actual_workers = min(max_workers, len(image_data_list))
    logger.info(f"Processing PDF pages with {actual_workers} parallel threads")
    
    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        # Process all pages in parallel
        list(executor.map(process_page, image_data_list))
    
    # 4. Organize results into a list
    student_records = list(results_by_page.values())
    
    sorted_student_records = sorted(student_records, key=lambda x: x['start_page'])
    logger.debug(f"Student records sorted by page number: {sorted_student_records}")

    # Format student records in a tabular form
    table_header = "Student ID    | Name          | Start Page"
    table_separator = "-" * 40
    table_rows = [table_header, table_separator]
    for record in sorted_student_records:
        table_rows.append(f"{record['student_id']:<12} | {record['name']:<12} | {record['start_page']}")
    logger.debug("Student records sorted by page number:\n" + "\n".join(table_rows))

    # 5. Deduplicate and keep earliest occurrence of each student
    # This part is already thread-safe since it happens after all threads are done
    unique_records = {}
    for record in student_records:
        student_id = record.get('student_id')
        # We don't need to check if student_id exists since we filtered that in results_by_page
        if student_id not in unique_records or record['start_page'] < unique_records[student_id]['start_page']:
            unique_records[student_id] = record
            logger.debug(f"Updated record for student {student_id} with start page {record['start_page']}")
    
    # 6. Sort records by start_page
    sorted_records = sorted(unique_records.values(), key=lambda x: x['start_page'])
    
    logger.info(f"Identified {len(sorted_records)} student sections in the PDF")
    return sorted_records


def analyze_pdf_page(page_data: Dict, gemini_api, pdf_path: Path) -> List[Dict]:
    """
    Send a single PDF page image to Gemini for analysis using the existing generate_content method.
    
    Args:
        page_data: Dict with page image bytes and page number
        gemini_api: Initialized Gemini API
        pdf_path: Path to the PDF file being analyzed
        
    Returns:
        List of student records found in this page
    """
    try:
        image_bytes = page_data["image_bytes"]
        page_num = page_data["page_num"]
        
        # Convert bytes to PIL Image for Gemini API
        img = Image.open(io.BytesIO(image_bytes))
        
        # Define how much to crop (in pixels)
        crop_width = 500    # pixels from left
        crop_height = 100   # pixels from top
        
        # Crop top-left corner where student ID and name typically appear
        cropped_img = img.crop((0, 0, crop_width, crop_height))  # (left, top, right, bottom)
        
        logger.debug(f"Cropped page {page_num} image from {img.size} to {cropped_img.size}")
        
        # Save cropped image for debugging if in debug mode
        if logger.getEffectiveLevel() <= logging.DEBUG:
            # Create debug directory relative to the pdf path
            debug_dir = pdf_path.with_name(f"debug_cropped_images_{pdf_path.stem}")
            debug_dir.mkdir(exist_ok=True, parents=True)
            debug_path = debug_dir / f"page_{page_num}_crop.png"
            cropped_img.save(debug_path)
            logger.debug(f"Saved cropped image for page {page_num} to {debug_path}")
                
        # Get response from Gemini using the existing generate_content method with cropped image
        response_text = gemini_api.generate_content(PromptManager.get_student_id_extraction_prompt(), cropped_img, thinking_budget=0)
        
        if not response_text:
            logger.warning(f"Empty response from Gemini for page {page_num}")
            return []
        
        # Extract student ID and name using simple text parsing
        student_id_match = re.search(r'Student ID:\s*([^\n]+)', response_text)
        name_match = re.search(r'Name:\s*([^\n]+)', response_text)
        
        if student_id_match and name_match:
            student_id = student_id_match.group(1).strip()
            name = name_match.group(1).strip()
            
            # Only include records with valid student IDs and names
            if student_id and name and student_id.lower() not in ['not found', 'n/a', 'none', 'unknown'] and name.lower() not in ['not found', 'n/a', 'none', 'unknown']:
                return [{
                    'student_id': student_id,
                    'name': name,
                    'start_page': page_num
                }]
            else:
                # This page doesn't have a valid student ID - this is expected for pages after the first page of each student
                logger.debug(f"No valid student ID/name found on page {page_num} - this may be a continuation page")
        else:
            # This page doesn't match the pattern - this is expected for pages after the first page of each student
            logger.debug(f"No student ID/name pattern found on page {page_num} - this may be a continuation page")
        
        return []
        
    except Exception as e:
        logger.error(f"Error analyzing PDF page {page_data.get('page_num')}: {str(e)}")
        return []


def create_student_page_mapping(student_records: List[Dict], total_pages: int) -> Dict[str, Tuple[int, int]]:
    """
    Create mapping of student IDs to page ranges.
    
    Args:
        student_records: List of student records from analyze_multi_student_pdf
        total_pages: Total number of pages in PDF
    
    Returns:
        Dict mapping student IDs to page ranges: {
            'S12345': (0, 3),  # pages 0-3 (inclusive)
            'S67890': (4, 8),  # pages 4-8 (inclusive)
            ...
        }
    """
    # 1. Sort student records by start_page
    sorted_records = sorted(student_records, key=lambda x: x['start_page'])
    
    # 2. Calculate page ranges for each student
    student_mappings = {}
    for i, record in enumerate(sorted_records):
        student_id = record['student_id']
        start_page = record['start_page']
        
        # End page is either the start page of the next student - 1, or the last page
        # Example: If we have students starting on pages [1, 5, 9] in a 12-page PDF:
        # - First student (1): end_page = 5 - 1 = 4 (pages 1-4)
        # - Second student (5): end_page = 9 - 1 = 8 (pages 5-8)
        # - Last student (9): end_page = 12 - 1 = 11 (pages 9-11)
        if i < len(sorted_records) - 1:
            end_page = sorted_records[i + 1]['start_page'] - 1
        else:
            end_page = total_pages - 1
        
        student_mappings[student_id] = (start_page, end_page)
    
    return student_mappings


def split_pdf_by_student(pdf_path: Path, student_mappings: Dict[str, Tuple[int, int]], 
                         output_dir: Path) -> List[Path]:
    """
    Split PDF into individual student PDFs using PyMuPDF.
    
    Args:
        pdf_path: Path to original multi-student PDF
        student_mappings: Dict mapping student IDs to page ranges
        output_dir: Directory to save split PDFs
    
    Returns:
        List of paths to created student PDFs
    """
    output_files = []
    
    # 1. Open the source PDF using PyMuPDF
    doc = fitz.open(pdf_path)
    
    # Track total pages created
    total_pages_created = 0
    
    # 2. For each student, extract their pages
    for student_id, (start_page, end_page) in student_mappings.items():
        # Skip empty or invalid student IDs
        if not student_id or student_id.lower() in ['not found', 'n/a', 'none', 'unknown']:
            logger.warning(f"Skipping invalid student ID: {student_id}")
            continue
            
        # 3. Create a new PDF document
        new_doc = fitz.open()
        
        # 4. Insert the range of pages for this student
        new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)
        pages_in_this_pdf = end_page - start_page + 1
        total_pages_created += pages_in_this_pdf
        
        # 5. Create output filename and path
        output_file = output_dir / f"{student_id}_answers.pdf"
        output_files.append(output_file)
        
        # 6. Save the new PDF
        new_doc.save(str(output_file))
        new_doc.close()
        
        logger.debug(f"Created PDF for student {student_id} with pages {start_page}-{end_page}: {output_file} ({pages_in_this_pdf} pages)")
    
    # 7. Close the source document
    doc.close()
        
    return output_files


def partition_multi_student_pdf(pdf_path: Path, output_dir: Path, gemini_api, max_workers: int = 4) -> List[Path]:
    """
    Main function to partition a multi-student PDF into individual files.
    
    Args:
        pdf_path: Path to multi-student PDF
        output_dir: Directory to save split PDFs
        gemini_api: Initialized Gemini API client
        max_workers: Maximum number of worker threads for parallel processing (default: 4)
    
    Returns:
        List of paths to created student PDFs
    
    Raises:
        ValueError: If the total number of pages in the split PDFs doesn't match the original PDF
    """
    # 1. Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Open PDF to get total pages
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()
    
    logger.info(f"Partitioning multi-student PDF ({total_pages} pages) into individual files")
    
    # 3. Analyze PDF to identify student sections
    student_records = analyze_multi_student_pdf(pdf_path, gemini_api, max_workers=max_workers)
    
    # 4. Create mapping of student IDs to page ranges
    student_mappings = create_student_page_mapping(student_records, total_pages)
    
    # 5. Split PDF into individual student PDFs
    split_pdfs = split_pdf_by_student(pdf_path, student_mappings, output_dir)
    
    # 6. Verify that all pages are accounted for
    split_page_count = 0
    for pdf_path in split_pdfs:
        try:
            doc = fitz.open(pdf_path)
            split_page_count += len(doc)
            doc.close()
        except Exception as e:
            logger.error(f"Error checking page count in {pdf_path}: {str(e)}")
    
    logger.debug(f"Original PDF: {total_pages} pages, Split PDFs total: {split_page_count} pages")
    
    if split_page_count != total_pages:
        error_msg = f"Page count mismatch: Original PDF has {total_pages} pages, but split PDFs have {split_page_count} pages total"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return split_pdfs 