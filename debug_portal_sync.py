
import sys
from database import get_db_connection, run_query
from config import MOVILES_DISPONIBLES, MOVILES_SANTIAGO

def test_portal_query(movil, f):
    try:
        f.write(f"\n--- Testing Portal Query for {movil} ---\n")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Check raw assignment
        f.write("1. Raw Assignment Table:\n")
        run_query(cursor, "SELECT sku_producto, cantidad, paquete FROM asignacion_moviles WHERE movil = ?", (movil,))
        raw = cursor.fetchall()
        for r in raw:
            f.write(f"   {r}\n")
            
        if not raw:
            f.write("   (No assignments found)\n")

        # 2. Check Products Table (BODEGA match)
        f.write("\n2. Products Table (BODEGA check for assigned SKUs):\n")
        for r in raw:
            sku = r[0]
            run_query(cursor, "SELECT sku, nombre, ubicacion FROM productos WHERE sku = ? AND ubicacion = 'BODEGA'", (sku,))
            prod = cursor.fetchone()
            if prod:
                f.write(f"   [OK] {sku} found in BODEGA: {prod}\n")
            else:
                f.write(f"   [FAIL] {sku} NOT found in BODEGA! This item will be hidden in portal.\n")

        # 3. Simulate Portal Query
        f.write("\n3. Full Portal Query Simulation:\n")
        sql = """
            SELECT p.nombre, a.sku_producto, a.cantidad, COALESCE(a.paquete, 'NINGUNO') as paquete
            FROM asignacion_moviles a
            JOIN productos p ON a.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
            WHERE a.movil = ?
            AND a.cantidad > 0
        """
        run_query(cursor, sql, (movil,))
        portal_res = cursor.fetchall()
        for r in portal_res:
            f.write(f"   {r}\n")
            
        if not portal_res:
            f.write("   (Query returned NO results - Portal will be empty)\n")

        conn.close()
    except Exception as e:
        f.write(f"ERROR: {e}\n")

if __name__ == "__main__":
    all_moviles = MOVILES_DISPONIBLES + MOVILES_SANTIAGO
    
    with open("debug_output.txt", "w", encoding="utf-8") as f:
        f.write(f"Checking {len(all_moviles)} mobiles...\n")
        
        try:
            conn = get_db_connection()
            c = conn.cursor()
            run_query(c, "SELECT COUNT(*) FROM asignacion_moviles")
            total_assignments = c.fetchone()[0]
            f.write(f"Total assignments in DB: {total_assignments}\n")
            conn.close()
        except Exception as e:
            sys.stderr.write(f"Error checking total assignments: {e}\n")
            f.write(f"Error checking total assignments: {e}\n")
        
        for movil in all_moviles:
            # Check if mobile has ANY assignment first to avoid spam
            try:
                conn = get_db_connection()
                c = conn.cursor()
                run_query(c, "SELECT COUNT(*) FROM asignacion_moviles WHERE movil = ?", (movil,))
                count = c.fetchone()[0]
                conn.close()
                
                if count > 0:
                    test_portal_query(movil, f)
            except Exception as e:
                f.write(f"Error checking movil {movil}: {e}\n")
