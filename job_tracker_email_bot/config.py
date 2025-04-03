import os
import json
from email.utils import parsedate_to_datetime


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

status_path = os.path.join(base_dir, 'status.json')
applied_path = os.path.join(base_dir, 'templates', 'applied.html')
rejected_path = os.path.join(base_dir, 'templates', 'rejected.html')
uncertain_path = os.path.join(base_dir, 'templates', 'uncertain.html')

# Initialize `status.json` if missing
if not os.path.exists(status_path):
    with open(status_path, 'w') as f:
        json.dump({"applied_count": 0, "rejected_count": 0}, f)

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