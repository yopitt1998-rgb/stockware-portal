
from database import get_db_connection
import config

def list_tables():
    print("--- LISTING TABLES IN CLOUD DB ---")
    print(f"DB Config: {config.MYSQL_DB}")
    conn = get_db_connection(target_db='MYSQL')
    try:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"Total Tables: {len(tables)}")
        for t in tables:
            print(f"- {t[0]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    list_tables()
