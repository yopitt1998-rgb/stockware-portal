"""
Complete simulation of what web_server.py index route does
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("SIMULATING WEB SERVER INDEX ROUTE")
print("=" * 70)

from database import (
    obtener_nombres_moviles,
    obtener_todos_los_skus_para_movimiento,
    obtener_detalles_moviles
)
from config import DB_TYPE, MYSQL_HOST, MYSQL_DB

status = "OK"
error_detail = ""
count_m = 0
count_p = 0

try:
    print("\n1. Calling obtener_nombres_moviles()...")
    moviles = obtener_nombres_moviles()
    print(f"   Result: {moviles}")
    count_m = len(moviles)
    
    print("\n2. Calling obtener_todos_los_skus_para_movimiento()...")
    productos = obtener_todos_los_skus_para_movimiento()
    print(f"   Count: {len(productos)}")
    if len(productos) > 0:
        print(f"   First 3: {productos[:3]}")
    count_p = len(productos)
    
    print("\n3. Calling obtener_detalles_moviles()...")
    details_moviles = obtener_detalles_moviles()
    print(f"   Count: {len(details_moviles)}")
    
    if count_m == 0 and count_p == 0:
        status = "BASE DE DATOS VACÍA"
        error_detail = f"Conectado a DB: '{MYSQL_DB}' en {MYSQL_HOST}. No se encontraron productos ni móviles."
        
except Exception as e:
    status = "ERROR DE CONEXIÓN"
    error_detail = str(e)
    moviles = []
    productos = []
    details_moviles = {}

print("\n" + "=" * 70)
print("RESULT THAT WOULD BE SENT TO TEMPLATE")
print("=" * 70)
print(f"db_status: {status}")
print(f"db_engine: {DB_TYPE}")
print(f"count_m: {count_m}")
print(f"count_p: {count_p}")
print(f"error_detail: {error_detail}")
print(f"moviles list: {moviles if 'moviles' in locals() else 'NOT DEFINED'}")

print("\n" + "=" * 70)
if status == "OK":
    print("✅ WEB SERVER WOULD SHOW: OK")
    print(f"   Móviles dropdown would have {count_m} options")
    print(f"   Materials list would have {count_p} items")
elif status == "BASE DE DATOS VACÍA":
    print("❌ WEB SERVER WOULD SHOW: BASE DE DATOS VACÍA")
    print("   This is what the user is seeing!")
else:
    print(f"❌ WEB SERVER WOULD SHOW: {status}")

print("=" * 70)
