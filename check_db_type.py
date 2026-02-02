import os
from dotenv import load_dotenv

# Check current directory
print(f"Current directory: {os.getcwd()}")
print(f"Script location: {os.path.dirname(os.path.abspath(__file__))}")

# Load .env
load_dotenv()

print("\n" + "=" * 60)
print("ENVIRONMENT VARIABLES CHECK")
print("=" * 60)

db_type = os.getenv("DB_TYPE", "SQLITE")
print(f"DB_TYPE: {db_type}")
print(f"MYSQL_HOST: {os.getenv('MYSQL_HOST')}")
print(f"MYSQL_USER: {os.getenv('MYSQL_USER')}")
print(f"MYSQL_DATABASE: {os.getenv('MYSQL_DATABASE')}")
print(f"MYSQL_PORT: {os.getenv('MYSQL_PORT')}")

print("\n" + "=" * 60)
print("CONFIG.PY CHECK")
print("=" * 60)

from config import DB_TYPE as CONFIG_DB_TYPE
from config import MYSQL_HOST, MYSQL_USER, MYSQL_DB, MYSQL_PORT

print(f"config.DB_TYPE: {CONFIG_DB_TYPE}")
print(f"config.MYSQL_HOST: {MYSQL_HOST}")
print(f"config.MYSQL_USER: {MYSQL_USER}")
print(f"config.MYSQL_DB: {MYSQL_DB}")
print(f"config.MYSQL_PORT: {MYSQL_PORT}")

print("\n" + "=" * 60)
if CONFIG_DB_TYPE == "SQLITE":
    print("❌ PROBLEM: System is configured to use SQLITE")
    print("   This is why the web portal shows empty data!")
    print("   SQLite database is empty, MySQL has the data")
elif CONFIG_DB_TYPE == "MYSQL":
    print("✅ System is configured to use MYSQL")
else:
    print(f"⚠️ Unknown DB_TYPE: {CONFIG_DB_TYPE}")

print("=" * 60)
