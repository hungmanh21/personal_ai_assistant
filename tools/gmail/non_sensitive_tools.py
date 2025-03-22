from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from langchain_core.tools import tool
from tools.get_credentials import get_credentials
from utils import read_personal_info

from .utils import extract_clean_text


@tool
def fetch_inbox_messages(
    max_results: int = 5, user_id: str = 'me',
    last_n_days: Optional[int] = None,
) -> str:
    """
    Lists messages from the Gmail inbox within a specified time range.

    Args:
        max_results (int, optional): The maximum number of messages to
        retrieve. Defaults to 5.
        user_id (str, optional): The user's email ID. Defaults to "me"
            (the authenticated user).
        last_n_days (Optional[int], optional): Number of past days to filter
            emails from. If None, retrieves all available emails.

    Returns:
        str: A formatted string containing the message details
            (ID, sender, subject).
    """
    personal_info = read_personal_info()
    credentials_file_path = personal_info.get('token_access_path', None)
    if credentials_file_path:
        credentials_file_path = Path(
            __file__,
        ).parents[2] / Path(credentials_file_path)
        creds = get_credentials(token_access_path=credentials_file_path)
    else:
        creds = get_credentials()

    if not creds:
        return 'Failed to authenticate with Gmail API.'
    service = build('gmail', 'v1', credentials=creds)
    query = 'in:inbox'  # Base query to get only Inbox emails

    # If last_n_days is specified, calculate the date and update query
    if last_n_days is not None:
        date_since = (
            datetime.utcnow() -
            timedelta(days=last_n_days)
        ).strftime('%Y/%m/%d')
        query += f' after:{date_since}'  # Gmail query to filter by date

    results = service.users().messages().list(
        userId=user_id, maxResults=max_results, q=query,
    ).execute()
    messages = results.get('messages', [])

    if not messages:
        return 'No messages found in the specified time range.'
    email_list = ['📩 **Inbox Messages**', '=' * 60]
    for msg in messages:
        msg_id = msg['id']
        message = service.users().messages().get(
            userId=user_id, id=msg_id, format='metadata',
            metadataHeaders=['Subject', 'From'],
        ).execute()
        headers = message['payload']['headers']

        subject = next(
            (h['value'] for h in headers if h['name'] == 'Subject'),
            'No Subject',
        )

        sender = next(
            (h['value'] for h in headers if h['name'] == 'From'),
            'Unknown Sender',
        )

        email_list.append(
            f'📧 Message ID: {msg_id}\nFrom: {sender}\nSubject: {subject}\n'
            f"{'-' * 50}",
        )
    return '\n'.join(email_list)


@tool
def get_email_details(message_id: str, user_id: str = 'me') -> str:
    """
    Fetches and returns the full details of an email, including sender,
    subject, date, and content.

    Args:
        message_id (str): The unique ID of the email message.
        user_id (str, optional): The user's email ID.

    Returns:
        str: A formatted string containing the email details (sender, subject,
        date, and content).
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
    if creds:
        service = build('gmail', 'v1', credentials=creds)
        message = service.users().messages().get(
            userId=user_id, id=message_id, format='full',
        ).execute()
        payload = message['payload']
        headers = payload['headers']

        # Extract Details
        subject = next(
            (
                header['value']
                for header in headers if header['name'] == 'Subject'
            ),
            'No Subject',
        )
        sender = next(
            (
                header['value']
                for header in headers if header['name'] == 'From'
            ),
            'Unknown Sender',
        )
        date = next(
            (
                header['value']
                for header in headers if header['name'] == 'Date'
            ),
            'Unknown Date',
        )
        email_content = extract_clean_text(payload)
        # Print Email Details
        email_details = (
            f'📩 **Email Details**\n'
            f"{'=' * 60}\n"
            f'From: {sender}\n'
            f'Subject: {subject}\n'
            f'Date: {date}\n'
            f'Content:\n\n'
            f'{email_content}\n'
        )
        return email_details
    return 'Failed to fetch email details due to authentication issues.'


# get_email_details(message_id="195b3c980ad27ca2")
# list_messages(last_n_days=2)
