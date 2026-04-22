import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PatchAgent")

def read_file(file_path, max_lines=None):
    """Reads a file securely. Returns content or raises error."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    if max_lines and len(lines) > max_lines:
        logger.warning(f"File {file_path} truncated for context (limit: {max_lines})")
        return "".join(lines[:max_lines]) + "\n...[truncated]..."
        
    return "".join(lines)

def list_files_recursive(root_dir, ignore_dirs=None):
    """Lists all files in a directory recursively, ignoring specified folders."""
    if ignore_dirs is None:
        ignore_dirs = [".git", "node_modules", ".next", "__pycache__", "venv"]
        
    file_list = []
    for root, dirs, files in os.walk(root_dir):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            file_list.append(os.path.join(root, file))
    return file_list
