from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .utils import save_personal_info

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


TIME_OUT_GET_CREDENTIALS = int(os.getenv('TIME_OUT_GET_CREDENTIALS', 60))


def get_credentials(token_access_path: str | None = None):
    """
    Manages Google API authentication for Calendar and Gmail.

    This function handles authentication by checking for existing credentials,
    refreshing expired tokens, or prompting the user to log in if necessary.
    It supports multiple Google services, including Google Calendar and Gmail.

    Args:
        token_access_path (str | None, optional):
            Path to the stored credentials file.
            If None, a new credentials file will be created using the
            authenticated user's email as the filename.

    Returns:
        Credentials | None:
        A valid `google.auth.credentials.Credentials` object if
        authentication is successful, otherwise None.
    """
    SCOPES = [
        'openid',
        'https://www.googleapis.com/auth/calendar',  # Full access to Calendar
        # Read, send, and manage Gmail messages
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.send',  # Send emails via Gmail
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
    ]
    creds = None

    # Check if token.json exists to load stored credentials
    if token_access_path and os.path.exists(token_access_path):
        logging.info('Loading credentials')
        creds = Credentials.from_authorized_user_file(
            token_access_path, SCOPES,
        )

    # If no valid credentials are available, prompt user to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES,
                )

                # Start authentication process
                start_time = time.time()
                creds = flow.run_local_server(
                    port=0, timeout_seconds=TIME_OUT_GET_CREDENTIALS,
                )

                if time.time() - start_time > TIME_OUT_GET_CREDENTIALS:
                    logging.warning(
                        (
                            'Authentication timeout: '
                            'User did not complete login in time.'
                        ),
                    )
                    return creds

            except Exception as e:
                logging.exception(f'Authentication failed: {e}')
                return creds

        # Retrieve the authenticated email to create a unique token file
        if creds and creds.valid:
            try:
                service = build('oauth2', 'v2', credentials=creds)
                user_info = service.userinfo().get().execute()
                user_email = user_info.get('email', 'unknown_user')
                safe_email = user_email.replace(
                    '@', '_',
                ).replace('.', '_')  # Safe filename
                token_access_path = (
                    token_access_path or f'token_{safe_email}.json'
                )

                # Save the new credentials for future use
                with open(token_access_path, 'w') as token:
                    token.write(creds.to_json())

                logging.info(f'Credentials saved to {token_access_path}')

                save_personal_info('token_access_path', token_access_path)

            except Exception as e:
                logging.error(f'Failed to retrieve user email: {e}')

    return creds
