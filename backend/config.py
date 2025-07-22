import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_URL = f"sqlite://{os.path.join(BASE_DIR, 'db.sqlite3')}" 