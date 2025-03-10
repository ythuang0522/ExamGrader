"""Utility functions for file operations."""

import json
import os
from typing import Dict, Any

def save_intermediate_json(data: Dict[str, Any], base_filepath: str, suffix: str) -> str:
    """Save intermediate data to a JSON file.
    
    Args:
        data: Dictionary data to save
        base_filepath: Original input filepath to derive the JSON filename from
        suffix: Suffix to append to the filename (e.g., '_questions', '_correct', '_student')
        
    Returns:
        Path to the saved JSON file
    """
    # Get the directory and filename without extension
    directory = os.path.dirname(base_filepath)
    filename = os.path.splitext(os.path.basename(base_filepath))[0]
    
    # Create output filename
    output_path = os.path.join(directory, f"{filename}{suffix}.json")
    
    # Save with nice formatting
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return output_path

def load_intermediate_json(filepath: str) -> Dict[str, Any]:
    """Load intermediate data from a JSON file.
    
    Args:
        filepath: Path to the JSON file to load
        
    Returns:
        Dictionary containing the loaded data
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f) 