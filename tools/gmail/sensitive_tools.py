from __future__ import annotations

import base64
from email.mime.text import MIMEText
from pathlib import Path

from googleapiclient.discovery import build
from langchain_core.tools import tool
from tools.get_credentials import get_credentials
from utils import read_personal_info


@tool
def send_email(to_email: str, subject: str, message_body: str) -> str:
    """
    Sends an email using the Gmail API.

    This function retrieves stored credentials, constructs an email, and sends
    it via Gmail API.

    Args:
        to_email (str): Recipient's email address.
        subject (str): Subject of the email.
        message_body (str): Body content of the email.

    Returns:
        str: A success message if the email is sent successfully, or an error
        message if it fails.
    """
    personal_info = read_personal_info()
    credentials_file_path = personal_info.get('token_access_path', None)
    if credentials_file_path:
        credentials_file_path = Path(
            __file__,
        ).parents[2] / Path(credentials_file_path)
        creds = get_credentials(
            token_access_path=credentials_file_path,
        )
    else:
        creds = get_credentials()
    if not creds:
        return 'Failed to retrieve credentials. Email not sent.'
    service = build('gmail', 'v1', credentials=creds)

    # Create email message
    message = MIMEText(message_body)
    message['to'] = to_email
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # Send email
    try:
        service.users().messages().send(
            userId='me', body={'raw': raw_message},
        ).execute()
        return f'Email successfully sent to {to_email}'
    except Exception as e:
        return f'Error sending email: {e}'


# send_email("hungmanh211103@gmail.com", "Hello from AI", "Xin chào")
