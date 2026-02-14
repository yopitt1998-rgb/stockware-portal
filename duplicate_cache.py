"""
Módulo de gestión optimizada de duplicados con caché
"""
import os
import json
from datetime import datetime, timedelta

CACHE_FILE = "duplicates_check_cache.json"
CACHE_DURATION_HOURS = 24  # Ejecutar limpieza solo una vez al día

def should_run_duplicate_check():
    """
    Verifica si debe ejecutarse la verificación de duplicados basándose en caché.
    Retorna True si debe ejecutarse, False si ya se ejecutó recientemente.
    """
    if not os.path.exists(CACHE_FILE):
        return True
    
    try:
        with open(CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
        
        last_run = datetime.fromisoformat(cache_data.get('last_run', '2000-01-01'))
        now = datetime.now()
        
        # Ejecutar solo si han pasado más de CACHE_DURATION_HOURS
        if now - last_run > timedelta(hours=CACHE_DURATION_HOURS):
            return True
        
        return False
        
    except Exception as e:
        print(f"Error leyendo caché de duplicados: {e}")
        return True

def update_duplicate_check_cache():
    """Actualiza el caché con la fecha/hora de última ejecución."""
    try:
        cache_data = {
            'last_run': datetime.now().isoformat(),
            'version': '1.0'
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        print(f"✅ Caché de verificación de duplicados actualizado")
        
    except Exception as e:
        print(f"⚠️ Error actualizando caché: {e}")

def force_duplicate_check():
    """Fuerza la ejecución de la verificación eliminando el caché."""
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            print("🔄 Caché de duplicados eliminado, se forzará verificación")
    except Exception as e:
        print(f"Error eliminando caché: {e}")
