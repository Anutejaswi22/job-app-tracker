# job_tracker_email_bot/tracker.py

from job_tracker_email_bot.gmail_utils import authenticate_gmail
from job_tracker_email_bot.processor import get_job_emails
from googleapiclient.discovery import build
import time

if __name__ == '__main__':
    start = time.time()
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    get_job_emails(service, max_emails=10)
    print(f"⏱️ Finished in {time.time() - start:.2f} seconds")