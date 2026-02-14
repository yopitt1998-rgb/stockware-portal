
from database import get_db_connection, run_query

def check_barcodes():
    print("--- CHECKING BARCODES IN DB ---")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if columns exist
        cursor.execute("SHOW COLUMNS FROM productos LIKE 'codigo%'")
        cols = cursor.fetchall()
        print(f"Barcode Columns: {[c[0] for c in cols]}")
        
        # Check sample data
        print("\nSample Products with Barcodes:")
        query = "SELECT sku, nombre, codigo_barra, codigo_barra_maestro FROM productos WHERE codigo_barra IS NOT NULL OR codigo_barra_maestro IS NOT NULL LIMIT 10"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("  (No products have barcodes assigned)")
        else:
            for r in rows:
                print(f"  SKU: {r[0]} | Name: {r[1]} | Code: {r[2]} | Master: {r[3]}")
                
    except Exception as e:
        print(f"Error: {e}")
        
    conn.close()

if __name__ == "__main__":
    check_barcodes()
