
from database import get_db_connection, run_query
import sys

def audit_mobiles():
    mobiles = ["Movil 200", "Movil 201", "Movil 202", "Movil 203", "Movil 204", "Movil 205"]
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for movil in mobiles:
            print(f"\n=== AUDITORIA PARA {movil} ===")
            
            # 1. Total en asignacion_moviles
            run_query(cursor, "SELECT SUM(cantidad) FROM asignacion_moviles WHERE movil=%s", (movil,))
            total_asig = cursor.fetchone()[0] or 0
            print(f"Total asignado (tabla asignacion_moviles): {total_asig}")
            
            # 2. Conteo de SKUs
            run_query(cursor, "SELECT COUNT(*) FROM asignacion_moviles WHERE movil=%s AND cantidad > 0", (movil,))
            skus_count = cursor.fetchone()[0]
            print(f"Items con stock > 0: {skus_count}")
            
            # 3. Movimientos
            run_query(cursor, "SELECT COUNT(*) FROM movimientos WHERE movil_afectado=%s", (movil,))
            mov_count = cursor.fetchone()[0]
            print(f"Movimientos registrados: {mov_count}")
            
            if skus_count > 0:
                print("Muestra de items:")
                run_query(cursor, "SELECT sku_producto, paquete, cantidad FROM asignacion_moviles WHERE movil=%s AND cantidad > 0 LIMIT 5", (movil,))
                for r in cursor.fetchall():
                    print(f" - {r[0]} (Paq: {r[1]}): {r[2]}")
                    
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    audit_mobiles()
