from datetime import datetime
from email.utils import parsedate_to_datetime
import html

def build_html_page(title, entries):
    entries.sort(key=lambda x: parsedate_to_datetime(x[2]), reverse=True)
    html_content = f"""<!DOCTYPE html>
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

        escaped_body = html.escape(body).replace('`', '&#96;')

        html_content += f"""
        <tr>
            <td>
                {job_title}
                <button class="view-btn" onclick="showEmailModal(`{escaped_body}`)">👁 View</button>
            </td>
            <td>{company_display}</td>
            <td>{badge_html}</td>
            <td>{formatted_date}</td>
        </tr>
        """

    last_updated = datetime.now().strftime('%b %d, %Y at %I:%M %p')
    html_content += f"""
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

    return html_content