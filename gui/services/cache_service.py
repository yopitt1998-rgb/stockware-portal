import threading
import logging
import time
from datetime import datetime
from database import (
    obtener_todos_los_skus_para_movimiento,
    obtener_nombres_moviles,
    obtener_tecnicos
)

logger = logging.getLogger(__name__)

class CacheService:
    """Manages local in-memory caching of frequently used database records."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CacheService, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self.products = []
        self.moviles = []
        self.tecnicos = []
        self.last_sync = None
        self.is_syncing = False
        self._initialized = True

    def refresh_cache(self, callback=None):
        """Asynchronously refresh the cache from the database."""
        if self.is_syncing: return
        
        def run_sync():
            self.is_syncing = True
            logger.info("🔄 [CACHE] Sincronizando datos con la nube...")
            try:
                # 1. Fetch SKUs
                raw_products = obtener_todos_los_skus_para_movimiento()
                # Store as list of dicts or objects for easier access
                self.products = [
                    {"nombre": p[0], "sku": p[1], "stock": p[2]} 
                    for p in raw_products
                ]
                
                # 2. Fetch Mobiles
                self.moviles = obtener_nombres_moviles()
                
                # 3. Fetch Technicians
                self.tecnicos = obtener_tecnicos(solo_activos=True)
                
                self.last_sync = datetime.now()
                logger.info(f"✅ [CACHE] Sincronización completada. {len(self.products)} productos cargados.")
                
                if callback: callback(True)
            except Exception as e:
                logger.error(f"❌ [CACHE] Error en la sincronización: {e}")
                if callback: callback(False, str(e))
            finally:
                self.is_syncing = False

        thread = threading.Thread(target=run_sync, daemon=True)
        thread.start()

    def get_products(self):
        return self.products

    def get_moviles(self):
        return self.moviles

    def get_tecnicos(self):
        return self.tecnicos
