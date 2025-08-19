from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from flask_socketio import SocketIO, emit, disconnect
from datetime import datetime
import os
from dotenv import load_dotenv
from services.email_monitor import initialize_monitor, get_monitor
from utils import db

load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*")

current_user_id = None

applications = []
app_counter = [1]
email_monitor = initialize_monitor(applications, app_counter)

# Set up real-time broadcast callbacks for email monitor
email_monitor.set_broadcast_callbacks(
    broadcast_callback=lambda: broadcast_applications_update(),
    new_app_callback=lambda company, position, stage: broadcast_new_application(company, position, stage)
)

def create_app(company, position, stage):
    app_dict = {
        "id": app_counter[0],
        "company": company,
        "position": position,
        "stage": stage,
        "date_added": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    app_counter[0] += 1
    return app_dict

@app.route("/api/applications", methods=["GET"])
def get_applications():
    grouped = {"Applied": [], "Interview": [], "Offer": [], "Rejected": []}
    for app in applications:
        if (stage := app.get("stage", "Applied")) in grouped:
            grouped[stage].append(app)
    return jsonify(grouped)

@app.route("/api/applications", methods=["POST"])
def add_application():
    data = request.get_json()
    if not data or not data.get("company") or not data.get("position"):
        return jsonify({"error": "Company and position are required"}), 400
    
    company, position, stage = data["company"], data["position"], data.get("stage", "Applied")
    existing = next((app for app in applications if 
                    app["company"].lower() == company.lower() and 
                    app["position"].lower() == position.lower()), None)
    
    if existing:
        existing.update({"stage": stage, "date_added": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        if current_user_id:
            db.save_application(current_user_id, company, position, stage)
        return jsonify({"message": "Application updated", "application": existing})
    
    new_app = create_app(company, position, stage)
    applications.append(new_app)
    if current_user_id:
        db.save_application(current_user_id, company, position, stage)
    
    # Broadcast real-time update
    broadcast_applications_update()
    return jsonify({"message": "Application added", "application": new_app})

@app.route("/api/applications/<int:app_id>", methods=["PUT"])
def update_application(app_id):
    data = request.get_json()
    if not (stage := data.get("stage")) or stage not in ["Applied", "Interview", "Offer", "Rejected"]:
        return jsonify({"error": "Valid stage required"}), 400
    
    if not (app := next((app for app in applications if app["id"] == app_id), None)):
        return jsonify({"error": "Application not found"}), 404
    
    app.update({"stage": stage, "date_added": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    if current_user_id:
        db.save_application(current_user_id, app["company"], app["position"], stage)
    
    # Broadcast real-time update
    broadcast_applications_update()
    return jsonify({"message": "Application updated", "application": app})

@app.route("/api/applications/<int:app_id>", methods=["DELETE"])
def delete_application(app_id):
    global applications
    applications = [app for app in applications if app["id"] != app_id]
    if current_user_id:
        try:
            db.cursor.execute("DELETE FROM applications WHERE id=? AND user_id=?", (app_id, current_user_id))
            db.conn.commit()
        except:
            pass
    
    # Broadcast real-time update
    broadcast_applications_update()
    return jsonify({"message": "Application deleted"})

def error_page(title, message):
    return f'<html><body style="font-family:Arial;text-align:center;padding:50px;"><h1>{title}</h1><p>{message}</p><a href="{os.getenv("FRONTEND_URL", "http://localhost")}:{os.getenv("FRONTEND_PORT", 8501)}" style="color:#4285f4;">Return to WheresMyJobAt</a></body></html>'

@app.route("/api/gmail/auth-url", methods=["GET"])
def get_gmail_auth_url():
    try:
        if not (monitor := get_monitor()):
            return jsonify({"error": "Email monitor not initialized"}), 500
        return jsonify({"auth_url": auth_url}) if (auth_url := monitor.get_auth_url()) else (jsonify({"error": "Failed to get authorization URL"}), 500)
    except:
        return jsonify({"error": "OAuth not configured"}), 500

@app.route("/auth/callback", methods=["GET"])
def gmail_oauth_callback():
    if error := request.args.get('error'):
        return error_page("❌ OAuth Error", f"Error: {error}")
    if not (auth_code := request.args.get('code')):
        return error_page("❌ OAuth Error", "No authorization code received")
    
    try:
        if not (monitor := get_monitor()):
            return error_page("❌ Error", "Email monitor not available")
        
        success, result = monitor.authenticate_with_code(auth_code)
        if success:
            try:
                import threading
                global current_user_id
                current_user_id = db.ensure_user(result)
                monitor.set_current_user(current_user_id)  # Set user ID on monitor for DB operations
                applications.clear()
                loaded_apps = db.get_user_applications(current_user_id)
                print(f"✅ Loaded {len(loaded_apps)} applications from DB for {result}")
                for app in loaded_apps:
                    print(f"  • {app['company']} - {app['position']} ({app['stage']})")
                applications.extend(loaded_apps)
                app_counter[0] = max([a['id'] for a in applications], default=0) + 1
                monitor.set_applications_ref(applications, app_counter)
                
                # Re-establish broadcast callbacks after authentication
                monitor.set_broadcast_callbacks(
                    broadcast_callback=lambda: broadcast_applications_update(),
                    new_app_callback=lambda company, position, stage: broadcast_new_application(company, position, stage)
                )

                threading.Timer(1.0, lambda: monitor.start_monitoring()).start()
            except:
                pass
            return redirect(f'{os.getenv("FRONTEND_URL", "http://localhost")}:{os.getenv("FRONTEND_PORT", 8501)}?auth=success')
        return error_page("❌ Authentication Failed", f"Error: {result}")
    except Exception as e:
        return error_page("❌ Authentication Error", f"Something went wrong: {str(e)}")

@app.route("/api/monitor/status", methods=["GET"])
def get_monitor_status():
    if monitor := get_monitor():
        status = monitor.get_status()
        status['total_applications'] = len(applications)
        return jsonify(status)
    return jsonify({'is_running': False, 'gmail_connected': False, 'gmail_email': None, 'gemini_available': False, 'processed_emails': 0, 'check_interval': 1, 'total_applications': len(applications)})

@app.route("/api/monitor/scan", methods=["POST"])
def manual_scan():
    if (monitor := get_monitor()) and monitor.manual_scan():
        # Broadcast update after manual scan in case new applications were found
        broadcast_applications_update()
        return jsonify({"message": "Manual scan completed"})
    return jsonify({"error": "Manual scan failed or monitoring not running"}), 400

@app.route("/api/monitor/stop", methods=["POST"])
def stop_monitoring():
    if monitor := get_monitor():
        monitor.stop_monitoring()
        return jsonify({"message": "Email monitoring stopped"})
    return jsonify({"error": "Monitor not available"}), 400

@app.route("/api/analyze-email", methods=["POST"])
def analyze_email():
    try:
        data = request.get_json()
        if not (subject := data.get('email_subject', '')) and not (body := data.get('email_body', '')):
            return jsonify({"error": "Email subject or body is required"}), 400
        
        from utils.gemini_analyzer import GeminiEmailAnalyzer
        result = GeminiEmailAnalyzer().analyze_email_for_interview_stage(subject, body, "")
        
        company, job, stage, confidence = result.get('company_name'), result.get('job_title'), result.get('interview_stage'), result.get('confidence', 0)
        stage_map = {'application_received': 'Applied', 'phone_screen': 'Interview', 'technical_interview': 'Interview', 'behavioral_interview': 'Interview', 'final_interview': 'Interview', 'offer': 'Offer', 'rejected': 'Rejected'}
        dashboard_stage = stage_map.get(stage, 'Applied')
        
        if confidence >= 30 and company and job:
            existing = next((app for app in applications if app["company"].lower() == company.lower() and app["position"].lower() == job.lower()), None)
            
            if not existing:
                applications.append(create_app(company, job, dashboard_stage))
                if current_user_id:
                    db.save_application(current_user_id, company, job, dashboard_stage)
                message = "Email analyzed and application added automatically"
                # Broadcast real-time update for manual analysis
                broadcast_new_application(company, job, dashboard_stage)
                broadcast_applications_update()
            else:
                stage_order = ['Applied', 'Interview', 'Offer', 'Rejected']
                if stage_order.index(dashboard_stage) > stage_order.index(existing.get('stage', 'Applied')) or dashboard_stage == 'Rejected':
                    existing.update({'stage': dashboard_stage, 'date_added': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                    if current_user_id:
                        db.save_application(current_user_id, company, job, dashboard_stage)
                    message = "Email analyzed and existing application updated"
                    # Broadcast real-time update for manual analysis
                    broadcast_applications_update()
                else:
                    message = "Email analyzed but no update needed"
            
            return jsonify({"message": message, "analysis": result, "added_to_dashboard": True})
        
        return jsonify({"message": "Email analyzed but not added to dashboard (low confidence or missing info)", "analysis": result, "added_to_dashboard": False})
        
    except ImportError:
        return jsonify({"error": "Gemini analyzer not available"}), 500
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"})

# WebSocket events for real-time updates
@socketio.on('connect')
def handle_connect():
    print('Client connected for real-time updates')
    emit('status', {'message': 'Connected to real-time updates'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected from real-time updates')

def broadcast_applications_update():
    """Broadcast application updates to all connected clients"""
    try:
        grouped = {"Applied": [], "Interview": [], "Offer": [], "Rejected": []}
        for app in applications:
            if (stage := app.get("stage", "Applied")) in grouped:
                grouped[stage].append(app)
        socketio.emit('applications_updated', grouped)
        print(f"📡 Broadcasted application update to connected clients")
    except Exception as e:
        print(f"❌ Error broadcasting update: {e}")

def broadcast_new_application(company, position, stage):
    """Broadcast when a new application is detected from email"""
    try:
        socketio.emit('new_application_detected', {
            'company': company,
            'position': position, 
            'stage': stage,
            'timestamp': datetime.now().isoformat()
        })
        print(f"🔔 Broadcasted new application: {company} - {position} ({stage})")
    except Exception as e:
        print(f"❌ Error broadcasting new application: {e}")

if __name__ == "__main__":
    if missing := [v for v in ['GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET', 'GEMINI_API_KEY'] if not os.getenv(v) or os.getenv(v).strip() in ['', "''"]]:
        print(f"❌ Missing environment variables: {', '.join(missing)}\n💡 Set all required variables in .env file")
        exit(1)
    
    print("✅ All required environment variables configured")
    port = int(os.getenv("PORT", 5000))  # Use .env PORT or fallback to 5000
    socketio.run(app, port=port, debug=False)

