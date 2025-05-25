**HR Agent Dashboard**


The HR Agent Dashboard is a web application designed to streamline the recruitment process by automating candidate data extraction from emails and providing an interactive interface for HR professionals to manage and evaluate candidates. Built with a Flask backend and a responsive Bootstrap frontend, it integrates with Outlook for email processing, MySQL for data storage, and OpenAI for AI-powered candidate analysis.
Features

**Candidate Table:** Displays candidate details (Name, Position, Qualifications, Experience, Skills, etc.) in a sortable, filterable table.


**Email Processing:** Extracts candidate data and resumes from Outlook emails via Microsoft Graph API.
Resume Viewer: View candidate resumes in a modal with an embedded PDF viewer.
AI Chatbot: Interactive AI assistant powered by OpenAI to answer questions about candidates (e.g., "What are the candidate’s key skills?").
Filters: Filter candidates by position, education, or minimum experience.
Responsive Design: Optimized for desktop and mobile devices (<768px).
Loading States: Visual feedback with spinners and overlays during email processing.

**Tech Stack
**
**Frontend:** HTML, Bootstrap 5.3, JavaScript
**Backend:** Flask (Python)
**Database:** MySQL
**APIs:**
Microsoft Graph API (Outlook email access)
OpenAI API (GPT-4o-mini for chatbot)


**Libraries:**
PyPDF2 (PDF text extraction)
python-dotenv (environment variables)


**Deployment:** Local server (Flask development server)

**Prerequisites**

Python 3.8+
MySQL Server
Outlook account with Microsoft Graph API access
OpenAI API key
Git

**Setup Instructions
**
Clone the Repository:
git clone https://github.com/your-username/hr-agent-dashboard.git
cd hr-agent-dashboard


**Install Dependencies:**
pip install -r requirements.txt

**Ensure requirements.txt includes:**
flask
mysql-connector-python
requests
PyPDF2
python-dotenv
openai


**Set Up Environment Variables:Create a .env file in the project root:**

MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_HOST=localhost
MYSQL_DATABASE=hr_agent_db
OUTLOOK_EMAIL=your_email@outlook.com
ol_CLIENT_ID=your_microsoft_client_id
ol_CLIENT_SECRET=your_microsoft_client_secret
ol_REDIRECT_URI=http://localhost:5000/oauth2/callback
SCOPE=https://graph.microsoft.com/Mail.Read offline_access
OPENAI_API_KEY=sk-proj-your_openai_api_key
OPENAI_MODEL=gpt-4o-mini


**Set Up MySQL Database:**

**Create the database:**CREATE DATABASE hr_agent_db;


**Create tables (candidates, positions, processed_emails):**

CREATE TABLE candidates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255),
    position VARCHAR(255),
    qualifications TEXT,
    experience_years INT,
    skills TEXT,
    previous_experience TEXT,
    interview_status VARCHAR(50),
    application_date DATE,
    resume_path VARCHAR(255)
);
CREATE TABLE positions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255),
    description TEXT
);
CREATE TABLE processed_emails (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email_id VARCHAR(255) UNIQUE,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



**
Create Resumes Directory:**
mkdir resumes

Ensure resumes are stored in resumes/ (e.g., resumes/Ishan_Ravi_Resume.pdf).

**Run the Application:**
python app.py

Access at http://localhost:5000.


Usage

**Process Emails:**

Click "Process Emails" to fetch candidate data from Outlook.
Authenticate via OAuth if prompted.
Resumes are saved to resumes/, and data is stored in MySQL.


**View Candidates:**

Table displays candidate details.
Click + in the Skills column to expand a narrower detail row (shows full skills).
Use filters (Position, Education, Experience) to narrow results.


**View Resumes:**

Click "View" in the Resume column to open a PDF in a modal.


**AI Chatbot:**

In the resume modal, click "Start Chatbot".
Use suggested questions (e.g., "What are the candidate’s key skills?") or enter custom queries.
Responses include bullet points for clarity.


**Test Data:**

Add sample candidates:INSERT INTO candidates (name, position, qualifications, experience_years, skills, previous_experience, interview_status, application_date, resume_path)
VALUES ('Ishan Ravi', 'Software Engineer', 'B.S. Computer Science', 5, 'Python, Java, JavaScript, SQL, React, Node.js, AWS, Docker', 'Senior Developer at TechCorp', 'Scheduled', '2025-05-25', 'resumes/Ishan_Ravi_Resume.pdf');





Project Structure
hr-agent-dashboard/

├── app.py                  # Flask backend

├── auth.py                 # OAuth handling for Microsoft Graph

├── templates/
│   └── index.html          # Frontend (table, modals, expandable rows)

├── resumes/                # Stores candidate resume PDFs

├── .env                    # Environment variables

├── requirements.txt        # Python dependencies

└── README.md               # Project documentation


Contributing
Contributions are welcome! To contribute:

Fork the repository.
Create a feature branch (git checkout -b feature/your-feature).
Commit changes (git commit -m 'Add your feature').
Push to the branch (git push origin feature/your-feature).
Open a Pull Request.

Please include tests and update documentation as needed.


For questions or feedback, reach out via GitHub Issues or email at [your-email@example.com].
