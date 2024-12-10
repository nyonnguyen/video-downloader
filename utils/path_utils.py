import os
import re
from pathlib import Path

def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_path(file):
    project_root = get_project_root()
    return os.path.join(project_root, file)

def create_directory(directory="output"):
    Path(directory).mkdir(parents=True, exist_ok=True)


def format_video_title(video_title: str) -> str:
    # Remove special characters using a regular expression
    formatted_title = re.sub(r'[^\w\s]', '', video_title)
    # Replace spaces by underscore
    formatted_title = formatted_title.replace(' ', '_')
    # Replace spaces with underscores
    formatted_title = formatted_title.replace(' ', '_')
    # Return the formatted title
    return formatted_title