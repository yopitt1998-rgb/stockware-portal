
import os
import sys
import time
import logging

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection, run_query
import config

def diagnose():
    print("--- STARTUP DIAGNOSIS ---")
    print(f"DB_TYPE: {config.DB_TYPE}")
    print(f"MYSQL_HOST: {config.MYSQL_HOST}")
    print(f"MYSQL_DATABASE: {config.MYSQL_DB}")
    
    start_time = time.time()
    try:
        print("Connecting to DB...")
        conn = get_db_connection()
        print(f"Connected in {time.time() - start_time:.2f}s")
        cursor = conn.cursor()
        
        # Test a simple query
        print("Testing SELECT 1...")
        t0 = time.time()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        print(f"SELECT 1 took {time.time() - t0:.2f}s")

        print("Testing SHOW TABLES...")
        t0 = time.time()
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"SHOW TABLES took {time.time() - t0:.2f}s. Found {len(tables)} tables.")
        
        # Test the mobile insertion that hung
        from config import ALL_MOVILES
        print(f"Testing {len(ALL_MOVILES)} mobile insertions (INSERT IGNORE)...")
        for mv in ALL_MOVILES:
            t_m = time.time()
            query = "INSERT IGNORE INTO moviles (nombre, activo) VALUES (%s, 1)" if config.DB_TYPE == 'MYSQL' else "INSERT OR IGNORE INTO moviles (nombre, activo) VALUES (?, 1)"
            run_query(cursor, query, (mv,))
            print(f"  - {mv}: {time.time() - t_m:.2f}s")
        
        print("Committing...")
        t_c = time.time()
        conn.commit()
        print(f"Commit took {time.time() - t_c:.2f}s")
        
        print(f"\nSUCCESS: Total time: {time.time() - start_time:.2f}s")
        
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    diagnose()
