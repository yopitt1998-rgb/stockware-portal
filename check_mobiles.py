
from database import get_db_connection, run_query

def check_mobile_names():
    conn = get_db_connection()
    c = conn.cursor()
    
    print("--- Mobile Names in Assign Table ---")
    run_query(c, "SELECT DISTINCT movil FROM asignacion_moviles")
    db_mobiles = [r[0] for r in c.fetchall()]
    for m in db_mobiles:
        print(f"'{m}' (len={len(m)})")
        
    print("\n--- Mobile Names in Config ---")
    from config import MOVILES_DISPONIBLES, MOVILES_SANTIAGO
    cfg_mobiles = MOVILES_DISPONIBLES + MOVILES_SANTIAGO
    for m in cfg_mobiles:
        print(f"'{m}' (len={len(m)})")
        
    print("\n--- Cross Check ---")
    vals = []
    for dbm in db_mobiles:
        if dbm not in cfg_mobiles:
             print(f"[WARN] '{dbm}' found in DB but NOT in Config!")
        else:
             print(f"[OK] '{dbm}' matches.")

    conn.close()

if __name__ == "__main__":
    check_mobile_names()
