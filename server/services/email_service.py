import os
import base64
import re
from datetime import datetime
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class GmailService:
    def __init__(self, user_id=None, access_token=None, refresh_token=None, token_expiry=None):
        self.user_id = user_id
        self.service = None
        self.processed_emails = set()
        
        self.client_id = os.getenv('GMAIL_CLIENT_ID')
        self.client_secret = os.getenv('GMAIL_CLIENT_SECRET')
        self.redirect_uri = f'{os.getenv("BACKEND_URL", "http://localhost")}:{os.getenv("BACKEND_PORT", "5000")}/auth/callback'
        
        if not self.client_id or not self.client_secret:
            raise ValueError("GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET required")
        
        self.credentials = self._build_credentials(access_token, refresh_token, token_expiry)
        if self.credentials:
            self.service = build('gmail', 'v1', credentials=self.credentials)

    def _build_credentials(self, access_token, refresh_token, token_expiry):
        if not access_token or not refresh_token:
            return None
        try:
            expiry = datetime.fromisoformat(token_expiry.replace('Z', '+00:00')) if isinstance(token_expiry, str) else token_expiry
            creds = Credentials(access_token, refresh_token, 'https://oauth2.googleapis.com/token', 
                              self.client_id, self.client_secret, SCOPES, expiry=expiry)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return creds
        except:
            return None

    def _get_oauth_config(self):
        return {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }

    def get_authorization_url(self):
        try:
            flow = Flow.from_client_config(self._get_oauth_config(), scopes=SCOPES)
            flow.redirect_uri = self.redirect_uri
            url, _ = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')
            return url
        except:
            return None

    def authenticate_with_code(self, authorization_code):
        try:
            flow = Flow.from_client_config(self._get_oauth_config(), scopes=SCOPES)
            flow.redirect_uri = self.redirect_uri
            flow.fetch_token(code=authorization_code)
            self.credentials = flow.credentials
            self.service = build('gmail', 'v1', credentials=self.credentials)
            
            try:
                profile = self.service.users().getProfile(userId='me').execute()
                email_address = profile['emailAddress']
                print(f"✅ Gmail connected for {email_address}")
                return True, email_address
            except:
                print("✅ Gmail connected for authenticated-user@gmail.com")
                return True, "authenticated-user@gmail.com"
        except Exception as e:
            return False, str(e)

    def is_authenticated(self):
        return self.service is not None

    def get_user_email(self):
        if not self.service:
            return None
        try:
            return self.service.users().getProfile(userId='me').execute()['emailAddress']
        except:
            return None

    def list_messages(self, query='is:unread', max_results=10):
        if not self.service:
            return []
        try:
            return self.service.users().messages().list(userId='me', q=query, maxResults=max_results).execute().get('messages', [])
        except:
            return []

    def get_message(self, msg_id):
        if not self.service:
            return None
        try:
            return self.service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        except:
            return None

    def extract_email_details(self, message):
        try:
            headers = {h['name']: h['value'] for h in message['payload'].get('headers', [])}
            return {
                'id': message['id'],
                'subject': headers.get('Subject', 'No Subject'),
                'sender': headers.get('From', 'Unknown Sender'),
                'body': self._extract_body_content(message['payload']),
                'thread_id': message.get('threadId'),
                'date': headers.get('Date', '')
            }
        except:
            return {'id': message.get('id', ''), 'subject': 'Error', 'sender': 'Error', 'body': '', 'thread_id': '', 'date': ''}

    def _extract_body_content(self, payload):
        try:
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                        return self._decode_base64(part['body']['data'])[:1000]
                    elif part['mimeType'] == 'text/html' and 'data' in part['body']:
                        return re.sub('<[^<]+?>', '', self._decode_base64(part['body']['data']))[:1000]
            elif 'body' in payload and 'data' in payload['body']:
                content = self._decode_base64(payload['body']['data'])
                if payload['mimeType'] == 'text/html':
                    content = re.sub('<[^<]+?>', '', content)
                return content[:1000]
            return ""
        except:
            return ""

    def _decode_base64(self, data):
        try:
            return base64.urlsafe_b64decode(data).decode('utf-8')
        except:
            return ""

    def get_recent_emails(self, max_results=50):
        if not self.service:
            return []
        try:
            keywords = ['interview', 'application', 'position', 'role', 'candidate', 'hiring', 'recruitment', 'job', 'career', 'opportunity', 'hr', 'human resources', 'talent', 'recruiter']
            query = f"({' OR '.join([f'\"{k}\"' for k in keywords])}) AND newer_than:7d"
            
            messages = self.list_messages(query=query, max_results=max_results)
            emails = []
            
            for message in messages:
                if message['id'] not in self.processed_emails:
                    full_message = self.get_message(message['id'])
                    if full_message:
                        emails.append(self.extract_email_details(full_message))
                        self.processed_emails.add(message['id'])
            
            return emails
        except:
            return []

    def get_credentials_dict(self):
        if not self.credentials:
            return None
        return {
            'access_token': self.credentials.token,
            'refresh_token': self.credentials.refresh_token,
            'token_expiry': self.credentials.expiry.isoformat() if self.credentials.expiry else None,
            'client_id': self.credentials.client_id,
            'client_secret': self.credentials.client_secret
        } 