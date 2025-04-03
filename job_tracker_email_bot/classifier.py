# job_tracker_email_bot/classifier.py

from transformers import pipeline
import re
import json
from collections import defaultdict
from job_tracker_email_bot.config import applied_keywords, rejected_keywords

classifier = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")

def hybrid_classify_email(subject, body, sender=None):
    keyword_result = classify_email(subject, body)
    ai_result, confidence = classify_email_with_ai(subject, body)

    print(f"🔍 Hybrid — Keywords: {keyword_result}, AI: {ai_result}")

    if keyword_result == "Rejected":
        return "Rejected", confidence
    elif keyword_result == "In Progress":
        return "In Progress", confidence
    elif ai_result == "In Progress":
        return "In Progress", confidence
    elif ai_result == "Rejected":
        print("⚠️ AI alone labeled as Rejected, ignoring as uncertain.")
        return None, confidence

    promo_phrases = ['apply now', 'is hiring', 'new jobs in', 'job alert', 'view jobs', 'check out']
    if any(p in subject.lower() for p in promo_phrases):
        print("🚫 Ignoring promotional email (detected by subject patterns).")
        return None, confidence

    if ai_result:
        return ai_result, confidence
    if keyword_result:
        return keyword_result, confidence

    with open("uncertain_emails.log", "a") as log:
        log.write(f"🟡 UNCERTAIN EMAIL:\nSubject: {subject}\nSender: {sender}\nBody Preview:\n{body[:300]}\n\n---\n\n")
    return None, confidence

def classify_email_with_ai(subject, body):
    content = f"{subject}\n{body}".strip()
    try:
        result = classifier(content, truncation=True, max_length=512)[0]
        label = result['label']
        score = result['score']
        print(f"🤖 AI label: {label} | Confidence: {score:.2f}")

        if score >= 0.85:
            return ("Rejected" if label == "NEGATIVE" else "In Progress"), score
    except Exception as e:
        print(f"⚠️ AI classification failed: {e}")
    return None, 0.0

def is_job_related(subject, sender, body):
    job_keywords = [
        'applied', 'application', 'job opportunity', 'job application', 'job opening',
        'interview', 'hiring', 'recruiter', 'resume', 'cv', 'your application',
        'thank you for applying', 'we regret to inform', 'not been selected'
    ]

    sender_domains = [
        'workday', 'indeed', 'jobvite', 'greenhouse', 'linkedin',
        'smartrecruiters', 'ziprecruiter', 'glassdoor', 'lever', 'successfactors',
        'ibm', 'amazon', 'oracle', 'accenture', 'deloitte', 'taleo'
    ]

    spam_phrases = [
        'delivery', 'discount', 'deal', 'store', 'invoice', 'offer', 'free',
        'your order', 'popular restaurants', 'mix and match', 'get expert support',
        'fire your resume writer', 'intellisearch alert', 'recommended jobs', 'job matches', 'check out these jobs', 
        'hot jobs','check out these jobs', 'view all recommended jobs', 'daily job alert', 'resume viewed', 
        'search results', 'we found jobs for you'
    ]

    subject_lower = subject.lower()
    body_lower = body.lower()
    sender_lower = sender.lower()

    sender_email = re.search(r'<([^>]+)>', sender)
    sender_email = sender_email.group(1) if sender_email else sender
    sender_domain = sender_email.split('@')[-1].lower()

    if any(domain in sender_domain for domain in sender_domains):
      return True

    spam_hits = sum(1 for spam in spam_phrases if spam in subject_lower or spam in body_lower)
    if spam_hits >= 2:
        return False

    vague_subjects = [
        "keep track of your", "check the status of", "track your", 
        "we found jobs", "we matched you with", "based on your profile"
    ]
    if any(v in subject_lower for v in vague_subjects):
        return False

    if 'glassdoor.com' in sender_lower:
        promo_subject_patterns = ['is hiring', 'jobs in', 'apply now', 'for you', 'check out', 'job alert']
        if any(p in subject_lower for p in promo_subject_patterns):
            return False

    if any(domain in sender_lower for domain in sender_domains):
        return True
    if any(kw in subject_lower for kw in job_keywords):
        return True
    if any(kw in body_lower for kw in job_keywords):
        return True

    return False

def classify_email(subject, body):
    subject = subject.lower()
    body = body.lower()
    
    # Check for keywords in both subject and body
    contains_applied = any(k in subject or k in body for k in applied_keywords)
    contains_rejected = any(k in subject or k in body for k in rejected_keywords)

    # If both are present, it's a rejection
    if contains_rejected:
        return 'Rejected'
    elif contains_applied:
        return 'Applied'
    else:
        return 'Uncertain'

# Suppose this is your parsed list of emails
emails = [
    {"subject": "Your IBM Application Status", "body": "We regret to inform you...", "job_title": "Research Engineer", "company": "IBM", "date": "Mar 27, 2025"},
    {"subject": "We received your application", "body": "Thank you for applying to IBM", "job_title": "Research Engineer", "company": "IBM", "date": "Mar 25, 2025"},
    {"subject": "RE: Intel Corporation Full Time Opportunity", "body": "Thanks for applying", "job_title": "SDE", "company": "Intel", "date": "Mar 26, 2025"},
    {"subject": "RE: Intel Corporation Full Time Opportunity", "body": "Let’s schedule a call", "job_title": "SDE", "company": "Intel", "date": "Mar 27, 2025"},
]

# 🧠 Deduplicate and prioritize Rejected
classified = defaultdict(dict)

for email in emails:
    status = classify_email(email["subject"], email["body"])
    key = (email["job_title"].strip().lower(), email["company"].strip().lower())

    # Prioritize rejected if both applied and rejected exist
    if key not in classified:
        classified[key] = {**email, "status": status}
    else:
        existing = classified[key]["status"]
        if existing == "Applied" and status == "Rejected":
            classified[key] = {**email, "status": status}
        # Otherwise, keep the existing one (Rejected preferred)

# ✅ Final result
applied_jobs = [v for v in classified.values() if v["status"] == "Applied"]
rejected_jobs = [v for v in classified.values() if v["status"] == "Rejected"]
uncertain_jobs = [v for v in classified.values() if v["status"] == "Uncertain"]

# 🔍 Print or use these in your HTML rendering
print("Applied:", applied_jobs)
print("Rejected:", rejected_jobs)
print("Uncertain:", uncertain_jobs)
