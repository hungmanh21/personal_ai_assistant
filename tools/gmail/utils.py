from __future__ import annotations

import base64
import re
from typing import Any
from typing import Dict
from typing import Optional

from bs4 import BeautifulSoup


def remove_invisible_chars(text: str) -> str:
    """Removes invisible Unicode characters like zero-width spaces,
    soft hyphens, and Combining Grapheme Joiner (CGJ).

    Args:
        text (str): The input text to be cleaned.

    Returns:
        str: The cleaned text without invisible characters.
    """
    return re.sub(r'[\u200B\u200C\u00AD\u034F]', '', text)


def decode_base64(data: Optional[str]) -> str:
    """Decodes a base64url encoded Gmail message content.

    Args:
        data (Optional[str]): The base64url encoded string.

    Returns:
        str: The decoded UTF-8 string, with errors ignored.
    """
    if not data:
        return ''
    decoded_bytes = base64.urlsafe_b64decode(data)
    return decoded_bytes.decode('utf-8', errors='ignore')


def extract_clean_text(payload: Dict[str, Any]) -> str:
    """Extracts and cleans text content from an email payload.

    - Decodes base64-encoded text.
    - Extracts plain text from `text/plain` or `text/html` parts.
    - Removes invisible characters.
    - Strips URLs.
    - Normalizes whitespace.

    Args:
        payload (Dict[str, Any]): The email payload containing body content.

    Returns:
        str: The cleaned email body text.
    """
    body = ''

    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                body = decode_base64(part['body'].get('data', ''))
            elif part['mimeType'] == 'text/html':
                html_content = decode_base64(part['body'].get('data', ''))
                soup = BeautifulSoup(html_content, 'html.parser')
                body = soup.get_text(separator=' ')
    else:
        if payload['mimeType'] == 'text/plain':
            body = decode_base64(payload['body'].get('data', ''))
        elif payload['mimeType'] == 'text/html':
            html_content = decode_base64(payload['body'].get('data', ''))
            soup = BeautifulSoup(html_content, 'html.parser')
            body = soup.get_text(separator=' ')

    body = remove_invisible_chars(body)
    body = re.sub(r'http[s]?://\S+', '', body)  # Remove URLs
    body = ' '.join(body.split())  # Remove extra whitespace

    return body
