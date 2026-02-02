"""
Script para borrar SOLO los productos y sus cantidades
(Mantiene movimientos, consumos, etc. para historial)
"""
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

print("=" * 70)
print("🗑️ BORRAR PRODUCTOS Y CANTIDADES")
print("=" * 70)
print("\nEste script borrará:")
print("  ❌ Todos los productos de la tabla 'productos'")
print("  ❌ Todas las cantidades en bodega y móviles")
print("\nSe mantendrán:")
print("  ✅ Movimientos (historial)")
print("  ✅ Consumos pendientes")
print("  ✅ Móviles")
print("=" * 70)

confirmar = input("\n¿Borrar todos los productos? (escribe 'SI'): ").strip()

if confirmar != "SI":
    print("\n✅ Operación cancelada")
    exit()

try:
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        port=int(os.getenv("MYSQL_PORT", 3306))
    )
    cursor = conn.cursor()
    
    # Contar productos
    cursor.execute("SELECT COUNT(*) FROM productos")
    count = cursor.fetchone()[0]
    
    print(f"\n📊 Hay {count} productos en el sistema")
    
    if count == 0:
        print("\n✅ No hay productos para borrar")
    else:
        # Borrar productos
        cursor.execute("DELETE FROM productos")
        conn.commit()
        print(f"\n✅ Se borraron {count} productos exitosamente")
        print("\n⚡ El inventario está vacío ahora")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("Reinicia la aplicación para ver los cambios")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
