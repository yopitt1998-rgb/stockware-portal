
import sys
import os

# Forzar encoding UTF-8 para evitar errores con emojis en terminales limitadas
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database import inicializar_bd, registrar_movimiento_gui, obtener_asignacion_movil_con_paquetes, run_query, get_db_connection
from config import MATERIALES_COMPARTIDOS

def sanitize(text):
    if not text: return ""
    return str(text).encode('ascii', 'ignore').decode('ascii')

def test_reproduce():
    print("Iniciando prueba de reproduccion...")
    # Asegurar que la BD este inicializada
    inicializar_bd()
    
    movil = "Movil 201"
    sku_material = "1-8-40" # FAJILLA_8 (Esta en MATERIALES_COMPARTIDOS)
    sku_equipo = "4-4-644"   # ONT (No esta en MATERIALES_COMPARTIDOS)
    paquete_a = "PAQUETE A"
    paquete_b = "PAQUETE B"
    fecha = "2026-02-24"
    
    # 1. Limpiar datos previos para el movil
    print(f"Limpiando datos para {movil}...")
    conn = get_db_connection()
    cursor = conn.cursor()
    run_query(cursor, "DELETE FROM asignacion_moviles WHERE movil = ?", (movil,))
    run_query(cursor, "DELETE FROM movimientos WHERE movil_afectado = ?", (movil,))
    conn.commit()
    conn.close()
    
    # 2. Asignar material a Paquete A
    print(f"Asignando {sku_material} (Material) a {paquete_a}...")
    ok, msg = registrar_movimiento_gui(sku_material, 'SALIDA_MOVIL', 10, movil, fecha, paquete_a)
    print(f"Resultado: {sanitize(msg)}")
    
    # 3. Asignar equipo a Paquete A
    print(f"Asignando {sku_equipo} (Equipo) a {paquete_a}...")
    ok, msg = registrar_movimiento_gui(sku_equipo, 'SALIDA_MOVIL', 1, movil, fecha, paquete_a)
    print(f"Resultado: {sanitize(msg)}")
    
    # 4. Consultar resultados
    print("\nConsultando asignacion con paquetes...")
    resultados = obtener_asignacion_movil_con_paquetes(movil)
    
    for res in resultados:
        # (nombre, sku, total, paq_a, paq_b, carro, sin_paquete, personalizado)
        nombre, sku, total, paq_a, paq_b, carro, sin_p, pers = res
        print(f"\nSKU: {sku} ({sanitize(nombre)})")
        print(f"  Total Real: {total}")
        print(f"  En PAQUETE A: {paq_a}")
        print(f"  En PAQUETE B: {paq_b}")
        
        if sku == sku_material:
            if paq_b > 0:
                print("  RESULTADO: El material asignado a A aparece en B! (BUG CONFIRMADO)")
            else:
                print("  RESULTADO: El material solo aparece en A. (OK)")
                
        if sku == sku_equipo:
            if paq_b > 0:
                print("  RESULTADO: El equipo asignado a A aparece en B! (BUG CONFIRMADO)")
            else:
                print("  RESULTADO: El equipo solo aparece en A. (OK)")

if __name__ == "__main__":
    test_reproduce()
