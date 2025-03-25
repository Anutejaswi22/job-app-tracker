from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest
from email.utils import parsedate_to_datetime
from threading import Thread
import base64
import os
import json
import re
import time

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Paths
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
status_path = os.path.join(parent_dir, 'status.json')
applied_path = os.path.join(parent_dir, 'applied.html')
rejected_path = os.path.join(parent_dir, 'rejected.html')

def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def extract_plain_text(payload):
    body = ""
    if 'parts' in payload:
        for part in payload['parts']:
            data = part.get('body', {}).get('data')
            mime = part.get('mimeType', '')
            if data:
                try:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    if mime == 'text/plain':
                        return decoded.strip()
                    elif mime == 'text/html' and not body:
                        body = re.sub('<[^<]+?>', '', decoded)
                except Exception:
                    continue
    elif payload.get('body', {}).get('data'):
        try:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        except Exception:
            pass
    return body.strip()

def is_valid_title(title):
    if not title or not isinstance(title, str):
        return False
    title = title.strip()

    # Filter out short, vague, or spammy lines
    if len(title.split()) <= 1:
        return False
    invalid_phrases = [
        "aligns with the specific requirements",
        "interest",
        "not quite finished",
        "position listed below",
        "has been submitted",
        "matches your qualifications",
        "at ",  # this is a strong sign it's a company name not title
        "with ",  # same
        "becomes available",
        "Thank you for applying",
        "application submitted"
    ]
    return not any(p.lower() in title.lower() for p in invalid_phrases)

def extract_job_title(body, subject):
    body = re.sub(r'\s+', ' ', body)

    # 1. Try from subject
    if subject:
        match = re.search(r'Indeed Application:\s*(.+)', subject)
        if match:
            title = match.group(1).strip()
            return title if is_valid_title(title) else "Unknown Title"

     # 2. Try regex patterns on body
    patterns = [
        r'role of ([\w\s\-\–\/&]+?)\s*(?:[\.\n]| - \d+)',
        r'for the ([\w\s\-\–\/&]+?) role',
        r'application for ([\w\s\-\–\/&]+?)(?:[\.\n]| - \d+)',
        r'considered for ([\w\s\-\–\/&]+)',
        r'opening for ([\w\s\-\–\/&]+)',
        r'position(?: of| for)? ([\w\s\-\–\/&]+?)(?:[\.\n]| - \d+)',
        r'job title[:\s]+([\w\s\-\–\/&]+)',
        r'(JR\d{6,}) ([\w\s\-\–\/&]+)',
        r'([\w\s\-\–]+?) position at',
        r'\b([\w\s\-\–]+?)\s*-\s*\d{5,}',
        r'application[:\s]+([\w\s\-\–\/&]+)',
        r'Indeed Application[:\s]+([\w\s\-\–\/&]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            title = ' '.join(match.groups()).strip()[:100]
            return title if is_valid_title(title) else "Unknown Title"

   # 3. Fallback: lines after “application submitted”
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if "application submitted" in line.lower():
            for offset in range(1, 4):
                if i + offset < len(lines):
                    candidate = lines[i + offset].strip()
                    if 4 <= len(candidate.split()) <= 10 and not candidate.lower().startswith("has been"):
                        return candidate if is_valid_title(candidate) else "Unknown Title"

    return "Unknown Title"

def extract_company_name(body, sender):
    match = re.search(r'\b(?:at|with)\s+([A-Z][a-zA-Z0-9& ]{2,40})\b', body)
    if match:
        return match.group(1).strip()

    domain = sender.split('@')[-1].split('.')[0]
    return domain.capitalize()

def build_html_page(title, entries):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    body {{ background-color: #0b0c17; color: #fff; font-family: Orbitron, sans-serif; padding: 40px; }}
    h1 {{ text-align: center; font-size: 2rem; color: #61e8f8; margin-bottom: 30px; }}
    .search-container {{ text-align: center; margin-bottom: 20px; }}
    .search-container input {{
      width: 300px; padding: 10px; border-radius: 6px; font-size: 16px; border: none;
    }}
    table {{ width: 90%; margin: auto; border-collapse: collapse; }}
    th, td {{
      padding: 14px; border-bottom: 1px solid #61e8f822; text-align: left;
    }}
    th {{ background-color: #11232f; color: #00ffff; }}
    tr:hover {{ background-color: #061821; }}
    .status.in-progress {{ color: lime; font-weight: bold; }}
    .status.rejected {{ color: red; font-weight: bold; }}
    a {{ color: #00ffff; display: block; text-align: center; margin-top: 30px; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="search-container">
    <input type="text" id="searchInput" placeholder="Search job title or company...">
  </div>
  <table id="jobsTable">
    <thead>
      <tr><th>Job Title</th><th>Company</th><th>Status</th><th>Date</th></tr>
    </thead>
    <tbody>
"""
    for job_title, company, date, status in entries:
        try:
            formatted_date = parsedate_to_datetime(date).strftime('%b %d, %Y %I:%M %p')
        except:
            formatted_date = date
        html += f"""
      <tr>
        <td>{job_title}</td>
        <td>{company}</td>
        <td class="status {'in-progress' if status == 'In Progress' else 'rejected'}">{status}</td>
        <td>{formatted_date}</td>
      </tr>"""
    html += """
    </tbody>
  </table>
  <a href="index.html">← Back to Tracker</a>
  <script>
    document.getElementById("searchInput").addEventListener("input", function () {
      const filter = this.value.toLowerCase();
      const rows = document.querySelectorAll("#jobsTable tbody tr");
      rows.forEach(row => {
        row.style.display = row.innerText.toLowerCase().includes(filter) ? "" : "none";
      });
    });
  </script>
</body>
</html>"""
    return html

def chunkify(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

def threaded_batch_fetch(service, message_ids, callback):
    def execute_batch(chunk, idx):
        time.sleep(idx * 2)  # slight delay to avoid rate limits
        print(f"📦 Processing batch {idx + 1}/{(len(message_ids) + 99) // 100}")
        batch = BatchHttpRequest(callback=callback, batch_uri='https://gmail.googleapis.com/batch')
        for msg in chunk:
            batch.add(service.users().messages().get(userId='me', id=msg['id'], format='full'))
        try:
            batch.execute()
        except Exception as e:
            print(f"❌ Batch {idx+1} failed:", e)

    threads = []
    for i, chunk in enumerate(chunkify(message_ids, 100)):
        t = Thread(target=execute_batch, args=(chunk, i))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


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


def get_job_emails(service, max_emails=10):
    applied, rejected = [], []
    all_messages = []
    next_page_token = None
    fetched = 0

    print(f"📬 Collecting up to {max_emails} message IDs...")

    while fetched < max_emails:
        response = service.users().messages().list(
            userId='me',
            maxResults=min(100, max_emails - fetched),
            pageToken=next_page_token
        ).execute()

        messages = response.get('messages', [])
        if not messages:
            break

        all_messages.extend(messages)
        fetched += len(messages)
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    print(f"✅ Collected {len(all_messages)} message IDs\n")

    # Break into chunks of 100
    chunks = list(chunkify(all_messages, 100))

    for i, chunk in enumerate(chunks):
        print(f"🔎 Scanning emails {i*100 + 1}–{i*100 + len(chunk)}...")

        for j, msg in enumerate(chunk, 1):
            msg_data = safe_get_message(service, msg['id'])
            if not msg_data:
                continue

            payload = msg_data.get('payload', {})
            headers = payload.get("headers", [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'No Date')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'unknown@unknown.com')

            body = extract_plain_text(payload)
            body_lower = body.lower()

            rejected_keywords = [
                "not move forward", "regret to inform you", "unfortunately", "another candidate",
                "no longer under consideration", "unable to offer"
            ]
            applied_keywords = [
                "thank you for your interest", "you have applied", "application will be reviewed",
                "we received your application", "has been submitted"
            ]

            job_title = extract_job_title(body, subject)
            company = extract_company_name(body, sender)

            if any(k in body_lower for k in rejected_keywords):
                rejected.append((job_title, company, date, "Rejected"))
            elif any(k in body_lower for k in applied_keywords):
                applied.append((job_title, company, date, "In Progress"))

        print(f"✅ Completed batch {i + 1}/{len(chunks)}\n")
        time.sleep(2)  # Delay between batches to avoid 429

    # ✅ Save HTML
    with open(applied_path, 'w') as f:
        f.write(build_html_page("Applied Companies", applied))
    with open(rejected_path, 'w') as f:
        f.write(build_html_page("Rejected Companies", rejected))
    with open(status_path, 'w') as f:
        json.dump({"applied_count": len(applied), "rejected_count": len(rejected)}, f, indent=2)

    print(f"✅ Done! Total scanned: {fetched} | Applied: {len(applied)} | Rejected: {len(rejected)}")

if __name__ == '__main__':
    start = time.time()
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    get_job_emails(service, max_emails=10)
    print(f"⏱️ Finished in {time.time() - start:.2f} seconds")