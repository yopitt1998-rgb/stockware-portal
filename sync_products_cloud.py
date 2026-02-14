
from database import get_db_connection, run_query
from config import PRODUCTOS_INICIALES

def sync_products():
    print("Syncing products to Cloud DB...")
    conn = get_db_connection(target_db='MYSQL')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT DATABASE()")
        print(f"Current Database: {cursor.fetchone()[0]}")
    except:
        pass
        
    print("Forcing USE test...")
    cursor.execute("USE test")


    
    added = 0
    for nombre, sku, secuencia in PRODUCTOS_INICIALES:
        # Check if exists in BODEGA
        run_query(cursor, "SELECT COUNT(*) FROM productos WHERE sku = ? AND ubicacion = 'BODEGA'", (sku,))
        exists = cursor.fetchone()[0]
        
        if not exists:
            print(f"Adding missing product: {sku} - {nombre}")
            sql = "INSERT INTO productos (nombre, sku, cantidad, ubicacion, secuencia_vista) VALUES (?, ?, ?, ?, ?)"
            run_query(cursor, sql, (nombre, sku, 0, "BODEGA", secuencia))
            added += 1
            
    conn.commit()
    conn.close()
    print(f"Sync complete. Added {added} products.")

if __name__ == "__main__":
    sync_products()
