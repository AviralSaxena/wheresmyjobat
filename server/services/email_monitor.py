import threading
import time
from .email_service import GmailService
import os
from datetime import datetime

try:
    from utils.gemini_analyzer import GeminiEmailAnalyzer
except ImportError:
    GeminiEmailAnalyzer = None

class EmailMonitor:
    
    def __init__(self, applications_list=None):
        self.email_service = GmailService()
        self.is_running = False
        self.monitor_thread = None
        self.check_interval = 1
        self.processed_emails = 0
        self.applications = applications_list or []
        self.app_counter_ref = None
        self.consecutive_errors = 0
        self.last_activity_time = 0
        self.dynamic_interval = 1  # Start with 1 second
        self.broadcast_callback = None  # Will be set by app.py
        self.new_app_callback = None   # Will be set by app.py
        self.current_user_id = None    # Will be set when user authenticates
        
        self.analyzer = None
        if GeminiEmailAnalyzer and os.getenv('GEMINI_API_KEY'):
            try:
                self.analyzer = GeminiEmailAnalyzer()
            except:
                pass
    
    def set_applications_ref(self, applications_list, app_counter_ref):
        self.applications = applications_list
        self.app_counter_ref = app_counter_ref
        
    def set_broadcast_callbacks(self, broadcast_callback, new_app_callback):
        """Set callbacks for real-time broadcasting"""
        self.broadcast_callback = broadcast_callback
        self.new_app_callback = new_app_callback
        
    def set_current_user(self, user_id):
        """Set the current user ID for database operations"""
        self.current_user_id = user_id
        
    def get_auth_url(self):
        return self.email_service.get_authorization_url()
    
    def authenticate_with_code(self, auth_code):
        return self.email_service.authenticate_with_code(auth_code)
    
    def start_monitoring(self):
        if self.is_running or not self.email_service.is_authenticated():
            return self.is_running
        try:
            recent_msgs = self.email_service.list_messages(max_results=50)
            self.email_service.processed_emails.update({m['id'] for m in recent_msgs})
        except:
            pass

        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        return True
    
    def stop_monitoring(self):
        self.is_running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
    
    def _monitor_loop(self):
        while self.is_running:
            try:
                emails_processed = self._check_emails()
                self.consecutive_errors = 0
                
                # Smart polling: adjust interval based on activity
                if emails_processed > 0:
                    self.last_activity_time = time.time()
                    self.dynamic_interval = 0.5  # Very fast when emails are being processed
                    print(f"⚡ Processed {emails_processed} emails, using fast polling (0.5s)")
                else:
                    time_since_activity = time.time() - self.last_activity_time
                    if time_since_activity < 30:  # Active period
                        self.dynamic_interval = 1  # Fast polling for 30s after activity
                    elif time_since_activity < 120:  # Medium quiet period
                        self.dynamic_interval = 2  # Medium polling for next 2 minutes
                    else:  # Long quiet period
                        self.dynamic_interval = min(5, self.check_interval)  # Slower polling
                
                time.sleep(self.dynamic_interval)
                
            except Exception as e:
                self.consecutive_errors += 1
                wait_time = min(60, 10 * (2 ** min(self.consecutive_errors - 1, 3)))
                time.sleep(wait_time)
    
    def _check_emails(self):
        emails = self.email_service.get_recent_emails(max_results=10)
        emails_processed = 0
        for email in emails:
            if not self.is_running:
                break
            if self._process_email(email):
                emails_processed += 1
            self.processed_emails += 1
        return emails_processed
    
    def _process_email(self, email):
        if not self.analyzer:
            return False
        
        try:
            result = self.analyzer.analyze_email_for_interview_stage(
                email['subject'], email['body'], email.get('sender', '')
            )
            
            stage_mapping = {
                'application_received': 'Applied', 'phone_screen': 'Interview',
                'technical_interview': 'Interview', 'behavioral_interview': 'Interview',
                'final_interview': 'Interview', 'offer': 'Offer', 'rejected': 'Rejected'
            }
            
            confidence = result.get('confidence', 0)
            if confidence >= 30 and result.get('company_name') and result.get('job_title'):
                company = result['company_name']
                position = result['job_title']
                stage = stage_mapping.get(result.get('interview_stage'), 'Applied')
                
                was_added = self._add_or_update_application(company, position, stage)
                
                if was_added:
                    print(f"🎉 NEW APPLICATION from email: {company} - {position} ({stage})")
                    # Trigger real-time notifications
                    if self.new_app_callback:
                        self.new_app_callback(company, position, stage)
                    if self.broadcast_callback:
                        self.broadcast_callback()
                    return True
                else:
                    print(f"✅ Updated application from email: {email['subject'][:50]}...")
                    if self.broadcast_callback:
                        self.broadcast_callback()
                    return True
            else:
                print(f"📧 Analyzed email: {email['subject'][:50]}... (not added - confidence: {confidence}%)")
                return False
        except Exception as e:
            print(f"❌ Error processing email: {e}")
            return False
    
    def _add_or_update_application(self, company, position, stage):
        try:
            existing = next((app for app in self.applications if 
                           app["company"].lower() == company.lower() and 
                           app["position"].lower() == position.lower()), None)
            
            is_new_application = False
            
            if existing:
                stage_order = ['Applied', 'Interview', 'Offer', 'Rejected']
                if stage_order.index(stage) > stage_order.index(existing.get('stage', 'Applied')) or stage == 'Rejected':
                    existing['stage'] = stage
                    existing['date_added'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                app_id = self.app_counter_ref[0] if self.app_counter_ref else len(self.applications) + 1
                if self.app_counter_ref:
                    self.app_counter_ref[0] += 1
                
                self.applications.append({
                    "id": app_id, "company": company, "position": position,
                    "stage": stage, "date_added": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                is_new_application = True

            # Persist to DB (if user available)
            try:
                from utils import db
                if self.current_user_id:
                    db.save_application(self.current_user_id, company, position, stage)
                    print(f"✅ Saved application to DB: {company} - {position} ({stage})")
            except Exception as e:
                print(f"❌ Failed to save to DB: {e}")
                pass
            
            return is_new_application
        except:
            return False
    
    def manual_scan(self):
        if not self.email_service.is_authenticated():
            return False
        try:
            self._check_emails()
            return True
        except:
            return False
    
    def get_status(self):
        return {
            'is_running': self.is_running,
            'email_connected': self.email_service.is_authenticated(),
            'email_email': self.email_service.get_user_email(),
            'gemini_available': self.analyzer is not None,
            'processed_emails': self.processed_emails,
            'check_interval': self.check_interval,
            'dynamic_interval': self.dynamic_interval,
            'last_activity': self.last_activity_time
        }

_monitor_instance = None

def get_monitor():
    return _monitor_instance

def initialize_monitor(applications_list=None, app_counter_ref=None):
    global _monitor_instance
    _monitor_instance = EmailMonitor(applications_list)
    if applications_list is not None and app_counter_ref is not None:
        _monitor_instance.set_applications_ref(applications_list, app_counter_ref)
    return _monitor_instance 