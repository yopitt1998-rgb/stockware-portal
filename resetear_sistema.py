"""
Script para RESETEAR COMPLETAMENTE el sistema
ADVERTENCIA: Esto borrará TODOS los datos del inventario
"""
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

print("=" * 70)
print("⚠️  RESETEO COMPLETO DEL SISTEMA")
print("=" * 70)
print("\nEste script borrará:")
print("  ❌ Todos los productos")
print("  ❌ Todos los movimientos")
print("  ❌ Todos los consumos pendientes")
print("  ❌ Todos los préstamos")
print("  ❌ Todos los recordatorios")
print("  ❌ Todas las asignaciones de móviles")
print("\n⚠️  ESTA ACCIÓN NO SE PUEDE DESHACER ⚠️")
print("=" * 70)

confirmar1 = input("\n¿Estás SEGURO de que quieres borrar TODO? (escribe 'SI' en mayúsculas): ").strip()

if confirmar1 != "SI":
    print("\n✅ Operación cancelada. No se borró nada.")
    exit()

confirmar2 = input("\nÚltima confirmación. Escribe 'BORRAR TODO' para continuar: ").strip()

if confirmar2 != "BORRAR TODO":
    print("\n✅ Operación cancelada. No se borró nada.")
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
    
    print("\n🗑️ Borrando datos...")
    
    # Contar registros antes
    tablas = {
        'productos': 'SELECT COUNT(*) FROM productos',
        'movimientos': 'SELECT COUNT(*) FROM movimientos',
        'consumos_pendientes': 'SELECT COUNT(*) FROM consumos_pendientes',
        'prestamos': 'SELECT COUNT(*) FROM prestamos',
        'recordatorios': 'SELECT COUNT(*) FROM recordatorios',
        'asignaciones_moviles': 'SELECT COUNT(*) FROM asignaciones_moviles'
    }
    
    print("\n📊 Registros antes del borrado:")
    totales = {}
    for tabla, query in tablas.items():
        try:
            cursor.execute(query)
            count = cursor.fetchone()[0]
            totales[tabla] = count
            print(f"  - {tabla}: {count}")
        except:
            totales[tabla] = 0
            print(f"  - {tabla}: 0 (tabla no existe o vacía)")
    
    print("\n🗑️ Borrando...")
    
    # Borrar en orden (respetando foreign keys)
    orden_borrado = [
        'asignaciones_moviles',
        'recordatorios',
        'prestamos',
        'consumos_pendientes',
        'movimientos',
        'productos'
    ]
    
    for tabla in orden_borrado:
        try:
            cursor.execute(f"DELETE FROM {tabla}")
            print(f"  ✅ {tabla}: {totales.get(tabla, 0)} registros borrados")
        except Exception as e:
            print(f"  ⚠️ {tabla}: Error - {e}")
    
    conn.commit()
    
    print("\n" + "=" * 70)
    print("✅ SISTEMA RESETEADO COMPLETAMENTE")
    print("=" * 70)
    print("\n📋 Próximos pasos:")
    print("  1. Reinicia la aplicación")
    print("  2. Los móviles se mantendrán (no se borran)")
    print("  3. Puedes agregar productos nuevos desde cero")
    print("  4. O importar productos desde Excel")
    
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
