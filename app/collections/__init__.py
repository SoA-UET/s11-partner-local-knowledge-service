from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv('MONGO_URL')

if not MONGO_URL:
    print(f"Environment variable MONGO_URL is missing.")
    import sys
    sys.exit(1)

client = MongoClient(MONGO_URL)
db = client.get_default_database()

# NOTE: Change collection names as appropriate.

conversations_collection = db.conversations
messages_collection = db.messages

# S11 Collections
packages_collection = db.packages
faqs_collection = db.faqs
file_imports_collection = db.file_imports
