from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

mongo_uri = os.getenv("MONGO_URI")
print(f"Testing connection to: {mongo_uri[:50]}...")

try:
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ Successfully connected to MongoDB Atlas!")
    print(f"Databases: {client.list_database_names()}")
    client.close()
except Exception as e:
    print(f"❌ Connection failed: {str(e)}")