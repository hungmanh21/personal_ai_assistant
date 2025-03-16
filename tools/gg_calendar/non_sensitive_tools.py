from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from googleapiclient.discovery import build
from langchain_core.tools import tool
from tools.get_credentials import get_credentials
from utils import read_personal_info


@tool
def get_next_n_calendar_events(
    n: int, calendar_name: Optional[str] = None,
    duration: Optional[Union[str, datetime.timedelta]] = None,
) -> str:
    """
    Retrieves the next `n` events from Google Calendar.

    Args:
        n (int): The number of upcoming events to retrieve.
        calendar_name (Optional[str], optional):
        The name of the calendar to filter events from.
            If None, events from all available calendars are considered.
            Defaults to None.
        duration (Optional[Union[str, datetime.timedelta]], optional):
        The time range for events.
            Can be a string ('day', 'week', 'year') or a `datetime.
            timedelta` object. If None,
            there is no upper time limit. Defaults to None.

    Returns:
        str: A formatted string listing the next `n` events,
        including details such as
        event ID, calendar name, start time, event name, location,
        and description.
    """
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

        now = datetime.datetime.utcnow()

        # Compute timeMax based on duration
        if isinstance(duration, str):
            if duration == 'day':
                time_max = now + datetime.timedelta(days=1)
            elif duration == 'week':
                time_max = now + datetime.timedelta(weeks=1)
            elif duration == 'year':
                time_max = now + datetime.timedelta(days=365)
            else:
                return (
                    "Invalid duration. Use 'day', 'week', 'year', "
                    'or a timedelta object.'
                )
        elif isinstance(duration, datetime.timedelta):
            time_max = now + duration
        else:
            time_max = None  # No duration filter

        now_iso: str = now.isoformat() + 'Z'
        time_max_iso: Optional[str] = time_max.isoformat(
        ) + 'Z' if time_max else None

        events_all: List[Dict[str, Any]] = []
        calendar_list: Dict[str, Any] = service.calendarList().list().execute()

        # Extract calendar names
        calendar_names = [
            calendar['summary']
            for calendar in calendar_list.get('items', [])
        ]

        if (
            calendar_name
            and calendar_name.casefold()
            not in (name.casefold() for name in calendar_names)
        ):
            return (
                'Calendar name should be one of the following: '
                f"{', '.join(calendar_names)}"
            )

        # Loop through each calendar to fetch events
        for calendar in calendar_list.get('items', []):
            if (
                calendar_name
                and calendar['summary'].lower() != calendar_name.lower()
            ):
                continue  # Skip calendars that don't match the filter

            calendar_id: str = calendar['id']
            if time_max_iso:
                events_result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=now_iso,
                    timeMax=time_max_iso,
                    maxResults=20,
                    singleEvents=True,
                    orderBy='startTime',
                ).execute()

            else:
                events_result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=now_iso,
                    maxResults=20,
                    singleEvents=True,
                    orderBy='startTime',
                ).execute()

            events: List[Dict[str, Any]] = events_result.get('items', [])

            for event in events:
                start: str = event.get('start', {}).get(
                    'dateTime', event.get('start', {}).get('date'),
                )
                end: str = event.get('end', {}).get(
                    'dateTime', event.get('end', {}).get('date'),
                )
                event_data: Dict[str, Any] = {
                    'id': event['id'],
                    'calendar': calendar['summary'],
                    'start': start,
                    'end': end,
                    'summary': event['summary'],
                }

                # Add location and notes only if they exist
                if 'location' in event:
                    event_data['location'] = event['location']
                if 'description' in event:
                    event_data['description'] = event['description']

                events_all.append(event_data)

        # Sort all events by start time
        events_all = sorted(events_all, key=lambda x: x['start'])

        next_n_events = events_all[:n]

        results = f'Next {n} Events Across All Calendars:\n'
        for event in next_n_events:
            results += (
                f"Event ID : {event['id']}\n"
                f"Calendar Name: {event['calendar']} | "
                f"From {event['start']} To {event['end']}"
                f"- {event['summary']}\n"
            )
            if 'location' in event:
                results += f"📍 Location: {event['location']}\n"
            if 'description' in event:
                results += f"📝 Notes: {event['description']}\n"
            results += '\n'
        return results
    return 'No events found'
