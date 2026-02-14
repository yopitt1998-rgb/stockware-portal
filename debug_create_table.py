
from database import get_db_connection
import config

def test_create():
    print("--- TESTING CREATE PERMISSION ---")
    conn = get_db_connection(target_db='MYSQL')
    try:
        cursor = conn.cursor()
        print("Attempting to create table 'test_perm'...")
        cursor.execute("CREATE TABLE IF NOT EXISTS test_perm (id INT)")
        print("SUCCESS: Table created.")
        cursor.execute("DROP TABLE test_perm")
        print("SUCCESS: Table dropped.")
    except Exception as e:
        print(f"FAILURE: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    test_create()
