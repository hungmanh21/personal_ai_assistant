from __future__ import annotations

import json
import os
from typing import Any
from typing import Dict

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PERSONAL_INFO_FILE_PATH = os.getenv('PERSONAL_INFO_PATH', 'personal_info.json')


def read_personal_info() -> Dict[str, Any]:
    """
    Reads and returns the personal information stored in the JSON file.

    Returns:
        dict: A dictionary containing the stored personal information.
    """
    try:
        with open(PERSONAL_INFO_FILE_PATH, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_personal_info(key: str, value: Any) -> None:
    """
    Saves a key-value pair to the personal information JSON file.
    If the file does not exist, it creates a new one.

    Args:
        key (str): The key for the information to be stored.
        value (Any): The value associated with the key.
    """
    try:
        with open(PERSONAL_INFO_FILE_PATH, encoding='utf-8') as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    print('data in file')
    print(data)
    print('------')

    if data.get(key) == value:
        return  # No update needed
    # Update the dictionary with the new key-value pair
    data[key] = value

    # Save the updated data back to the file
    with open(PERSONAL_INFO_FILE_PATH, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4)


def read_markdown(file_path: str) -> str:
    """
    Reads the content of a Markdown file and returns it as a string.

    Args:
        file_path (str): The path to the Markdown file.

    Returns:
        str: The content of the file or an error message if an issue occurs.
    """
    try:
        with open(file_path, encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return 'File not found. Please check the file path.'
    except Exception as e:
        return f'An error occurred: {e}'
