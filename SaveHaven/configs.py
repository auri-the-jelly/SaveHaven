from __future__ import print_function

import os.path
from appdirs import user_config_dir
config_dir = user_config_dir("SaveHaven", "Aurelia")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']

creds = None
# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
token_path = os.path.join(config_dir, 'token.json')
creds_path = os.path.join(config_dir, 'credentials.json')
if os.path.exists(token_path):
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            creds_path, SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open(token_path, 'w') as token:
        token.write(creds.to_json())
