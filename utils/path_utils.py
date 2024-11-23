import os
from pathlib import Path

def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_path(file):
    project_root = get_project_root()
    return os.path.join(project_root, file)

def create_directory(directory="output"):
    Path(directory).mkdir(parents=True, exist_ok=True)
