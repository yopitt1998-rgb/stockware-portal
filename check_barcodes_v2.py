
from database import get_db_connection

def check_barcodes_v2():
    print("--- CHECKING BARCODES V2 ---")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get products with ANY barcode set
        query = "SELECT sku, nombre, codigo_barra, codigo_barra_maestro FROM productos WHERE codigo_barra IS NOT NULL OR codigo_barra_maestro IS NOT NULL LIMIT 20"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        print(f"Found {len(rows)} products with barcodes.")
        for r in rows:
            print(f"SKU: {r[0]:<10} | Master: {repr(r[3])} | Legacy: {repr(r[2])} | Name: {r[1][:30]}")
            
    except Exception as e:
        print(f"Error: {e}")
        
    conn.close()

if __name__ == "__main__":
    check_barcodes_v2()
