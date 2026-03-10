import os
import sys
sys.path.append(os.getcwd())
try:
    from database import get_db_connection, close_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("CHECK_START")
    # Limpieza de espacios y mayúsculas
    target = 'MOVIL 206'
    
    cursor.execute("SELECT sku_producto, cantidad, paquete FROM asignacion_moviles WHERE UPPER(TRIM(movil)) = %s", (target,))
    rows = cursor.fetchall()
    print(f"ASIGNACION_COUNT: {len(rows)}")
    for r in rows:
        print(f"ASIGNACION_ITEM: {r}")
        
    cursor.execute("SELECT sku, serial_number, mac_number, estado, ubicacion FROM series_registradas WHERE UPPER(TRIM(ubicacion)) = %s", (target,))
    rows = cursor.fetchall()
    print(f"SERIES_COUNT: {len(rows)}")
    for r in rows:
        print(f"SERIES_ITEM: {r}")
    
    print("CHECK_END")
    close_connection(conn)
except Exception as e:
    print(f"ERROR: {e}")
