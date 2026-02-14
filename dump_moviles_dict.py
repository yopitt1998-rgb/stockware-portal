
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
        data[r[0]] = {
            "conductor": r[1] or "",
            "ayudante": r[2] or "",
            "patente": r[3] or ""
        }
    
    print("COPY THIS DICT:")
    print(json.dumps(data, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    dump_moviles()
