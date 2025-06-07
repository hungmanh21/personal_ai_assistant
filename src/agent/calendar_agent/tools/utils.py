from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Dict

from googleapiclient.discovery import build
from shared.utils import read_personal_info
from src.agent.shared.get_credentials import get_credentials


def get_calendar_names() -> list[str]:
    """
    Retrieves the list of calendar names from the Google Calendar API.

    Returns:
        Optional[List[str]]: A list of calendar names if credentials are valid,
        otherwise empty list.
    """
    personal_info = read_personal_info()
    credentials_file_path = personal_info.get('token_access_path', None)
    if credentials_file_path is None:
        return []
    credentials_file_path = Path(
        __file__,
    ).parents[2] / Path(credentials_file_path)
    creds = get_credentials(
        token_access_path=credentials_file_path,
    )
    if creds:
        service = build('calendar', 'v3', credentials=creds)
        calendar_list: Dict[str, Any] = service.calendarList().list().execute()

        # Extract calendar names
        calendar_names = [
            calendar['summary']
            for calendar in calendar_list.get('items', [])
        ]

        return calendar_names
    return []
