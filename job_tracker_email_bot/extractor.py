import spacy
import re
import base64
import html
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from datetime import datetime

nlp = spacy.load("en_core_web_sm")

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
                        soup = BeautifulSoup(decoded, "html.parser")
                        text = soup.get_text(separator=' ', strip=True)
                        if text:
                            body = text
                except Exception:
                    continue
    elif payload.get('body', {}).get('data'):
        try:
            decoded = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
            body = decoded
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
    
    invalid_patterns = [
        r'^https?:\/\/',  # starts with http
        r'^www\.',        # starts with www
        r'\.com|\.org|\.net',  # contains domain
        r'<!DOCTYPE html>',
        r'\b(html|head|body|meta|script)\b',
    ]
        
    if any(re.search(p, title, re.IGNORECASE) for p in invalid_patterns):
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
        "application submitted","interest", "position listed", "application submitted", "thank you"
    ]
    return not any(p.lower() in title.lower() for p in invalid_phrases)

def extract_job_title_nlp(text):
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ in ["WORK_OF_ART", "TITLE", "PRODUCT", "ORG"]:
            if len(ent.text.strip().split()) >= 2:
                return ent.text.strip()
    return "Unknown Title"

def extract_job_title(body, subject):
    body = re.sub(r'\s+', ' ', body)  # Normalize whitespace

    # A. Match pattern like: Ref: 5005 - Research Engineer
    match = re.search(r'Ref[:\s]*\d{4,}\s*[-–]\s*([\w\s/\-&]{3,80})', body, re.IGNORECASE)
    if match:
        return clean_title(match.group(1))

    # B. Match: "for the JRxxxx Job Title"
    match = re.search(r'for the JR\d+\s+([\w\s/\-&]{3,80})\s+(role|position)?', body, re.IGNORECASE)
    if match:
        return clean_title(match.group(1))

    # C. Match: "applying to the XYZ Role"
    match = re.search(r'applying (?:to|for) (?:the )?([\w\s/\-&]{3,80})(?: role| position)?', body, re.IGNORECASE)
    if match:
        return clean_title(match.group(1))

    # D. Match: "application for the position of XYZ"
    match = re.search(r'application for (?:the )?(position|role) of ([\w\s/\-&]{3,80})', body, re.IGNORECASE)
    if match:
        return clean_title(match.group(2))

    # E. Match: "your application to XYZ for the ABC role"
    match = re.search(r'application to [\w\s]+ for the ([\w\s/\-&]{3,80})', body, re.IGNORECASE)
    if match:
        return clean_title(match.group(1))

    # F. Match: "Job Title: XYZ" in body
    match = re.search(r'Job Title[:\s]*([\w\s/\-&]{3,80})', body, re.IGNORECASE)
    if match:
        return clean_title(match.group(1))

    # G. Fallback: subject line patterns
    if subject:
        match = re.search(r'Application[:\s\-]*([\w\s/\-&]{3,80})', subject)
        if match:
            return clean_title(match.group(1))

        # Last resort — just clean the full subject line
        return clean_title(subject)

    return "Unknown Title"

def clean_title(title):
    title = title.strip()

    # Remove greetings or names
    title = re.sub(r'\bDear\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b', '', title, flags=re.IGNORECASE)
    title = re.sub(r'^(Hi|Hello|Dear)[^.,:\n]*', '', title, flags=re.IGNORECASE)

    # Remove known labels and IDs (Ref, Job Number, Application)
    title = re.sub(r'(?:Ref|Job Number|Position)\s*[:\-]?\s*\d{4,}\s*[-–]?', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\b(?:Application|Applying|Submitted|Regarding)\b.*?(to|for)?', '', title, flags=re.IGNORECASE)
    # Remove "Re:" or "Fwd:" from start
    title = re.sub(r'^(Re|Fwd):\s*', '', title, flags=re.IGNORECASE)

    # Remove trailing job-related filler
    title = re.sub(r'\b(role|position|job)\b.*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\b(at|in|with|from|of)\s+\w+.*$', '', title, flags=re.IGNORECASE)

    # Remove URLs, HTML noise, or extra punctuation
    title = re.sub(r'https?:\/\/\S+|www\.\S+', '', title)
    title = re.sub(r'<.*?>', '', title)
    title = title.strip(' .,-–')

    # Remove duplicate words (e.g., "Engineer Engineer")
    title = ' '.join(dict.fromkeys(title.split()))

    # Truncate long titles
    words = title.split()
    if len(words) > 10:
        title = ' '.join(words[:8])

    # Format nicely
    title = title.title()

    return title if is_valid_title(title) else "Unknown Title"

known_companies = [
    "Intel", "Google", "Amazon", "Microsoft", "Meta", "Apple", "Netflix",
    "Salesforce", "Nvidia", "Adobe", "Oracle", "Cisco"
]

blacklist_names = ['dave', 'team', 'hiring team', 'from the team', 'gmail']

def extract_company_name(body, sender):
    domain = sender.split('@')[-1].split('.')[0].lower()

    domain_map = {
        'intel': 'Intel',
        'google': 'Google',
        'amazon': 'Amazon',
        'microsoft': 'Microsoft',
        'meta': 'Meta',
        'apple': 'Apple',
        'netflix': 'Netflix',
        'salesforce': 'Salesforce',
        'nvidia': 'Nvidia',
        'adobe': 'Adobe',
        'oracle': 'Oracle',
        'cisco': 'Cisco',
    }

    # 1. Map from domain if possible
    if domain in domain_map:
        return domain_map[domain]

    # 2. Try body phrases like "from the team at Intel"
    for company in known_companies:
        if any(phrase in body.lower() for phrase in [
            f"at {company.lower()}",
            f"with {company.lower()}",
            f"from the team at {company.lower()}",
        ]):
            return company

    # 3. Filter out common false positives
    suspicious_match = re.search(r'\b(?:from|at|with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', body)
    if suspicious_match:
        probable = suspicious_match.group(1)
        if probable.strip().lower() in blacklist_names:
            return "Unknown Company"

    # 4. Try pattern like: "at XYZ Corp"
    match = re.search(r'\b(?:at|with)\s+([A-Z][a-zA-Z0-9& ]{2,40})\b', body)
    if match:
        company_guess = match.group(1).strip()
        if company_guess.lower() not in blacklist_names:
            return company_guess

    # 5. Final fallback to domain
    return domain.capitalize() if domain not in blacklist_names else "Unknown Company"

def build_html_page(title, entries):
    entries.sort(key=lambda x: parsedate_to_datetime(x[2]), reverse=True)
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
    footer {{
      text-align: center;
      margin-top: 20px;
      font-size: 0.9em;
      color: gray;
    }}
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
    for idx, (job_title, company, date, status, body) in enumerate(entries):
        company_display = company.upper() if company.lower() in {"ibm", "trm"} else company.title()

        try:
            formatted_date = parsedate_to_datetime(date).strftime('%b %d, %Y %I:%M %p')
        except:
            formatted_date = date

        if status == 'In Progress':
            badge_html = '<span class="badge badge-success">In Progress</span>'
        elif status == 'Rejected':
            badge_html = '<span class="badge badge-danger">Rejected</span>'
        elif status == 'Uncertain':
            badge_html = '<span class="badge" style="background-color: gold; color: black;">Uncertain</span>'
        else:
            badge_html = f'<span class="badge">{status}</span>'

        html += f"""
        <tr>
            <td>
                {job_title}
                <button class="view-btn" onclick="showEmailModal(`{html.escape(body).replace('`', '&#96;')}`)">👁 View</button>
            </td>
            <td>{company_display}</td>
            <td>{badge_html}</td>
            <td>{formatted_date}</td>
        </tr>
        """

    last_updated = datetime.now().strftime('%b %d, %Y at %I:%M %p')
    html += f"""
    </tbody>
  </table>
  <a href="/uncertain">🟡 View Uncertain Emails</a>
  <footer>⏱️ Last updated on: {last_updated}</footer>
  <a href="/dashboard">← Back to Tracker</a>

  <!-- 📬 Popup Modal for Full Email -->
  <div id="popupModal" style="display:none; position:fixed; top:10%; left:10%; width:80%; height:70%; background-color:#1b1c28; color:#eee; padding:20px; border-radius:10px; overflow-y:auto; z-index:9999; box-shadow: 0 0 20px rgba(0,0,0,0.6);">
    <button onclick="closeEmailModal()" style="float:right; background-color:#333; color:#fff; border:none; padding:5px 10px; border-radius:6px;">❌ Close</button>
    <h3 style="margin-top:0;">📬 Full Email Content</h3>
    <div id="popupContent" style="white-space: pre-wrap; margin-top:10px; word-wrap: break-word;"></div>
  </div>

  <script>
    document.getElementById("searchInput").addEventListener("input", function () {{
      const filter = this.value.toLowerCase();
      document.querySelectorAll("#jobsTable tbody tr").forEach(row => {{
        const text = row.innerText.toLowerCase();
        row.style.display = text.includes(filter) ? "" : "none";
      }});
    }});

    function showEmailModal(content) {{
        document.getElementById("popupContent").innerText = content;
        document.getElementById("popupModal").style.display = "block";
    }}

    function closeEmailModal() {{
        document.getElementById("popupModal").style.display = "none";
    }}
  </script>
</body>
</html>"""

    return html

def chunkify(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


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

applied_keywords = ['applied', 'application submitted', 'thank you for applying', 'received your application',
        'thank you for your interest', 'you have applied', 'application will be reviewed',
        'we received your application', 'has been submitted', 'application received',
        'this email is to confirm', 'you’re being considered', 'we appreciate your application',
        'has been successfully submitted', 'we have received your application',
        'your application has been received', 'you have successfully applied'
    ]

rejected_keywords = ['rejected', 'not selected', 'unfortunately', 'We regret to inform you', 'pursue other candidates',
        'we regret to inform', 'not been selected', 'unfortunately',
        'we have decided to move forward', 'position has been closed',
        'we will not be moving forward', 'your application was not successful',
        'we are unable to offer you a position', 'another candidate has been selected',
        'no longer under consideration', 'decided not to move forward',
        'your candidacy has been declined', 'we’re unable to proceed',
        'we have chosen to move forward with other candidates',
        'we won’t be progressing your application'
    ]  