import os
import sys
sys.path.append(os.getcwd())
try:
    from database import get_db_connection, close_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    target = 'MOVIL 206'
    print(f"--- INVESTIGACION PROFUNDA: {target} ---")
    
    # 1. Buscar en préstamos activos
    cursor.execute("SELECT * FROM prestamos_activos WHERE UPPER(TRIM(movil_destino)) = %s", (target,))
    rows = cursor.fetchall()
    print(f"PRESTAMOS_COUNT: {len(rows)}")
    for r in rows: print(f"PRESTAMO: {r}")
    
    # 2. Buscar en consumos pendientes
    cursor.execute("SELECT * FROM consumos_pendientes WHERE UPPER(TRIM(movil)) = %s", (target,))
    rows = cursor.fetchall()
    print(f"CONSUMOS_PENDIENTES_COUNT: {len(rows)}")
    for r in rows: print(f"CONSUMO_PENDIENTE: {r}")

    # 3. Buscar en movimientos recientes
    cursor.execute("SELECT * FROM movimientos WHERE UPPER(TRIM(detalle)) LIKE %s ORDER BY id DESC LIMIT 5", (f"%{target}%",))
    rows = cursor.fetchall()
    print(f"MOVIMIENTOS_RECIENTES_COUNT: {len(rows)}")
    for r in rows: print(f"MOVIMIENTO: {r}")

    close_connection(conn)
except Exception as e:
    print(f"ERROR: {e}")
