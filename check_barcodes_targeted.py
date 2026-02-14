
from database import get_db_connection

def check_barcodes_targeted():
    print("--- TARGETED BARCODE CHECK ---")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    target_skus = ['7-1-171', '10-1-04', '1-2-16']
    
    for sku in target_skus:
        print(f"\nChecking SKU: {sku}")
        # MySQL uses %s, SQLite uses ?. Since config.DB_TYPE is MYSQL, use %s
        cursor.execute("SELECT sku, nombre, codigo_barra, codigo_barra_maestro FROM productos WHERE sku = %s", (sku,))
        row = cursor.fetchone()
        
        if row:
            print(f"  Found: {row[0]}")
            print(f"  Legacy Barcode: {repr(row[2])}")
            print(f"  Master Barcode: {repr(row[3])}")
        else:
            print("  Not Found in DB")
            
    conn.close()

if __name__ == "__main__":
    check_barcodes_targeted()
