import flask
from flask import Flask, jsonify, render_template, request, redirect, url_for, send_from_directory
import mysql.connector
import PyPDF2
import requests
import re
from datetime import datetime
import json
from dotenv import load_dotenv
import os
from auth import get_auth_url, get_token

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
print("OPENROUTER_API_KEY:",   os.getenv('OPENROUTER_API_KEY'))
print("Database Configuration:", db_config)

# Validate db_config
if not all([db_config['user'], db_config['database']]):
    raise ValueError("Missing required MySQL configuration (user or database) in .env file")

# OpenRouter API Configuration from environment variables
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'meta-llama/llama-3.1-8b-instruct:free')
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Validate OpenRouter API key
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is not set in .env file")

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

# Check if PDF is a resume using OpenRouter API
def is_resume(text):
    if not text.strip():
        print("No text extracted for resume check, assuming not a resume")
        return False
    
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    prompt = f"""
    Analyze the following text (first 25 lines of a document) and determine if it is a resume. A resume typically includes sections like personal information (name, contact details), education, work experience, skills, or job titles. Return a JSON response with a single field 'is_resume' set to true or false.

    Text:
    {text}
    """
    
    payload = {
        'model': OPENROUTER_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'response_format': {'type': 'json_object'}
    }
    
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()

        if response.headers.get('content-type', '').startswith('application/json'):
            # The API itself might return directly parseable JSON,
            # so we'll try that first.
            try:
                # Direct JSON parsing if the 'content-type' is truly json
                content_json = response.json()
                # Assuming the structure is choices[0].message.content which holds the JSON string
                if 'choices' in content_json and len(content_json['choices']) > 0:
                    model_response_content = content_json['choices'][0]['message']['content']
                    # Now, search for the JSON object within the model's response string
                    json_search = re.search(r'\{.*?\}', model_response_content, re.DOTALL)
                    if json_search:
                        json_str = json_search.group(0)
                        result = json.loads(json_str)
                        return result.get('is_resume', False)
                    else:
                        print(f"No JSON object found within the model's response content: {model_response_content[:100]}...")
                        return False
                else:
                    print("Unexpected API response structure (missing 'choices' or empty).")
                    return False

            except json.JSONDecodeError:
                # Fallback if the initial response.json() fails, meaning the content
                # might be a string that *contains* JSON, like your example.
                content = response.text # Get the raw text if it's not direct JSON

                # Use re.search to find the JSON object anywhere in the string
                json_search = re.search(r'\{.*?\}', content, re.DOTALL)
                print("json_search ", json_search) # Debugging print
                if json_search:
                    json_str = json_search.group(0)
                    result = json.loads(json_str)
                    return result.get('is_resume', False)
                else:
                    print(f"No JSON found in content: {content[:100]}...")
                    return False
        else:
            print(f"Unexpected content-type: {response.headers.get('content-type')}")
            # Try to parse the raw text anyway, as some APIs might send json in text/plain
            content = response.text
            json_search = re.search(r'\{.*?\}', content, re.DOTALL)
            if json_search:
                json_str = json_search.group(0)
                try:
                    result = json.loads(json_str)
                    return result.get('is_resume', False)
                except json.JSONDecodeError:
                    print(f"Content-type was not application/json, and extracted string was not valid JSON: {json_str[:100]}...")
                    return False
            else:
                print(f"No JSON found in unexpected content-type: {content[:100]}...")
                return False

    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Error checking if document is resume: {str(e)}")
        return False

# Parse resume using OpenRouter API
def parse_resume(text):
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json'
    }

    # MODIFICATION HERE: Changed qualifications to be a list of strings
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
        'model': OPENROUTER_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'response_format': {'type': 'json_object'}
    }

    candidate = { # Initialize candidate with defaults outside try-except
        'name': 'Unknown',
        'position': 'Not specified',
        'qualifications': [], # Changed default to empty list
        'experience_years': 0,
        'skills': [],
        'previous_experience': [],
        'interview_status': 'Not Taken'
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()

        model_response_content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')

        json_search = re.search(r'\{.*?\}', model_response_content, re.DOTALL)

        if json_search:
            json_str = json_search.group(0)
            try:
                parsed_data = json.loads(json_str)

                # Update candidate with parsed data, using .get for safety
                candidate['name'] = parsed_data.get('name', 'Unknown')
                candidate['position'] = parsed_data.get('position', 'Not specified')

                # Handle qualifications, ensuring it's a list
                qualifications_data = parsed_data.get('qualifications', [])
                if isinstance(qualifications_data, list):
                    candidate['qualifications'] = qualifications_data
                elif isinstance(qualifications_data, str) and qualifications_data.strip():
                    candidate['qualifications'] = [q.strip() for q in qualifications_data.split(',') if q.strip()]
                else:
                    candidate['qualifications'] = []


                candidate['experience_years'] = parsed_data.get('experience_years', 0)
                # Ensure skills is a list
                skills_data = parsed_data.get('skills', [])
                if isinstance(skills_data, list):
                    candidate['skills'] = skills_data
                elif isinstance(skills_data, str) and skills_data.strip():
                    candidate['skills'] = [s.strip() for s in skills_data.split(',') if s.strip()]
                else:
                    candidate['skills'] = []


                # Ensure previous_experience is a list
                prev_exp_data = parsed_data.get('previous_experience', [])
                if isinstance(prev_exp_data, list):
                    candidate['previous_experience'] = prev_exp_data
                elif isinstance(prev_exp_data, str) and prev_exp_data.strip():
                    candidate['previous_experience'] = [p.strip() for p in prev_exp_data.split(',') if p.strip()]
                else:
                    candidate['previous_experience'] = []


            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from model response: {e}. Raw content: {json_str[:200]}...")
            except Exception as e:
                print(f"Error processing parsed JSON data: {e}. Parsed data: {parsed_data}")
        else:
            print(f"No JSON object found in model response content: {model_response_content[:200]}...")

    except (requests.RequestException, KeyError) as e:
        print(f"Error communicating with OpenRouter API or unexpected response structure: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in parse_resume: {e}")

    return candidate
# Match resume to open positions using OpenRouter API
def match_position(candidate, positions):
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json'
    }

    # Prepare position texts, handling cases where skills/qualifications might be lists
    position_texts = []
    for pos in positions:
        # Ensure 'required_skills' and 'qualifications' are joined correctly if they are lists
        required_skills_str = ', '.join(pos.get('required_skills', [])) if isinstance(pos.get('required_skills'), list) else pos.get('required_skills', '')
        qualifications_str = ', '.join(pos.get('qualifications', [])) if isinstance(pos.get('qualifications'), list) else pos.get('qualifications', '')

        position_texts.append(
            f"Position: {pos.get('title', 'N/A')}, Required Skills: {required_skills_str}, Qualifications: {qualifications_str}, Min Experience: {pos.get('min_experience_years', 0)} years"
        )

    # Prepare candidate details, ensuring lists are joined correctly
    candidate_skills_str = ', '.join(candidate.get('skills', [])) if isinstance(candidate.get('skills'), list) else candidate.get('skills', '')
    candidate_qualifications_str = ', '.join(candidate.get('qualifications', [])) if isinstance(candidate.get('qualifications'), list) else candidate.get('qualifications', '')
    candidate_experience_years = candidate.get('experience_years', 0)

    prompt = f"""
    Given the candidate's details and a list of open positions, determine the best matching position. If no position matches, return 'No matching position available'.

    Candidate Details:
    - Skills: {candidate_skills_str}
    - Qualifications: {candidate_qualifications_str}
    - Experience: {candidate_experience_years} years

    Open Positions:
    {', '.join(position_texts)}

    Return the response in JSON format with a single field 'position'.
    """

    payload = {
        'model': OPENROUTER_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'response_format': {'type': 'json_object'}
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()

        # Get the raw content from the model's response
        # It's usually nested under choices[0].message.content
        model_response_content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')

        # Use re.search to find the JSON object anywhere in the string
        json_search = re.search(r'\{.*?\}', model_response_content, re.DOTALL)

        if json_search:
            json_str = json_search.group(0)
            try:
                result = json.loads(json_str)
                return result.get('position', 'No matching position available')
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from model response in match_position: {e}. Raw content: {json_str[:200]}...")
                return 'No matching position available'
        else:
            print(f"No JSON object found in model response content for match_position: {model_response_content[:200]}...")
            return 'No matching position available'

    except (requests.RequestException, KeyError) as e:
        print(f"Error communicating with OpenRouter API or unexpected response structure in match_position: {e}")
        return 'No matching position available'
    except Exception as e:
        print(f"An unexpected error occurred in match_position: {e}")
        return 'No matching position available'
def match_position(candidate, positions):
    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
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

    # --- IMPORTANT: MODIFIED PROMPT BELOW ---
    prompt = f"""
    Given the candidate's details and a list of open positions, determine the best matching position.
    Return the response strictly in JSON format with a single field "position".
    The value for "position" MUST be a string enclosed in double quotes.

    Example if a match is found: {{"position": "Software Engineer"}}
    Example if no match: {{"position": "No matching position available"}}

    Candidate Details:
    - Skills: {candidate_skills_str}
    - Qualifications: {candidate_qualifications_str}
    - Experience: {candidate_experience_years} years

    Open Positions:
    {'; '.join(position_texts)}
    """
    # --- END MODIFIED PROMPT ---

    payload = {
        'model': OPENROUTER_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'response_format': {'type': 'json_object'}
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()

        model_response_content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')

        json_search = re.search(r'\{.*?\}', model_response_content, re.DOTALL)

        if json_search:
            json_str = json_search.group(0)
            try:
                result = json.loads(json_str)
                # Ensure the returned position is a string, even if the model messes up the type
                position_value = result.get('position', 'No matching position available')
                if not isinstance(position_value, str):
                    print(f"Warning: 'position' value is not a string, defaulting. Value: {position_value}")
                    return 'No matching position available'
                return position_value
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from model response in match_position: {e}. Raw content: {json_str[:200]}...")
                return 'No matching position available'
        else:
            print(f"No JSON object found in model response content for match_position: {model_response_content[:200]}...")
            return 'No matching position available'

    except (requests.RequestException, KeyError) as e:
        print(f"Error communicating with OpenRouter API or unexpected response structure in match_position: {e}")
        return 'No matching position available'
    except Exception as e:
        print(f"An unexpected error occurred in match_position: {e}")
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
        response = requests.get(
            'https://graph.microsoft.com/v1.0/me/mailFolders/Inbox/messages?$filter=isRead eq false and hasAttachments eq true',
            headers=headers
        )
        response.raise_for_status()
        messages = response.json().get('value', [])
        print(f"Found {len(messages)} unread emails with attachments.")
        
        for message in messages:
            # Get attachments
            attachments_response = requests.get(
                f'https://graph.microsoft.com/v1.0/me/messages/{message["id"]}/attachments',
                headers=headers
            )
            attachments_response.raise_for_status()
            attachments = attachments_response.json().get('value', [])
            
            for attachment in attachments:
                if attachment['contentType'] != 'application/pdf':
                    print(f"Skipping non-PDF attachment: {attachment['name']}")
                    continue
                
                attachment_path = f'resumes/{attachment["name"]}'
                
                # Check if filename contains 'resume'
                if 'resume' in attachment['name'].lower():
                    print(f"Processing resume attachment: {attachment['name']}")
                    # Download attachment
                    content_bytes = requests.get(
                        f'https://graph.microsoft.com/v1.0/me/messages/{message["id"]}/attachments/{attachment["id"]}/$value',
                        headers=headers
                    ).content
                    with open(attachment_path, 'wb') as f:
                        f.write(content_bytes)
                else:
                    print(f"Checking if attachment is a resume: {attachment['name']}")
                    # Download temporarily to check content
                    content_bytes = requests.get(
                        f'https://graph.microsoft.com/v1.0/me/messages/{message["id"]}/attachments/{attachment["id"]}/$value',
                        headers=headers
                    ).content
                    with open(attachment_path, 'wb') as f:
                        f.write(content_bytes)
                    
                    # Extract first 25 lines and check if it's a resume
                    first_25_lines = extract_first_25_lines(attachment_path)
                    # print(f"First 25 lines extracted for resume check: {first_25_lines}")
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
                    INSERT INTO candidates (name, position, qualifications, experience_years, skills, previous_experience, interview_status, application_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    candidate['name'],
                    candidate['position'],
                    ', '.join(candidate['qualifications']),
                    candidate['experience_years'],
                    ', '.join(candidate['skills']),
                    ', '.join(candidate['previous_experience']),
                    candidate['interview_status'],
                    datetime.now()
                )
                cursor.execute(query, values)
                db.commit()
                
                # Mark email as read
                requests.patch(
                    f'https://graph.microsoft.com/v1.0/me/messages/{message["id"]}',
                    headers=headers,
                    json={'isRead': True}
                )
        
        cursor.close()
        db.close()
        return True
    except mysql.connector.Error as err:
        print(f"Database error in process_emails: {err}")
        return False
    except requests.HTTPError as e:
        print(f"Graph API error in process_emails: {e.response.text}")
        return False
    except Exception as e:
        print(f"Error in process_emails: {str(e)}")
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