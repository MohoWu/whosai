import os

from dotenv import load_dotenv

from whosai.transport.http import create_app

load_dotenv()

app = create_app(enable_test_controls=os.getenv("WHOSAI_E2E") == "1")
