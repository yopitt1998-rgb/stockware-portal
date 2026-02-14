
from config import *
print(f"DB_TYPE: {DB_TYPE}")
print(f"MYSQL_HOST: {MYSQL_HOST}")
print(f"MYSQL_DB: {MYSQL_DB}")

try:
    from database import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1")
    print("Connection successful")
    c.execute("SELECT COUNT(*) FROM asignacion_moviles")
    print(f"Count Assignments: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM productos WHERE ubicacion='BODEGA'")
    print(f"Count Bodega Products: {c.fetchone()[0]}")
    
    # Check specific SKU '7-1-171' (Cable UTP) which we saw in assignment
    c.execute("SELECT * FROM productos WHERE sku='7-1-171' AND ubicacion='BODEGA'")
    print(f"Cable UTP in Bodega: {c.fetchone()}")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")

with open("results.txt", "w", encoding="utf-8") as f:
    f.write(f"DB_TYPE: {DB_TYPE}\n")
    f.write(f"MYSQL_HOST: {MYSQL_HOST}\n")
    f.write(f"MYSQL_DB: {MYSQL_DB}\n")
    try:
        from database import get_db_connection
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT 1")
        c.fetchone()
        f.write("Connection successful\n")
        
        c.execute("SELECT COUNT(*) FROM asignacion_moviles")
        f.write(f"Count Assignments: {c.fetchone()[0]}\n")
        
        c.execute("SELECT COUNT(*) FROM productos WHERE ubicacion='BODEGA'")
        f.write(f"Count Bodega Products: {c.fetchone()[0]}\n")
        
        c.execute("SELECT * FROM productos WHERE sku='7-1-171' AND ubicacion='BODEGA'")
        f.write(f"Cable UTP in Bodega: {c.fetchone()}\n")
        
        conn.close()
    except Exception as e:
        f.write(f"Error: {e}\n")
