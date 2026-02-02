def limpiar_base_datos():
    """
    Limpia todos los movimientos y datos de la base de datos, manteniendo solo la estructura.
    ADVERTENCIA: Esta operación es irreversible.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Limpiar todas las tablas de datos
        tablas_a_limpiar = [
            'movimientos',
            'asignacion_moviles',
            'consumos_pendientes',
            'recordatorios_pendientes',
            'prestamos_activos'
        ]
        
        for tabla in tablas_a_limpiar:
            run_query(cursor, f"DELETE FROM {tabla}")
        
        # Resetear cantidades de productos a 0
        run_query(cursor, "UPDATE productos SET cantidad = 0")
        
        conn.commit()
        return True, "Base de datos limpiada exitosamente. Todos los movimientos y datos han sido eliminados."
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Error al limpiar la base de datos: {str(e)}"
    finally:
        if conn: conn.close()
