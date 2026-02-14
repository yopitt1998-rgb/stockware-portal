
from database import get_db_connection
import config

def list_dbs():
    print("--- LISTING DATABASES ---")
    conn = get_db_connection(target_db='MYSQL')
    try:
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        dbs = cursor.fetchall()
        for d in dbs:
            print(d[0])
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    list_dbs()
