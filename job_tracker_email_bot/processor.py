# job_tracker_email_bot/processor.py
from job_tracker_email_bot.classifier import hybrid_classify_email, is_job_related
from job_tracker_email_bot.extractor import extract_plain_text, extract_job_title, extract_company_name
from job_tracker_email_bot.gmail_utils import safe_get_message, chunkify
from job_tracker_email_bot.builder import build_html_page
from job_tracker_email_bot.config import (
    status_path, applied_path, rejected_path, parsedate_to_datetime, base_dir
)
import json, time, os
from datetime import datetime
from job_tracker_email_bot.extractor import (
    clean_title,
    extract_job_title_nlp,
    extract_company_name,
    extract_job_title,
    is_valid_title
)

def deduplicate(entries):
    seen = set()
    result = []
    for entry in entries:
        title = entry[0].strip().lower()
        company = entry[1].strip().lower()
        if title == "unknown title":
            continue  # skip
        key = (title, company)
        if key not in seen:
            seen.add(key)
            result.append(entry)
    return result

def get_job_emails(service, max_emails=50, after=None, before=None, filter_by_date=False):
    from datetime import datetime

    applied, rejected, uncertain = [], [], []
    all_messages = []
    next_page_token = None
    fetched = 0

    print(f"📬 Collecting up to {max_emails} message IDs...")

    # Gmail query
    search_query = (
        "(subject:(application OR interview OR opportunity OR rejected) "
        "OR from:(workday.com OR linkedin.com OR greenhouse.io OR ziprecruiter.com "
        "OR glassdoor.com OR jobvite.com OR smartrecruiters.com OR successfactors.com))"
    )
    if after:
        after_str = datetime.utcfromtimestamp(after).strftime("%Y/%m/%d")
        search_query += f" after:{after_str}"
    if before:
        # ✅ Include the "To" date by adding 1 day (86400 seconds)
        before += 86400
        before_str = datetime.utcfromtimestamp(before).strftime("%Y/%m/%d")
        search_query += f" before:{before_str}"

    while fetched < max_emails:
        response = service.users().messages().list(
            userId='me',
            q=search_query,
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
            date_str = next((h['value'] for h in headers if h['name'] == 'Date'), 'No Date')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'unknown@unknown.com')

            try:
                email_datetime = parsedate_to_datetime(date_str)
                email_epoch = int(time.mktime(email_datetime.timetuple()))
            except:
                print("❌ Failed to parse date, skipping.")
                continue

            if filter_by_date:
                if (after and email_epoch < after) or (before and email_epoch > before):
                    print(f"⏳ Skipping email outside range: {date_str}")
                    continue

            body = extract_plain_text(payload)

            if not is_job_related(subject, sender, body):
                print(f"🚫 Skipping: {subject} | From: {sender}")
                with open("skipped_emails.log", "a") as log:
                    log.write(f"Skipped: {subject} | Sender: {sender}\n")
                continue

            print(f"\n📨 Email {j} of batch {i + 1}")
            print(f"🟦 Subject: {subject}")
            print(f"📅 Date: {date_str}")
            print(f"📤 Sender: {sender}")
            print(f"📃 Body Preview:\n{body[:300]}...\n")

            job_title = extract_job_title(body, subject)

            if job_title == "Unknown Title":
                nlp_title = clean_title(extract_job_title_nlp(body))
                invalid_fragments = ["joinrs ai", "unsubscribe", "privacy policy"]
                if is_valid_title(nlp_title) and not any(frag in nlp_title.lower() for frag in invalid_fragments):
                    job_title = nlp_title
                else:
                    fallback_subject_title = subject.split(":")[1] if ":" in subject else subject
                    fallback_subject_title = clean_title(fallback_subject_title.strip())
                    if is_valid_title(fallback_subject_title):
                        job_title = fallback_subject_title
                    else:
                        with open("skipped_titles.log", "a") as log:
                            log.write(f"❌ Skipped: Unknown title\nSubject: {subject}\nSender: {sender}\n\nPreview:\n{body[:300]}\n\n---\n\n")
                        continue

            print(f"🧠 NLP Fallback Title: {job_title}")
            if job_title.lower().startswith("keep track of") or len(job_title.split()) < 1:
                print("🚫 Skipping vague entry based on job title.")
                continue

            company = extract_company_name(body, sender)
            print(f"🔎 Extracted Title: {job_title}")
            print(f"🏢 Extracted Company: {company}")

            result = hybrid_classify_email(subject, body, sender)
            if result is None:
                print("🟡 Hybrid classifier returned None. Marking as Uncertain.")
                uncertain.append((job_title, company, date_str, "Uncertain", body))
                continue
            status, classifier_confidence = result

        # 🧠 Fallback override if keywords clearly show outcome
            body_lower = body.lower()

            # Rejection takes priority
            if any(kw in body_lower for kw in [
                "move forward with other candidates",
                "we regret to inform you",
                "unfortunately we will not",
                "we have decided not to move forward",
                "we will not be moving forward with your application",
                "not selected",
                "position has been filled"
            ]):
                print("❌ Detected strong keyword pattern for 'Rejected'. Overriding status to Rejected.")
                status = "Rejected"

            # Only override to 'Applied' if not already set to Rejected
            elif not status or status == "Uncertain":
                if any(kw in body_lower for kw in [
                    "your application has been submitted",
                    "thank you for applying",
                    "we received your application",
                    "application received",
                    "we’ve received your application"
                ]):
                    print("✅ Detected strong keyword pattern for 'Applied'. Overriding status to In Progress.")
                    status = "In Progress"

            # Final fallback
            if not status:
                print("🟡 Could not confidently classify. Marking as Uncertain.")
                uncertain.append((job_title, company, date_str, "Uncertain", body))
            elif status == "Rejected":
                rejected.append((job_title, company, date_str, "Rejected", body))
            elif status == "In Progress":
                applied.append((job_title, company, date_str, "In Progress", body))
                

        print(f"✅ Completed batch {i + 1}/{len(chunks)}\n")
        time.sleep(2)

    # 🧹 Deduplicate
    applied = deduplicate(applied)
    rejected = deduplicate(rejected)
    uncertain = deduplicate(uncertain)

    # ✅ Sort after deduplication
    applied.sort(key=lambda x: parsedate_to_datetime(x[2]), reverse=True)
    rejected.sort(key=lambda x: parsedate_to_datetime(x[2]), reverse=True)
    uncertain.sort(key=lambda x: parsedate_to_datetime(x[2]), reverse=True)
    

    applied_html = build_html_page("Applied Companies", applied)
    with open("templates/applied.html", "w", encoding="utf-8") as f:
        f.write(applied_html)

    rejected_html = build_html_page("Rejected Companies", rejected)
    with open("templates/rejected.html", "w", encoding="utf-8") as f:
        f.write(rejected_html)

    uncertain_html = build_html_page("Uncertain Applications", uncertain)
    with open("templates/uncertain.html", "w", encoding="utf-8") as f:
        f.write(uncertain_html)

    print("📁 Current save location:", os.getcwd())    

    print("✅ HTML files updated.")  

    with open(status_path, 'w') as f:
        json.dump({
            "applied_count": len(applied),
            "rejected_count": len(rejected),
            "uncertain_count": len(uncertain)
        }, f, indent=2)

        

    print(f"✅ Done! Total scanned: {fetched} | Applied: {len(applied)} | Rejected: {len(rejected)}")