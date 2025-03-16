from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from langchain_core.tools import tool
from tools.get_credentials import get_credentials
from utils import read_personal_info


def validate_datetime(dt_str: str) -> bool:
    """Validate if the given datetime string is in ISO 8601 format
    (YYYY-MM-DDTHH:MM:SSZ or YYYY-MM-DDTHH:MM:SS±HH:MM)."""
    iso_utc_format = '%Y-%m-%dT%H:%M:%SZ'  # UTC format with 'Z'
    iso_offset_format = '%Y-%m-%dT%H:%M:%S%z'  # Offset format

    try:
        if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', dt_str):
            datetime.datetime.strptime(dt_str, iso_utc_format)
        else:
            datetime.datetime.strptime(dt_str, iso_offset_format)
        return True
    except ValueError:
        return False


@tool
def create_calendar_event(
    start_time: str, end_time: str,
    calendar_name: str, title: str,
    location: Optional[str] = None, description: Optional[str] = None,
):
    """
    Creates an event in a Google Calendar.

    Args:
        start_time (str): The start time of the event in ISO 8601 format
            (YYYY-MM-DDTHH:MM:SSZ or YYYY-MM-DDTHH:MM:SS±HH:MM).
        end_time (str): The end time of the event in ISO 8601 format
            (YYYY-MM-DDTHH:MM:SSZ or YYYY-MM-DDTHH:MM:SS±HH:MM).
        calendar_name (str): The name of the Google Calendar where the event
            should be created.
        title (str): The title of the event.
        location (Optional[str]): The location of the event. Defaults to None.
        description (Optional[str]): The description of the event. Defaults to
            None.

    Returns:
        Optional[str]: A message confirming event creation with the event link,
            or an error message if unsuccessful.
    """
    if not all([start_time, end_time, calendar_name, title]):
        return (
            "Error: 'start_time', 'end_time', "
            "'calendar_name', and 'title' are required."
        )

    if not validate_datetime(start_time) or not validate_datetime(end_time):
        return (
            "Error: 'start_time' and 'end_time' must be in ISO 8601 format "
            '(YYYY-MM-DDTHH:MM:SSZ or '
            'YYYY-MM-DDTHH:MM:SS±HH:MM).'
        )

    personal_info = read_personal_info()
    credentials_file_path = personal_info.get('token_access_path', None)
    credentials_file_path = Path(
        __file__,
    ).parents[2] / Path(credentials_file_path)
    creds = get_credentials(token_access_path=credentials_file_path)

    if creds:
        service = build('calendar', 'v3', credentials=creds)

        # Get list of calendars to match the provided calendar name
        calendar_list = (
            service.calendarList()
            .list()
            .execute()
            .get('items', [])
        )
        calendar_id = next(
            (
                cal['id'] for cal in calendar_list if cal.get(
                    'summary',
                ) == calendar_name
            ), None,
        )

        if not calendar_id:
            return f"Error: Calendar '{calendar_name}' not found."

        event = {
            'summary': title,
            'location': location or '',
            'description': description or '',
            'start': {'dateTime': start_time},
            'end': {'dateTime': end_time},
        }

        event_result = service.events().insert(
            calendarId=calendar_id, body=event,
        ).execute()
        return f"Event created: {event_result.get('htmlLink')}"


@tool
def delete_calendar_event(calendar_name: str, event_id: str):
    """
    Deletes an event from a Google Calendar.

    Args:
        calendar_name (str): The name of the Google Calendar containing the
            event.
        event_id (str): The unique ID of the event to be deleted.

    Returns:
        Optional[str]: A success message if deletion is successful, or an error
            message if unsuccessful.
    """

    try:
        personal_info = read_personal_info()
        credentials_file_path = personal_info.get('token_access_path', None)
        credentials_file_path = Path(
            __file__,
        ).parents[2] / Path(credentials_file_path)
        creds = get_credentials(
            token_access_path=credentials_file_path,
        )
        if creds:
            service = build('calendar', 'v3', credentials=creds)

            # Fetch the list of calendars to find the calendar ID
            calendar_list = (
                service.calendarList()
                .list()
                .execute()
                .get('items', [])
            )
            calendar_id = next(
                (
                    cal['id'] for cal in calendar_list if cal.get(
                        'summary',
                    ) == calendar_name
                ), None,
            )

            if not calendar_id:
                print(f"Error: Calendar '{calendar_name}' not found.")
                return

            # Delete the event
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
            ).execute()
            return (
                f"Event '{event_id}' deleted successfully from "
                f"'{calendar_name}'."
            )
        return (
            f"Event '{event_id}' cannot be deleted."
        )

    except Exception as e:
        return (
            f"Event '{event_id}' cannot be deleted. Error {e}"
        )
