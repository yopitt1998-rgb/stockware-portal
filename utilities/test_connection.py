from config import MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT
import mysql.connector

config = {
    'host': MYSQL_HOST,
    'user': MYSQL_USER,
    'password': MYSQL_PASS,
    'database': MYSQL_DB,
    'port': MYSQL_PORT,
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

print(f"Testing connection to {config['host']} on port {config['port']}...")
print(f"User: {config['user']}")
print(f"Database: {config['database']}")

try:
    conn = mysql.connector.connect(**config)
    print("✅ Connection successful!")
    conn.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
