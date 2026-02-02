"""
Debug script to see exactly what DB_TYPE is being used
"""
import os
import sys

print("=" * 70)
print("DEBUGGING DB_TYPE CONFIGURATION")
print("=" * 70)

print(f"\nCurrent working directory: {os.getcwd()}")
print(f"Script directory: {os.path.dirname(os.path.abspath(__file__))}")

# Check if .env exists
env_path = os.path.join(os.getcwd(), '.env')
print(f"\n.env path: {env_path}")
print(f".env exists: {os.path.exists(env_path)}")

if os.path.exists(env_path):
    print("\n.env contents:")
    with open(env_path, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                print(f"  {line.strip()}")

# Load dotenv
from dotenv import load_dotenv
load_dotenv()

print("\n" + "=" * 70)
print("ENVIRONMENT VARIABLES (from os.getenv)")
print("=" * 70)
print(f"DB_TYPE: '{os.getenv('DB_TYPE')}'")
print(f"DB_TYPE (with default): '{os.getenv('DB_TYPE', 'SQLITE')}'")

# Import config
print("\n" + "=" * 70)
print("CONFIG MODULE")
print("=" * 70)

from config import DB_TYPE, application_path, dotenv_path
print(f"config.DB_TYPE: '{DB_TYPE}'")
print(f"config.application_path: {application_path}")
print(f"config.dotenv_path: {dotenv_path}")
print(f"dotenv_path exists: {os.path.exists(dotenv_path)}")

# Test database connection
print("\n" + "=" * 70)
print("DATABASE CONNECTION TEST")
print("=" * 70)

from database import get_db_connection

try:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DB_TYPE == 'MYSQL':
        cursor.execute("SELECT DATABASE()")
        db_name = cursor.fetchone()[0]
        print(f"✅ Connected to MySQL database: {db_name}")
    else:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        result = cursor.fetchone()
        print(f"✅ Connected to SQLite database")
        print(f"   First table: {result[0] if result else 'No tables'}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Connection error: {e}")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)

if DB_TYPE == 'MYSQL':
    print("✅ System is configured for MYSQL")
else:
    print("❌ System is configured for SQLITE")
    print("   This is the problem!")

print("=" * 70)
