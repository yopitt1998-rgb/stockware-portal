
import sqlite3
import json

def dump_moviles():
    conn = sqlite3.connect("inventario_sqlite.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nombre, conductor, ayudante, patente FROM moviles WHERE activo = 1")
    rows = cursor.fetchall()
    conn.close()
    
    data = {}
    for r in rows:
        # Fallback for None
        cond = r[1] if r[1] else ""
        ayu = r[2] if r[2] else ""
        pat = r[3] if r[3] else ""
        
        data[r[0]] = {
            "conductor": cond,
            "ayudante": ayu,
            "patente": pat
        }
    
    print("START_JSON")
    print(json.dumps(data, indent=4, ensure_ascii=False))
    print("END_JSON")

if __name__ == "__main__":
    dump_moviles()
