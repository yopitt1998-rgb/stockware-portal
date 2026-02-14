"""
Check the consumos_pendientes table to see submitted forms
"""
import os
from dotenv import load_dotenv
import mysql.connector
from datetime import datetime

load_dotenv()

print("=" * 70)
print("CONSUMOS PENDIENTES - FORMULARIOS ENVIADOS")
print("=" * 70)

try:
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        port=int(os.getenv("MYSQL_PORT", 3306))
    )
    cursor = conn.cursor()
    
    # Get all pending consumos
    cursor.execute("""
        SELECT id, movil, sku, cantidad, tecnico_nombre, ayudante_nombre, 
               ticket, colilla, num_contrato, fecha, estado, fecha_registro
        FROM consumos_pendientes
        ORDER BY fecha_registro DESC
    """)
    
    consumos = cursor.fetchall()
    
    print(f"\nTotal de formularios enviados: {len(consumos)}")
    
    if len(consumos) == 0:
        print("\n⚠️ No hay formularios pendientes en la base de datos")
    else:
        print("\n" + "=" * 70)
        print("FORMULARIOS RECIBIDOS:")
        print("=" * 70)
        
        for consumo in consumos:
            id_consumo, movil, sku, cantidad, tecnico, ayudante, ticket, colilla, contrato, fecha, estado, fecha_reg = consumo
            
            print(f"\n📋 ID: {id_consumo}")
            print(f"   Móvil: {movil}")
            print(f"   Técnico: {tecnico}")
            print(f"   Ayudante: {ayudante or 'N/A'}")
            print(f"   Fecha: {fecha}")
            print(f"   Colilla: {colilla}")
            print(f"   Contrato: {contrato}")
            print(f"   Material: {sku} x {cantidad}")
            print(f"   Estado: {estado}")
            print(f"   Registrado: {fecha_reg}")
            print("-" * 70)
    
    # Group by submission (same movil, fecha, tecnico)
    cursor.execute("""
        SELECT movil, fecha, tecnico_nombre, colilla, num_contrato, 
               COUNT(*) as materiales, fecha_registro
        FROM consumos_pendientes
        GROUP BY movil, fecha, tecnico_nombre, colilla, num_contrato, fecha_registro
        ORDER BY fecha_registro DESC
    """)
    
    reportes = cursor.fetchall()
    
    if reportes:
        print("\n" + "=" * 70)
        print("RESUMEN DE REPORTES:")
        print("=" * 70)
        
        for i, reporte in enumerate(reportes, 1):
            movil, fecha, tecnico, colilla, contrato, num_materiales, fecha_reg = reporte
            print(f"\n{i}. Reporte de {tecnico}")
            print(f"   Móvil: {movil}")
            print(f"   Fecha: {fecha}")
            print(f"   Colilla: {colilla}")
            print(f"   Contrato: {contrato}")
            print(f"   Materiales reportados: {num_materiales}")
            print(f"   Enviado: {fecha_reg}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("CÓMO VER ESTOS DATOS EN LA APLICACIÓN DE ESCRITORIO:")
    print("=" * 70)
    print("1. Abre la aplicación: python app_inventario.py")
    print("2. Ve a la pestaña '🔍 Auditoría Terreno'")
    print("3. Ahí verás todos los consumos pendientes para aprobar")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
