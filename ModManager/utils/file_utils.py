"""
Utility functions for file operations
"""
import os

def read_file(file_path):
    """
    Read a file and return its contents
    
    Args:
        file_path (str): Path to the file to read
        
    Returns:
        str: Contents of the file, or empty string if file doesn't exist
    """
    if not os.path.exists(file_path):
        return ""
        
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return ""

def write_file(file_path, content):
    """
    Write content to a file
    
    Args:
        file_path (str): Path to the file to write
        content (str): Content to write to the file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        return True
    except Exception as e:
        print(f"Error writing to file {file_path}: {e}")
        return False