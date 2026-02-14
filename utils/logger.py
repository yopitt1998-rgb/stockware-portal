"""
Sistema de Logging Centralizado para StockWare

Este módulo proporciona un sistema de logging robusto con:
- Rotación automática de archivos
- Niveles configurables por ambiente
- Formato uniforme y legible
- Logging a archivo y consola
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Detectar ruta base para archivos de log
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directorio de logs
LOG_DIR = os.path.join(application_path, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Configuración de niveles según ambiente
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

# Formato de log
LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class StockWareLogger:
    """Gestor centralizado de logging para StockWare"""
    
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Obtiene o crea un logger específico.
        
        Args:
            name: Nombre del logger (usualmente __name__ del módulo)
            
        Returns:
            Logger configurado
        """
        if name in cls._loggers:
            return cls._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        
        # Evitar duplicación de handlers
        if logger.handlers:
            return logger
        
        # Handler para archivo principal con rotación
        main_log_file = os.path.join(LOG_DIR, 'stockware.log')
        file_handler = RotatingFileHandler(
            main_log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        
        # Handler para errores (archivo separado)
        error_log_file = os.path.join(LOG_DIR, 'errors.log')
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        
        # Handler para consola (solo en desarrollo)
        if os.getenv('DEV_MODE', 'false').lower() == 'true':
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter(
                '%(levelname)-8s | %(name)-15s | %(message)s'
            ))
            logger.addHandler(console_handler)
        
        logger.addHandler(file_handler)
        logger.addHandler(error_handler)
        
        cls._loggers[name] = logger
        return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Función helper para obtener un logger.
    
    Args:
        name: Nombre del logger. Si es None, usa el nombre del módulo llamante.
        
    Returns:
        Logger configurado
        
    Ejemplo:
        >>> from utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Mensaje informativo")
    """
    if name is None:
        # Intentar obtener el nombre del módulo que llama
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'stockware')
    
    return StockWareLogger.get_logger(name)


def log_function_call(func):
    """
    Decorador para loggear llamadas a funciones.
    
    Útil para debugging de funciones críticas.
    
    Ejemplo:
        >>> @log_function_call
        >>> def mi_funcion(param1, param2):
        >>>     return param1 + param2
    """
    import functools
    
    logger = get_logger(func.__module__)
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"Llamando {func.__name__} con args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completado exitosamente")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} falló: {e}", exc_info=True)
            raise
    
    return wrapper


def log_startup():
    """Registra información de inicio de la aplicación"""
    logger = get_logger('startup')
    logger.info("=" * 70)
    logger.info("STOCKWARE - Sistema de Gestión de Inventario")
    logger.info(f"Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Nivel de log: {LOG_LEVEL}")
    logger.info(f"Directorio de logs: {LOG_DIR}")
    logger.info(f"Modo desarrollo: {os.getenv('DEV_MODE', 'false')}")
    logger.info(f"Auto-login: {os.getenv('DEV_AUTO_LOGIN', 'false')}")
    logger.info(f"Tipo de DB: {os.getenv('DB_TYPE', 'SQLITE')}")
    logger.info("=" * 70)


def cleanup_old_logs(days: int = 30):
    """
    Limpia logs antiguos para evitar acumulación.
    
    Args:
        days: Eliminar logs más antiguos que este número de días
    """
    logger = get_logger('cleanup')
    try:
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for filename in os.listdir(LOG_DIR):
            filepath = os.path.join(LOG_DIR, filename)
            if os.path.isfile(filepath):
                file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_modified < cutoff_date:
                    os.remove(filepath)
                    logger.info(f"Log antiguo eliminado: {filename}")
    except Exception as e:
        logger.error(f"Error limpiando logs antiguos: {e}")


# Inicializar al importar el módulo
if __name__ != '__main__':
    # Solo limpiar logs en producción, no en cada importación durante desarrollo
    if os.getenv('DEV_MODE', 'false').lower() != 'true':
        cleanup_old_logs(30)
