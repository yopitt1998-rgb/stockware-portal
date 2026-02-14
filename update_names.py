import sqlite3
import os
from config import DATABASE_NAME, PRODUCTOS_INICIALES

def update_product_names():
    print(f"Update DB: {DATABASE_NAME}")
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    count = 0
    for nombre_corto, sku, _ in PRODUCTOS_INICIALES:
        # Check current name
        cursor.execute("SELECT nombre FROM productos WHERE sku = ?", (sku,))
        row = cursor.fetchone()
        
        if row:
            current_name = row[0]
            if current_name != nombre_corto:
                print(f"Updating SKU {sku}: '{current_name}' -> '{nombre_corto}'")
                cursor.execute("UPDATE productos SET nombre = ? WHERE sku = ?", (nombre_corto, sku))
                count += 1
        else:
            print(f"SKU {sku} not found found in DB. Inserting...")
            # Optional: Insert if missing (though usually done by initializing script)
            cursor.execute("INSERT INTO productos (sku, nombre, ubicacion, cantidad) VALUES (?, ?, 'BODEGA', 0)", (sku, nombre_corto))
            count += 1

    conn.commit()
    conn.close()
    print(f"Updated {count} products.")

if __name__ == "__main__":
    update_product_names()
