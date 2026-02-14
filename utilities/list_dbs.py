
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    port=int(os.getenv("MYSQL_PORT", 3306))
)
cursor = conn.cursor()
cursor.execute("SHOW DATABASES")
for (db,) in cursor.fetchall():
    print(db)
conn.close()
