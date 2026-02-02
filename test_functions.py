import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("TESTING DATABASE FUNCTIONS")
print("=" * 60)

# Import the functions
from database import (
    obtener_nombres_moviles,
    obtener_todos_los_skus_para_movimiento,
    obtener_detalles_moviles,
    get_db_connection,
    run_query
)
from config import DB_TYPE

print(f"\n📊 DB_TYPE: {DB_TYPE}")

# Test 1: Direct query to productos
print("\n" + "=" * 60)
print("TEST 1: Direct query to productos table")
print("=" * 60)

try:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    run_query(cursor, "SELECT COUNT(*) FROM productos WHERE ubicacion = 'BODEGA'")
    count = cursor.fetchone()[0]
    print(f"✅ Total productos in BODEGA: {count}")
    
    if count > 0:
        run_query(cursor, "SELECT sku, nombre, secuencia_vista FROM productos WHERE ubicacion = 'BODEGA' LIMIT 5")
        productos = cursor.fetchall()
        print("\nFirst 5 products:")
        for p in productos:
            print(f"  SKU: {p[0]}, Nombre: {p[1]}, Secuencia: {p[2]}")
    
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Direct query to moviles
print("\n" + "=" * 60)
print("TEST 2: Direct query to moviles table")
print("=" * 60)

try:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    run_query(cursor, "SELECT COUNT(*) FROM moviles")
    count = cursor.fetchone()[0]
    print(f"✅ Total moviles: {count}")
    
    if count > 0:
        run_query(cursor, "SELECT nombre, activo FROM moviles LIMIT 5")
        moviles = cursor.fetchall()
        print("\nFirst 5 moviles:")
        for m in moviles:
            print(f"  Nombre: {m[0]}, Activo: {m[1]}")
    
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: obtener_todos_los_skus_para_movimiento()
print("\n" + "=" * 60)
print("TEST 3: obtener_todos_los_skus_para_movimiento()")
print("=" * 60)

try:
    productos = obtener_todos_los_skus_para_movimiento()
    print(f"✅ Function returned {len(productos)} products")
    
    if len(productos) > 0:
        print("\nFirst 5 products:")
        for p in productos[:5]:
            print(f"  {p}")
    else:
        print("⚠️ Function returned empty list!")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 4: obtener_nombres_moviles()
print("\n" + "=" * 60)
print("TEST 4: obtener_nombres_moviles()")
print("=" * 60)

try:
    moviles = obtener_nombres_moviles()
    print(f"✅ Function returned {len(moviles)} moviles")
    
    if len(moviles) > 0:
        print("\nMoviles:")
        for m in moviles:
            print(f"  {m}")
    else:
        print("⚠️ Function returned empty list!")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: obtener_detalles_moviles()
print("\n" + "=" * 60)
print("TEST 5: obtener_detalles_moviles()")
print("=" * 60)

try:
    detalles = obtener_detalles_moviles()
    print(f"✅ Function returned {len(detalles)} moviles with details")
    
    if len(detalles) > 0:
        print("\nMoviles details:")
        for nombre, info in detalles.items():
            print(f"  {nombre}: Conductor={info.get('conductor', 'N/A')}, Ayudante={info.get('ayudante', 'N/A')}")
    else:
        print("⚠️ Function returned empty dict!")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TESTING COMPLETED")
print("=" * 60)
