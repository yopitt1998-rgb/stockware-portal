"""
Script rápido para borrar TODOS los consumos pendientes
"""
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

print("🗑️ BORRAR TODOS LOS CONSUMOS PENDIENTES")
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
    
    # Contar registros
    cursor.execute("SELECT COUNT(*) FROM consumos_pendientes")
    count = cursor.fetchone()[0]
    
    print(f"\n📊 Hay {count} registros en consumos_pendientes")
    
    if count == 0:
        print("\n✅ No hay registros para borrar")
    else:
        # Borrar todo
        cursor.execute("DELETE FROM consumos_pendientes")
        conn.commit()
        print(f"\n✅ Se borraron {count} registros exitosamente")
        print("\n⚡ La tabla está vacía ahora")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("Reinicia la aplicación para ver los cambios")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
