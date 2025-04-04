# job_tracker_email_bot/gmail_utils.py

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import time
import random
from job_tracker_email_bot.config import SCOPES
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def safe_get_message(service, msg_id, retries=5):
    for i in range(retries):
        try:
            return service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        except HttpError as e:
            if e.resp.status == 429:
                wait = (2 ** i) + random.uniform(0, 1)
                print(f"⏳ Rate limit hit. Retrying in {wait:.1f}s...")
                time.sleep(wait)
            else:
                print(f"❌ Error fetching message {msg_id}: {e}")
                break
    return None  

def chunkify(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

def authenticate_gmail():
    token_path = "/tmp/token.json"
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        secret_path = "/etc/secrets/credentials.json" if os.getenv("RENDER") else "credentials.json"
        flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return creds