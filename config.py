import os
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("FLASK_HOST", "127.0.0.1")
PORT = int(os.getenv("FLASK_PORT", "5000"))
DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
