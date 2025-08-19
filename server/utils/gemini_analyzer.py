import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class GeminiEmailAnalyzer:
    
    def __init__(self):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key or api_key.strip() == '' or api_key.strip() == "''":
            raise ValueError("❌ GEMINI_API_KEY environment variable is required and cannot be empty. Please set it in the .env file.")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def analyze_email_for_interview_stage(self, subject, body, sender_email=""):
        prompt = f"""
        Analyze this email and extract job application information:
        
        Subject: {subject}
        Body: {body}
        Sender: {sender_email}
        
        Extract the following information:
        1. Company name
        2. Job title/position
        3. Interview stage (choose from: application_received, phone_screen, technical_interview, 
           behavioral_interview, final_interview, offer, rejected, other)
        4. Confidence level (0-100) based on how certain you are
        
        Return the response in this exact JSON format:
        {{
            "company_name": "extracted company name or null",
            "job_title": "extracted job title or null", 
            "interview_stage": "stage or null",
            "confidence": confidence_score
        }}
        
        Only return the JSON, no other text.
        """
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            import json
            import re
            
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1).strip()
            
            result = json.loads(result_text)
            
            def clean_value(value):
                return None if value in [None, 'null', ''] else (value.strip() if isinstance(value, str) else value)
            
            return {
                'company_name': clean_value(result.get('company_name')),
                'job_title': clean_value(result.get('job_title')),
                'interview_stage': clean_value(result.get('interview_stage')),
                'confidence': int(result.get('confidence', 0))
            }
            
        except Exception as e:
            print(f"❌ Gemini analysis error: {e}")
            return {
                'company_name': None,
                'job_title': None,
                'interview_stage': None,
                'confidence': 0
            }


def main():
    """Test function to check if Gemini API key is working"""
    print("🔍 Testing Gemini API key...")
    print("=" * 50)
    
    try:
        # Test API key loading
        api_key = os.getenv('GEMINI_API_KEY')
        print(f"📋 API Key found: {'✅ Yes' if api_key else '❌ No'}")
        if api_key:
            print(f"📋 API Key format: {api_key[:10]}...{api_key[-10:] if len(api_key) > 20 else api_key}")
        
        # Test analyzer initialization
        analyzer = GeminiEmailAnalyzer()
        print("✅ GeminiEmailAnalyzer initialized successfully")
        
        # Test with sample email
        test_subject = "Interview Invitation - Software Engineer Position at TechCorp"
        test_body = "Dear Candidate, We would like to invite you for a technical interview for the Software Engineer position at TechCorp. Please reply with your availability."
        test_sender = "hr@techcorp.com"
        
        print("\n🧪 Testing with sample email:")
        print(f"Subject: {test_subject}")
        print(f"Sender: {test_sender}")
        
        result = analyzer.analyze_email_for_interview_stage(test_subject, test_body, test_sender)
        
        print("\n📊 Analysis Result:")
        print(f"Company: {result.get('company_name', 'N/A')}")
        print(f"Job Title: {result.get('job_title', 'N/A')}")
        print(f"Interview Stage: {result.get('interview_stage', 'N/A')}")
        print(f"Confidence: {result.get('confidence', 0)}%")
        
        if result.get('confidence', 0) > 0:
            print("\n✅ SUCCESS: Gemini API key is working correctly!")
        else:
            print("\n⚠️ WARNING: API key works but analysis returned low confidence")
            
    except ValueError as e:
        print(f"❌ CONFIGURATION ERROR: {e}")
    except Exception as e:
        print(f"❌ API ERROR: {e}")
        print("   This could be due to:")
        print("   - Invalid API key")
        print("   - Quota exceeded")
        print("   - Network issues")
        print("   - API service issues")
    
    print("=" * 50)


if __name__ == "__main__":
    main()
