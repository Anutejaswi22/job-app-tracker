import os
import io
import json
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2 import id_token
import requests
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
import firebase_admin
from flask import Response
from firebase_admin import credentials as firebase_credentials, auth as firebase_auth

from job_tracker_email_bot.gmail_utils import authenticate_gmail
from job_tracker_email_bot.processor import get_job_emails
from job_tracker_email_bot.builder import build_html_page
from job_tracker_email_bot.config import applied_path, rejected_path, status_path

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SESSION_SECRET')  # 🔐 Use a secure key in production
app.permanent_session_lifetime = timedelta(minutes=10)

# 🔁 Ensure session persists for defined time
@app.before_request
def make_session_permanent():
    session.permanent = True

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

@app.route('/')
def home():
    if 'credentials' in session and 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route("/authorize")
def authorize():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                "redirect_uris": [url_for('oauth2callback', _external=True)],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    auth_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    state = session['state']
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                "redirect_uris": [url_for('oauth2callback', _external=True)],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    id_info = id_token.verify_oauth2_token(
        credentials.id_token,
        requests.Request(),
        credentials.client_id
    )
    session['user'] = {
        'name': id_info.get('name', ''),
        'email': id_info.get('email', ''),
        'picture': id_info.get('picture', ''),
        'locale': id_info.get('locale', ''),
        'gender': id_info.get('gender', 'Not provided'),
        'theme': 'dark',
        'email_alerts': False
    }

    return redirect(url_for('dashboard'))

@app.route('/scan_now')
def scan_now():
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    get_job_emails(service, max_emails=50)
    session['recent_activity'] = "✅ Scanning completed successfully."
    return redirect(url_for('home'))

@app.route('/scan_range')
def scan_range():
    from_date = request.args.get("from")
    to_date = request.args.get("to")

    if not from_date or not to_date:
        return "Invalid date range", 400

    after_ts = int(datetime.strptime(from_date, "%Y-%m-%d").timestamp())
    before_ts = int(datetime.strptime(to_date, "%Y-%m-%d").timestamp())

    creds = authenticate_gmail()
    service = build("gmail", "v1", credentials=creds)

    get_job_emails(service, max_emails=50, after=after_ts, before=before_ts, filter_by_date=True)
    return redirect(url_for("home"))

@app.route('/status.json')
def status():
    if os.path.exists(status_path):
        return send_file(status_path)
    else:
        return {"applied_count": 0, "rejected_count": 0}

@app.route('/applied')
def applied():
    if 'credentials' in session:
        return render_template('applied.html')
    return redirect(url_for('login'))

@app.route('/rejected')
def rejected():
    if 'credentials' in session:
        return render_template('rejected.html')
    return redirect(url_for('login'))

@app.route('/uncertain')
def show_uncertain():
    if 'credentials' in session:
        return render_template('uncertain.html')
    return redirect(url_for('login'))

@app.route('/gmail-login')
def gmail_login():
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    print("🔐 Checking session credentials:", session.get('credentials'))

    if 'credentials' in session and 'user' in session:
        if not os.path.exists(status_path):
            with open(status_path, 'w') as f:
                json.dump({"applied_count": 0, "rejected_count": 0}, f)

        with open(status_path) as f:
            data = json.load(f)
        return render_template("index.html", applied=data["applied_count"], rejected=data["rejected_count"], user=session.get('user'))

    return redirect(url_for('login'))


# ✅ Initialize Firebase Admin (run this once during app startup)
if not firebase_admin._apps:
    cred = firebase_credentials.Certificate("/etc/secrets/firebase-adminsdk.json")
    firebase_admin.initialize_app(cred)

@app.route('/sessionLogin', methods=['POST'])
def session_login():
    data = request.get_json()
    id_token = data.get("idToken")
    print("🪪 Received ID token:", id_token[:20], "...")
    try:
        # 🔐 Verify the ID token received from frontend
        decoded_token = firebase_auth.verify_id_token(id_token)
        email = decoded_token['email']

        session['credentials'] = {
            'logged_in': True,
            'user_email': email
        }

        session['user'] = {
            'email': email,
            'name': data.get('name'),
            'picture': data.get('picture'),
            'gender': data.get('gender', 'Not provided'),
            'locale': data.get('locale', 'en'),
            'theme': data.get('theme', 'dark'),
            'email_alerts': data.get('email_alerts', False)
        }

        print("✅ Firebase token verified & session set for:", session['user'])
        return '', 200

    except Exception as e:
        print("❌ Firebase token verification failed:", str(e))
        return 'Unauthorized', 401

@app.route('/logout')
def logout():
    session.pop('credentials', None)
    session.pop('user', None)
    return redirect(url_for('home'))

@app.route("/profile")
def profile():
    if 'credentials' not in session or 'user' not in session:
        return redirect(url_for("login"))
    return render_template("profile.html", user=session["user"])

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user' not in session:
        return redirect('/login')
    session['user']['locale'] = request.form.get('locale', '')
    session['user']['gender'] = request.form.get('gender', 'Not provided')
    print("✅ Updated profile info:", session['user'])
    return redirect('/profile?updated=true')

@app.route('/settings')
def settings():
    if 'credentials' in session and 'user' in session:
        return render_template('settings.html', user=session['user'])
    return redirect(url_for('login'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user' not in session:
        return redirect('/login')

    session['user']['name'] = request.form.get('displayName')
    session['user']['theme'] = request.form.get('theme')
    session['user']['email_alerts'] = 'email_alerts' in request.form

    print("✅ Updated settings:", session['user'])
    return redirect('/settings')

@app.route('/clear')
def clear():
    session.clear()
    return redirect(url_for('home'))

@app.context_processor
def inject_user():
    return {'user': session.get('user')}

@app.route('/view_email/<email_id>')
def view_email(email_id):
    try:
        path = os.path.join('job_tracker_email_bot', 'static', 'uncertain_emails', f'{email_id}.json')
        with open(path, 'r') as f:
            email_data = json.load(f)
    except FileNotFoundError:
        return "Email not found", 404

    return render_template('view_email.html', email=email_data)

@app.route('/test-login-js')
def test_login_js():
    return send_file('static/js/login.js')


@app.route('/firebase-config')
def firebase_config():
    with open('/etc/secrets/firebase-config.js', 'r') as f:
        js_code = f.read()
    return Response(js_code, mimetype='application/javascript')    

if __name__ == '__main__':
    app.run(debug=True)