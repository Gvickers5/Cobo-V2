import os
from pathlib import Path
from dotenv import load_dotenv

USER_HOME = Path.home()
COBO_ENV_DIR = USER_HOME / 'Cobo'
SYSTEM_DIR = COBO_ENV_DIR / '00 - System'
ASYNC_INBOX = COBO_ENV_DIR / 'async_inbox.txt'
CASE_FILE = SYSTEM_DIR / 'Cobo_Case_File.md'

# Store the keys securely in the user's folder
ENV_FILE = COBO_ENV_DIR / '.env'
load_dotenv(dotenv_path=ENV_FILE)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')

PROJECT_ROOT = Path(__file__).parent
CLIENT_SECRETS_FILE = PROJECT_ROOT / 'client_secrets.json'
KEEP_TOKEN_PATH = COBO_ENV_DIR / 'keep_token.json'
