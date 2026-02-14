
from database import obtener_todos_los_skus_para_movimiento, get_db_connection
import config

def debug_sku_fetch():
    print("--- DEBUG SKU FETCH CLOUD ---")
    print(f"Config DB: {config.MYSQL_DB}")
    print(f"Config Host: {config.MYSQL_HOST}")
    
    conn = get_db_connection(target_db='MYSQL')
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE()")
        print(f"Connected to: {cursor.fetchone()[0]}")
    except Exception as e:
        print(f"Connection Error: {e}")
        
    print("\nCalling obtener_todos_los_skus_para_movimiento()...")
    try:
        items = obtener_todos_los_skus_para_movimiento()
        print(f"Items returned: {len(items)}")
        if len(items) > 0:
            print("First 3 items:")
            for i in items[:3]:
                print(i)
        else:
             print("returned empty list []")
             
    except Exception as e:
        print(f"CRITICAL ERROR calling function: {e}")

if __name__ == "__main__":
    debug_sku_fetch()
