import database

def search_serial_everywhere(serial):
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    print(f"Searching for: {serial}")
    
    # 1. Search in series_registradas
    cursor.execute("SELECT * FROM series_registradas WHERE serial_number = %s OR mac_number = %s", (serial, serial))
    res = cursor.fetchall()
    print("\n[series_registradas]:", res)
    
    # 2. Search in movimientos (observations)
    cursor.execute("SELECT id, tipo_movimiento, movil_afectado, documento_referencia, observaciones FROM movimientos WHERE observaciones LIKE %s", (f"%{serial}%",))
    res = cursor.fetchall()
    print("\n[movimientos - observations]:", res)
    
    # 3. Search in movimientos (documento_referencia)
    cursor.execute("SELECT id, tipo_movimiento, movil_afectado, documento_referencia, observaciones FROM movimientos WHERE documento_referencia LIKE %s", (f"%{serial}%",))
    res = cursor.fetchall()
    print("\n[movimientos - doc_ref]:", res)

    # 4. Search in consumos_pendientes
    cursor.execute("SELECT * FROM consumos_pendientes WHERE seriales_usados LIKE %s", (f"%{serial}%",))
    res = cursor.fetchall()
    print("\n[consumos_pendientes]:", res)

if __name__ == "__main__":
    search_serial_everywhere("GZ25040112723608")
