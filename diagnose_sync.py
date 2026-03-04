
import sqlite3
import os
import sys
from dotenv import load_dotenv

# Load Environment
load_dotenv()

# Build Paths
application_path = os.getcwd()
db_path = os.path.join(application_path, 'inventario_sqlite.db')

print(f"--- DIAGNOSTIC: SYNC DISCREPANCY ---")

# 1. LOCAL DATA
if not os.path.exists(db_path):
    print(f"Error: Local DB not found at {db_path}")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get local mobiles
        cursor.execute("SELECT nombre FROM moviles WHERE activo = 1")
        local_moviles = [r[0] for r in cursor.fetchall()]

        # Get mobiles with assignments
        cursor.execute("SELECT DISTINCT movil FROM asignacion_moviles WHERE cantidad > 0")
        assigned_moviles = [r[0] for r in cursor.fetchall()]

        conn.close()

        print(f"\n[LOCAL] Mobiles in 'moviles' table ({len(local_moviles)}):")
        for m in sorted(local_moviles):
            print(f" - {m}")

        print(f"\n[LOCAL] Mobiles with active assignments ({len(assigned_moviles)}):")
        for m in sorted(assigned_moviles):
            status = "⚠️ MISSING from 'moviles' table!" if m not in local_moviles else "✅ OK"
            print(f" - {m} ({status})")
    except Exception as e:
        print(f"Error reading local DB: {e}")

# 2. CLOUD DATA (Simulated if connection fails)
print("\n[CLOUD] Checking cloud connection...")
try:
    # Use database helper if possible
    sys.path.append(application_path)
    from database import get_db_connection, DB_TYPE
    from config import ALL_MOVILES
    
    print(f"DB_TYPE: {DB_TYPE}")
    print(f"Hardcoded ALL_MOVILES ({len(ALL_MOVILES)}): {ALL_MOVILES[:5]}...")

    conn_cloud = get_db_connection() # Will use cloud config if DB_TYPE='MYSQL'
    cursor_cloud = conn_cloud.cursor()
    
    # Check cloud moviles table
    try:
        cursor_cloud.execute("SELECT nombre FROM moviles")
        cloud_moviles = [r[0] for r in cursor_cloud.fetchall()]
        print(f"\n[CLOUD] Mobiles in 'moviles' table ({len(cloud_moviles)}):")
        for m in sorted(cloud_moviles):
            print(f" - {m}")
        
        # Compare with local
        missing_on_cloud = set(local_moviles) - set(cloud_moviles)
        if missing_on_cloud:
            print(f"\n⚠️ WARNING: {len(missing_on_cloud)} mobiles missing on cloud: {missing_on_cloud}")
        else:
            print(f"\n✅ SUCCESS: All {len(local_moviles)} local mobiles are present on cloud.")
            
    except Exception as e:
        print(f"Error reading cloud 'moviles' table: {e}")

    # Check cloud assignments
    try:
        cursor_cloud.execute("SELECT DISTINCT movil FROM asignacion_moviles WHERE cantidad > 0")
        cloud_assigned = [r[0] for r in cursor_cloud.fetchall()]
        print(f"\n[CLOUD] Mobiles with assignments on CLOUD ({len(cloud_assigned)}):")
        for m in sorted(cloud_assigned):
            in_hardcoded = "IN hardcoded" if m in ALL_MOVILES else "⚠️ NOT in hardcoded"
            print(f" - {m} ({in_hardcoded})")
    except Exception as e:
        print(f"Error reading cloud 'asignacion_moviles': {e}")

    conn_cloud.close()

except Exception as e:
    print(f"Error connecting to cloud: {e}")
