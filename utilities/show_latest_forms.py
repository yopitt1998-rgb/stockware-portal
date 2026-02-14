import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    port=int(os.getenv("MYSQL_PORT", 3306))
)
cursor = conn.cursor()

# Get latest submissions
cursor.execute("""
    SELECT movil, fecha, tecnico_nombre, ayudante_nombre, colilla, num_contrato,
           COUNT(*) as materiales, MAX(fecha_registro) as enviado
    FROM consumos_pendientes
    GROUP BY movil, fecha, tecnico_nombre, ayudante_nombre, colilla, num_contrato
    ORDER BY MAX(fecha_registro) DESC
    LIMIT 5
""")

reportes = cursor.fetchall()

print("\n🔔 ÚLTIMOS FORMULARIOS RECIBIDOS:")
print("=" * 70)

if not reportes:
    print("⚠️ No hay formularios en la base de datos")
else:
    for i, r in enumerate(reportes, 1):
        movil, fecha, tecnico, ayudante, colilla, contrato, num_mat, enviado = r
        print(f"\n{i}. Reporte #{i}")
        print(f"   📅 Fecha: {fecha}")
        print(f"   🚗 Móvil: {movil}")
        print(f"   👤 Técnico: {tecnico}")
        print(f"   👥 Ayudante: {ayudante or 'N/A'}")
        print(f"   📋 Colilla: {colilla}")
        print(f"   📄 Contrato: {contrato}")
        print(f"   📦 Materiales: {num_mat} items")
        print(f"   ⏰ Enviado: {enviado}")

# Show details of the most recent
if reportes:
    print("\n" + "=" * 70)
    print("DETALLE DEL ÚLTIMO REPORTE:")
    print("=" * 70)
    
    ultimo = reportes[0]
    movil, fecha, tecnico, ayudante, colilla, contrato = ultimo[:6]
    
    cursor.execute("""
        SELECT sku, cantidad, estado
        FROM consumos_pendientes
        WHERE movil = %s AND fecha = %s AND tecnico_nombre = %s 
          AND colilla = %s AND num_contrato = %s
        ORDER BY id DESC
    """, (movil, fecha, tecnico, colilla, contrato))
    
    materiales = cursor.fetchall()
    
    for sku, cant, estado in materiales:
        estado_icon = "✅" if estado == "AUDITADO" else "⏳"
        print(f"  {estado_icon} {sku}: {cant} unidades ({estado})")

conn.close()

print("\n" + "=" * 70)
print("Para procesar estos reportes:")
print("  1. Abre: python app_inventario.py")
print("  2. Ve a la pestaña '🔍 Auditoría Terreno'")
print("=" * 70)
