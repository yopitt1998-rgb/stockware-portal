
from database import get_db_connection, run_query
import config

def check_moviles_cloud():
    print("--- CHECKING MOVILES IN CLOUD DB ---")
    conn = get_db_connection(target_db='MYSQL')
    try:
        cursor = conn.cursor()
        run_query(cursor, "SELECT nombre, conductor, ayudante FROM moviles")
        rows = cursor.fetchall()
        print(f"Total moviles: {len(rows)}")
        for r in rows:
            print(r)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    check_moviles_cloud()
