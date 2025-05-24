import msal
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OAuth 2.0 Configuration
CLIENT_ID = os.getenv('ol_CLIENT_ID')
CLIENT_SECRET = os.getenv('ol_CLIENT_SECRET')
AUTHORITY = os.getenv('ol_AUTHORITY')
REDIRECT_URI = os.getenv('ol_REDIRECT_URI')
SCOPE = [s for s in os.getenv('SCOPE').split() if s not in ['profile', 'offline_access', 'openid']]

# Debug: Print processed scopes
print("Processed SCOPE for MSAL:", SCOPE)

# Token storage file
TOKEN_FILE = 'tokens.json'

def save_tokens(token_result):
    """Save tokens to a file."""
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_result, f)
    print(f"Tokens saved to {TOKEN_FILE}")

def load_tokens():
    """Load tokens from a file if they exist."""
    try:
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"No token file found at {TOKEN_FILE}")
        return None

def get_auth_url():
    """Generate the authorization URL for OAuth 2.0 flow."""
    app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=AUTHORITY
    )
    auth_url = app.get_authorization_request_url(
        scopes=SCOPE,  # Include offline_access for refresh token
        redirect_uri=REDIRECT_URI
    )
    print(f"Generated auth URL: {auth_url}")
    return auth_url

def get_token(code=None):
    """Acquire a token, either by authorization code or refresh token."""
    app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=AUTHORITY
    )
    
    if code:
        # Exchange authorization code for token
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=SCOPE ,  # Include offline_access for refresh token
            redirect_uri=REDIRECT_URI
        )
        if 'access_token' in result:
            save_tokens(result)
            return result
        else:
            raise Exception(f"Token acquisition failed: {result.get('error_description', 'No error description')}")
    
    # Try to use refresh token
    tokens = load_tokens()
    if tokens and 'refresh_token' in tokens:
        result = app.acquire_token_by_refresh_token(
            refresh_token=tokens['refresh_token'],
            scopes=SCOPE  # Exclude offline_access for refresh token
        )
        if 'access_token' in result:
            save_tokens(result)
            return result
        else:
            raise Exception(f"Refresh token failed: {result.get('error_description', 'No error description')}")
    
    raise Exception("Authentication failed: No valid tokens available. Authorization code required.")