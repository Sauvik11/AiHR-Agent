import flask
from flask import Flask, jsonify, render_template, request, redirect, url_for, send_from_directory
import mysql.connector
import PyPDF2
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os
from auth import get_auth_url, get_token
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# MySQL Configuration from environment variables
db_config = {
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'database': os.getenv('MYSQL_DATABASE')
}

# Debug: Print environment variables and db_config
print("Environment Variables Loaded:")
print("MYSQL_USER:", os.getenv('MYSQL_USER'))
print("MYSQL_PASSWORD:", "****" if os.getenv('MYSQL_PASSWORD') else "None")
print("MYSQL_HOST:", os.getenv('MYSQL_HOST'))
print("MYSQL_DATABASE:", os.getenv('MYSQL_DATABASE'))
print("OUTLOOK_EMAIL:", os.getenv('OUTLOOK_EMAIL'))
print("ol_CLIENT_ID:", os.getenv('ol_CLIENT_ID'))
print("ol_CLIENT_SECRET:", "****" if os.getenv('ol_CLIENT_SECRET') else "None")
print("ol_REDIRECT_URI:", os.getenv('ol_REDIRECT_URI'))
print("SCOPE:", os.getenv('SCOPE'))
print("OPENAI_API_KEY:", "****" if os.getenv('OPENAI_API_KEY') else "None")
print("OPENAI_MODEL:", os.getenv('OPENAI_MODEL', 'gpt-4o-mini'))
print("Database Configuration:", db_config)

# Validate db_config
if not all([db_config['user'], db_config['database']]):
    raise ValueError("Missing required MySQL configuration (user or database) in .env file")

# OpenAI API Configuration from environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions'

# Validate OpenAI API key
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set in .env file")

# Create a requests session with retry logic
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

# Microsoft Graph Configuration with OAuth 2.0
def connect_graph():
    try:
        # Get token
        token_result = get_token()
        access_token = token_result['access_token']
        print("Access Token Obtained:", access_token[:10] + "...")
        return access_token
    except Exception as e:
        print(f"Token acquisition failed: {str(e)}. Redirecting to auth URL.")
        return redirect(get_auth_url())

# Route to trigger OAuth authentication explicitly
@app.route('/auth/login')
def auth_login():
    print("Initiating OAuth login")
    return redirect(get_auth_url())

@app.route('/resumes/<path:filename>')
def get_resume(filename):
    return send_from_directory('resumes', filename)

# OAuth 2.0 callback route
@app.route('/oauth2/callback')
def oauth_callback():
    code = request.args.get('code')
    error = request.args.get('error_description')
    print(f"OAuth callback received with code: {code}, error: {error}")
    
    if error:
        print(f"OAuth callback error: {error}")
        return jsonify({'error': error}), 400
    if not code:
        print("OAuth callback error: No authorization code provided")
        return jsonify({'error': 'No authorization code provided'}), 400
    
    try:
        token_result = get_token(code=code)
        access_token = token_result['access_token']
        print("Access Token Obtained via Callback:", access_token[:10] + "...")
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error in OAuth callback: {str(e)}")
        return jsonify({'error': str(e)}), 500

def extract_text_from_pdf(path):
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""

def ask_openai(resume_text, user_message):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "You are an AI HR assistant. Use the following resume text to answer questions "
        "about the candidate's suitability, skills, and fit. Only use provided data. If info is missing, say 'not specified'.\n\n"
        f"Resume Context:\n{resume_text[:3000]}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.5
    }

    for _ in range(3):
        try:
            res = requests.post(OPENAI_API_URL, headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            elif res.status_code == 429:
                time.sleep(5)
            else:
                break
        except requests.RequestException:
            time.sleep(3)

    return "Unable to process request currently."

@app.route("/api/ask_ai", methods=["POST"])
def ask_ai():
    data = request.get_json()
    user_message = data.get("message", "")
    resume_path = data.get("resume_path", "")

    if not user_message or not resume_path:
        return jsonify({"response": "Missing message or resume_path"}), 400

    # Assuming resume files are stored under ./resumes/
    resume_full_path = os.path.join("resumes", os.path.basename(resume_path))

    if not os.path.isfile(resume_full_path):
        return jsonify({"response": "Resume file not found"}), 404

    resume_text = extract_text_from_pdf(resume_full_path)

    if not resume_text.strip():
        return jsonify({"response": "Unable to extract text from resume."}), 500

    ai_response = ask_openai(resume_text, user_message)
    return jsonify({"response": ai_response})

# Extract text from PDF resume
def extract_resume_text(pdf_path):
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            for page in reader.pages:
                page_text = page.extract_text() or ''
                text += page_text
            return text
    except Exception as e:
        print(f"Error extracting text from PDF {pdf_path}: {str(e)}")
        return ''

# Extract first 25 lines from PDF
def extract_first_25_lines(pdf_path):
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            for page in reader.pages:
                page_text = page.extract_text() or ''
                text += page_text
            lines = text.split('\n')[:25]
            return '\n'.join(lines)
    except Exception as e:
        print(f"Error extracting first 25 lines from PDF {pdf_path}: {str(e)}")
        return ''

# Check if PDF is a resume using OpenAI API
def is_resume(text):
    if not text.strip():
        print("No text extracted for resume check, assuming not a resume")
        return False
    
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    prompt = f"""
    Analyze the following text (first 25 lines of a document) and determine if it is a resume. A resume typically includes sections like personal information (name, contact details), education, work experience, skills, or job titles. Return a JSON response with a single field 'is_resume' set to true or false.

    Text:
    {text}
    """
    
    payload = {
        'model': OPENAI_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'response_format': {'type': 'json_object'},
        'max_tokens': 100
    }
    
    for attempt in range(3):
        try:
            print(f"Sending OpenAI request (attempt {attempt + 1}): {json.dumps(payload, indent=2)}")
            response = session.post(OPENAI_API_URL, headers=headers, json=payload, timeout=10)
            print(f"OpenAI response status: {response.status_code}")
            print(f"OpenAI headers: {json.dumps(dict(response.headers), indent=2)}")
            
            # Save response to file for inspection
            response_file = f'openai_response_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            with open(response_file, 'w', encoding='utf-8') as f:
                f.write(f"Status: {response.status_code}\n")
                f.write(f"Headers: {json.dumps(dict(response.headers), indent=2)}\n")
                f.write(f"Body: {response.text}")
            print(f"Response saved to {response_file}")
            
            if response.status_code == 429:
                print("Rate limit exceeded, retrying after delay")
                time.sleep(5)
                continue
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            print(f"OpenAI raw content: {content}")
            result = json.loads(content)
            is_resume_value = result.get('is_resume', False)
            print(f"Extracted is_resume: {is_resume_value}")
            return is_resume_value
        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            print(f"Error checking if document is resume (attempt {attempt + 1}): {str(e)}")
            print(f"OpenAI raw response: {response.text[:500] if 'response' in locals() else 'No response'}...")
            if attempt < 2:
                time.sleep(2)
        except Exception as e:
            print(f"Unexpected error in is_resume (attempt {attempt + 1}): {str(e)}")
            if attempt < 2:
                time.sleep(2)
    
    print("All retry attempts failed, assuming not a resume")
    return False

# Parse resume using OpenAI API
def parse_resume(text):
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    prompt = f"""
    Extract the following details from the resume text below:
    - Candidate name
    - Position applied for (if mentioned, else return 'Not specified')
    - Qualifications (list of degrees/certifications, e.g., ["Bachelor of Science", "Master of Arts", "PMP Certificate"])
    - Years of experience (numeric value, estimate if not explicit)
    - Skills (list of technical or relevant skills, e.g., ["Python", "AWS", "SQL"])
    - Previous experience (list of companies or roles, max 2 entries, e.g., ["Software Engineer at Google", "Data Scientist at Amazon"])

    Return the response in JSON format. If a field cannot be determined, use appropriate defaults (e.g., empty list for lists, 0 for numbers, 'Not specified' for strings).

    Resume text:
    {text}
    """
    
    payload = {
        'model': OPENAI_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'response_format': {'type': 'json_object'},
        'max_tokens': 1500
    }
    
    candidate = {
        'name': 'Unknown',
        'position': 'Not specified',
        'qualifications': [],
        'experience_years': 0,
        'skills': [],
        'previous_experience': [],
        'interview_status': 'Not Taken'
    }
    
    try:
        response = session.post(OPENAI_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        print(f"OpenAI parse_resume content: {content}")
        parsed_data = json.loads(content)
        
        candidate['name'] = parsed_data.get('name', 'Unknown')
        candidate['position'] = parsed_data.get('position', 'Not specified')
        
        qualifications_data = parsed_data.get('qualifications', [])
        candidate['qualifications'] = qualifications_data if isinstance(qualifications_data, list) else [q.strip() for q in qualifications_data.split(',') if q.strip()] if isinstance(qualifications_data, str) else []
        
        candidate['experience_years'] = parsed_data.get('experience_years', 0)
        
        skills_data = parsed_data.get('skills', [])
        candidate['skills'] = skills_data if isinstance(skills_data, list) else [s.strip() for s in skills_data.split(',') if s.strip()] if isinstance(skills_data, str) else []
        
        prev_exp_data = parsed_data.get('previous_experience', [])
        candidate['previous_experience'] = prev_exp_data if isinstance(prev_exp_data, list) else [p.strip() for p in prev_exp_data.split(',') if p.strip()] if isinstance(prev_exp_data, str) else []
        
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing resume: {e}")
    except Exception as e:
        print(f"Unexpected error in parse_resume: {e}")
    
    return candidate

# Match resume to open positions using OpenAI API
def match_position(candidate, positions):
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json'
    }

    position_texts = []
    for pos in positions:
        required_skills_str = ', '.join(pos.get('required_skills', [])) if isinstance(pos.get('required_skills'), list) else pos.get('required_skills', '')
        qualifications_str = ', '.join(pos.get('qualifications', [])) if isinstance(pos.get('qualifications'), list) else pos.get('qualifications', '')
        position_texts.append(
            f"Position: {pos.get('title', 'N/A')}, Required Skills: {required_skills_str}, Qualifications: {qualifications_str}, Min Experience: {pos.get('min_experience_years', 0)} years"
        )

    candidate_skills_str = ', '.join(candidate.get('skills', [])) if isinstance(candidate.get('skills'), list) else candidate.get('skills', '')
    candidate_qualifications_str = ', '.join(candidate.get('qualifications', [])) if isinstance(candidate.get('qualifications'), list) else candidate.get('qualifications', '')
    candidate_experience_years = candidate.get('experience_years', 0)

    # --- MODIFIED PROMPT BELOW ---
    prompt = f"""
    Given the candidate's details and a list of open positions, determine the **best overall matching position**.

    Be flexible and consider **relatedness** in skills and qualifications, not just exact matches.
    Prioritize candidates who meet or are close to the minimum experience, but consider strong skill/qualification overlaps even if experience is slightly less.
    If a candidate has a broad set of technical skills, they might be a good fit for a software engineering or data role even if specific required skills aren't listed verbatim.
    Similarly, consider qualifications that are generally relevant to the field (e.g., any Bachelor's degree in a technical field for a tech role).

    If a reasonable match exists, return that position. Only return 'No matching position available' if there's truly no significant overlap or potential fit.

    Candidate Details:
    - Skills: {candidate_skills_str}
    - Qualifications: {candidate_qualifications_str}
    - Experience: {candidate_experience_years} years

    Open Positions:
    {'; '.join(position_texts)}

    Return the response strictly as a JSON object with a single key "position".
    Both the key "position" and its string value MUST be enclosed in double quotes.

    Example for a match: {{"position": "Software Engineer"}}
    Example for no match: {{"position": "No matching position available"}}
    """
    # --- END MODIFIED PROMPT ---

    payload = {
        'model': OPENAI_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'response_format': {'type': 'json_object'},
        'max_tokens': 200
    }

    try:
        # Use your session.post here if 'session' is defined, otherwise use requests.post
        # Assuming 'session' is an existing requests.Session object for persistent connections
        response = session.post(OPENAI_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        print(f"OpenAI match_position content: {content}")
        result = json.loads(content)
        position_value = result.get('position', 'No matching position available')
        if not isinstance(position_value, str):
            print(f"Warning: 'position' value is not a string: {position_value}")
            return 'No matching position available'
        return position_value
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Error matching position: {e}")
        return 'No matching position available'
    except Exception as e:
        print(f"Unexpected error in match_position: {e}")
        return 'No matching position available'

# Fetch and process emails using Microsoft Graph
def process_emails():
    try:
        access_token = connect_graph()
        if isinstance(access_token, flask.Response):
            return access_token
        
        db = mysql.connector.connect(**db_config)
        cursor = db.cursor(dictionary=True)
        
        cursor.execute("SELECT DATABASE()")
        current_db = cursor.fetchone()['DATABASE()']
        print(f"Connected to database: {current_db}")
        
        cursor.execute("SELECT title, required_skills, qualifications, min_experience_years FROM positions")
        positions = cursor.fetchall()
        
        # Fetch unread emails
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Get unread emails with attachments
        for attempt in range(3):
            try:
                response = session.get(
                    'https://graph.microsoft.com/v1.0/me/mailFolders/Inbox/messages?$filter=isRead eq false and hasAttachments eq true',
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                messages = response.json().get('value', [])
                print(f"Found {len(messages)} unread emails with attachments.")
                break
            except requests.RequestException as e:
                print(f"Graph API request failed (attempt {attempt + 1}): {str(e)}")
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise
        else:
            raise Exception("Failed to fetch emails after retries")
        
        for message in messages:
            # Get attachments
            for attempt in range(3):
                try:
                    attachments_response = session.get(
                        f'https://graph.microsoft.com/v1.0/me/messages/{message["id"]}/attachments',
                        headers=headers,
                        timeout=10
                    )
                    attachments_response.raise_for_status()
                    attachments = attachments_response.json().get('value', [])
                    break
                except requests.RequestException as e:
                    print(f"Graph API attachments request failed (attempt {attempt + 1}): {str(e)}")
                    if attempt < 2:
                        time.sleep(2)
                    else:
                        raise
            else:
                print(f"Skipping message {message['id']} due to repeated failures")
                continue
            
            for attachment in attachments:
                if attachment['contentType'] != 'application/pdf':
                    print(f"Skipping non-PDF attachment: {attachment['name']}")
                    continue
                
                attachment_path = f'resumes/{attachment["name"]}'
                
                # Check if filename contains 'resume'
                if 'resume' in attachment['name'].lower():
                    print(f"Processing resume attachment: {attachment['name']}")
                    # Download attachment
                    for attempt in range(3):
                        try:
                            content_bytes = session.get(
                                f'https://graph.microsoft.com/v1.0/me/messages/{message["id"]}/attachments/{attachment["id"]}/$value',
                                headers=headers,
                                timeout=10
                            ).content
                            with open(attachment_path, 'wb') as f:
                                f.write(content_bytes)
                            break
                        except requests.RequestException as e:
                            print(f"Graph API attachment download failed (attempt {attempt + 1}): {str(e)}")
                            if attempt < 2:
                                time.sleep(2)
                            else:
                                raise
                else:
                    print(f"Checking if attachment is a resume: {attachment['name']}")
                    # Download temporarily to check content
                    for attempt in range(3):
                        try:
                            content_bytes = session.get(
                                f'https://graph.microsoft.com/v1.0/me/messages/{message["id"]}/attachments/{attachment["id"]}/$value',
                                headers=headers,
                                timeout=10
                            ).content
                            with open(attachment_path, 'wb') as f:
                                f.write(content_bytes)
                            break
                        except requests.RequestException as e:
                            print(f"Graph API attachment download failed (attempt {attempt + 1}): {str(e)}")
                            if attempt < 2:
                                time.sleep(2)
                            else:
                                raise
                    
                    # Extract first 25 lines and check if it's a resume
                    first_25_lines = extract_first_25_lines(attachment_path)
                    if not is_resume(first_25_lines):
                        print(f"Attachment not a resume, skipping: {attachment['name']}")
                        os.remove(attachment_path)  # Clean up temporary file
                        continue
                    print(f"Confirmed resume attachment: {attachment['name']}")
                
                # Parse resume
                text = extract_resume_text(attachment_path)
                candidate = parse_resume(text)
                
                # Match to open position
                candidate['position'] = match_position(candidate, positions)
                
                # Insert into database
                query = """
                    INSERT INTO candidates (name, position, qualifications, experience_years, skills, previous_experience, interview_status, application_date, resume_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    candidate['name'],
                    candidate['position'],
                    ', '.join(candidate['qualifications']),
                    candidate['experience_years'],
                    ', '.join(candidate['skills']),
                    ', '.join(candidate['previous_experience']),
                    candidate['interview_status'],
                    datetime.now(),
                    attachment_path  # 🆕 Added resume path here
                )

                cursor.execute(query, values)
                db.commit()
                
                # Mark email as read
                for attempt in range(3):
                    try:
                        session.patch(
                            f'https://graph.microsoft.com/v1.0/me/messages/{message["id"]}',
                            headers=headers,
                            json={'isRead': True},
                            timeout=10
                        )
                        break
                    except requests.RequestException as e:
                        print(f"Graph API mark read failed (attempt {attempt + 1}): {str(e)}")
                        if attempt < 2:
                            time.sleep(2)
                        else:
                            raise
        
        cursor.close()
        db.close()
        return True
    except mysql.connector.Error as err:
        print(f"Database error in process_emails: {err}")
        return False
    except requests.HTTPError as e:
        print(f"Graph API HTTP error in process_emails: {e.response.text}")
        return False
    except requests.RequestException as e:
        print(f"Network error in process_emails: {str(e)}")
        return False
    except Exception as e:
        print(f"Unexpected error in process_emails: {str(e)}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/candidates', methods=['GET'])
def get_candidates():
    try:
        db = mysql.connector.connect(**db_config)
        cursor = db.cursor(dictionary=True)
        
        cursor.execute("SELECT DATABASE()")
        current_db = cursor.fetchone()['DATABASE()']
        print(f"Connected to database in get_candidates: {current_db}")
        
        position = request.args.get('position', '')
        education = request.args.get('education', '')
        experience = request.args.get('experience', '')
        
        query = "SELECT * FROM candidates WHERE 1=1"
        params = []
        
        if position:
            query += " AND position = %s"
            params.append(position)
        if education:
            query += " AND qualifications LIKE %s"
            params.append(f'%{education}%')
        if experience:
            query += " AND experience_years >= %s"
            params.append(int(experience))
        
        cursor.execute(query, params)
        candidates = cursor.fetchall()
        
        cursor.close()
        db.close()
        return jsonify(candidates)
    except mysql.connector.Error as err:
        print(f"Database error in get_candidates: {err}")
        return jsonify({'error': str(err)}), 500
    except Exception as e:
        print(f"Error in get_candidates: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/process_emails', methods=['POST'])
def trigger_email_processing():
    try:
        result = process_emails()
        if isinstance(result, flask.Response):
            return result
        if result:
            return jsonify({'status': 'Emails processed successfully'})
        else:
            return jsonify({'error': 'Failed to process emails'}), 500
    except Exception as e:
        print(f"Error processing emails: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)