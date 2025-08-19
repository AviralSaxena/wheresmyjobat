# WheresMyJobAt - Auto Job Application Tracker

Automatically tracks job applications from Gmail using AI analysis.

## Setup

1. **Get API Keys**
   
   **Gmail OAuth Setup:**
   - Go to [Google Cloud Console](https://console.developers.google.com)
   - Create a new project or select existing one
   - Enable the Gmail API (APIs & Services → Library → search "Gmail API")
   - Go to Credentials → Create Credentials → OAuth 2.0 Client IDs
   - copy the `Client ID` and `Client Secret` values.
   
   **Gemini AI Setup:**
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Click "Create API Key" 
   - Copy the generated API key

2. **Configure**
   ```bash
   cp .env-example .env
   # Edit .env with your API keys
   ```

3. **Run**
   ```bash
   python setup_and_run.py
   # Or python3 setup_and_run.py
   ```

The script handles everything - virtual environment, dependencies, and launches both frontend and backend.

**Heads-up:** The very first run can take some time (**5-10 minutes**) because the script creates the virtual environment and pulls down large Python packages. Please be patient—subsequent runs would be instant.

Access at: http://localhost:8501