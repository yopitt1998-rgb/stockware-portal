import sys
import os
sys.path.append(os.getcwd())

from utils.db_connector import get_db_connection, close_connection
from datetime import date

conn = None
try:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = date.today().isoformat()
    print(f"Checking registrations for date: {today}")
    
    query = """
        SELECT sku, COUNT(*) 
        FROM series_registradas 
        WHERE DATE(fecha_ingreso) = %s
        GROUP BY sku
    """
    cursor.execute(query, (today,))
    results = cursor.fetchall()
    if not results:
        print("No registrations found for today.")
    else:
        for sku, count in results:
            print(f"SKU: {sku} | Count: {count}")

except Exception as e:
    print(f"Error: {e}")
finally:
    if conn:
        close_connection(conn)
