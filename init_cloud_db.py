
import sys
import os

# 1. Force DB_TYPE to MYSQL in config before importing database
# This is tricky because config.py is imported by database.py
# We can modify sys.modules or just patch after import if the module uses the variable dynamically.

import config
config.DB_TYPE = 'MYSQL'

import database
database.DB_TYPE = 'MYSQL'

# Patch get_db_connection to always return MySQL connection for this script
original_get_db = database.get_db_connection
def forced_mysql_conn(target_db=None):
    return original_get_db(target_db='MYSQL')
    
database.get_db_connection = forced_mysql_conn

from database import inicializar_bd

print("--- INITIALIZING CLOUD DB (FORCED MYSQL) ---")
try:
    if inicializar_bd():
        print("✅ Cloud DB Initialized Successfully.")
    else:
        print("❌ Initialization returned False.")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
