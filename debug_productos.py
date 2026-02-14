from database import obtener_todos_los_skus_para_movimiento, obtener_nombres_moviles
from config import DB_TYPE, MYSQL_HOST, MYSQL_DB

print("="*60)
print("DIAGNÓSTICO RÁPIDO")
print("="*60)
print(f"DB_TYPE: {DB_TYPE}")
print(f"HOST: {MYSQL_HOST}")
print(f"DB: {MYSQL_DB}")
print("="*60)

try:
    # Test móviles
    moviles = obtener_nombres_moviles()
    print(f"\n✅ Móviles encontrados: {len(moviles)}")
    if moviles:
        print(f"   Primeros 3: {moviles[:3]}")
    
    # Test productos
    productos = obtener_todos_los_skus_para_movimiento()
    print(f"\n📦 Productos encontrados: {len(productos)}")
    if productos:
        print(f"   Primeros 5:")
        for nombre, sku, qty in productos[:5]:
            print(f"      {sku} | {nombre[:30]}")
    else:
        print("   ❌ LISTA VACÍA - Investigando...")
        
        # Verificar directamente en BD
        from database import get_db_connection, run_query
        conn = get_db_connection()
        cursor = conn.cursor()
        
        run_query(cursor, "SELECT COUNT(*) FROM productos")
        total = cursor.fetchone()[0]
        print(f"\n   Total en tabla productos: {total}")
        
        if total > 0:
            run_query(cursor, "SELECT DISTINCT nombre, sku FROM productos LIMIT 5")
            rows = cursor.fetchall()
            print(f"   Productos en BD (directo):")
            for nombre, sku in rows:
                print(f"      {sku} | {nombre}")
        
        conn.close()
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")

print("\n" + "="*60)
