
import os
import sys
from database import get_db_connection, run_query
from config import PAQUETES_MATERIALES

def diagnose():
    print("--- DIAGNOSTIC START ---")
    try:
        conn = get_db_connection(target_db='MYSQL') # Force MySQL/Cloud connection
        cursor = conn.cursor()
        
        # 1. Check Products in BODEGA
        print("\n[CHECK 1] Products in BODEGA:")
        run_query(cursor, "SELECT COUNT(*) FROM productos WHERE ubicacion = 'BODEGA'")
        count_bodega = cursor.fetchone()[0]
        print(f"  Count: {count_bodega}")
        
        if count_bodega > 0:
            run_query(cursor, "SELECT sku, nombre FROM productos WHERE ubicacion = 'BODEGA' LIMIT 5")
            sample = cursor.fetchall()
            print("  Sample:", sample)
        else:
            print("  CRITICAL: No products in BODEGA! Portal will be empty.")

        # 2. Check Assignments for MOVIL 200 and MOVIL 201
        for movil in ['MOVIL 200', 'MOVIL 201']:
            print(f"\n[CHECK 2] Assignments for {movil}:")
            # Check raw count
            run_query(cursor, "SELECT COUNT(*) FROM asignacion_moviles WHERE movil = ?", (movil,))
            count = cursor.fetchone()[0]
            print(f"  Total raw assignments: {count}")
            
            if count > 0:
                # Check formatting and joins
                run_query(cursor, """
                    SELECT a.sku_producto, a.cantidad, a.paquete, p.nombre 
                    FROM asignacion_moviles a 
                    LEFT JOIN productos p ON a.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
                    WHERE a.movil = ? LIMIT 5
                """, (movil,))
                rows = cursor.fetchall()
                print("  Sample (SKU, Qty, Pkg, ProdName):")
                for row in rows:
                    sku, qty, pkg, name = row
                    status = "OK" if name else "MISSING IN BODEGA"
                    print(f"    - {sku} | {qty} | {pkg} | {name} [{status}]")

        # 3. Check Package Config vs DB
        print("\n[CHECK 3] Package Configuration:")
        pkg_skus = [item[0] for item in PAQUETES_MATERIALES.get('PAQUETE A', [])]
        print(f"  PAQUETE A SKUs (Config): {len(pkg_skus)} items")
        
        if count_bodega > 0:
            placeholders = ','.join(['?'] * len(pkg_skus))
            run_query(cursor, f"SELECT sku FROM productos WHERE ubicacion = 'BODEGA' AND sku IN ({placeholders})", pkg_skus)
            found_skus = {r[0] for r in cursor.fetchall()}
            missing = set(pkg_skus) - found_skus
            print(f"  SKUs from Config found in DB: {len(found_skus)}")
            if missing:
                print(f"  MISSING SKUs in DB: {missing}")
            else:
                print("  ALL Package A SKUs exist in DB.")

        conn.close()
        print("\n--- DIAGNOSTIC END ---")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose()
