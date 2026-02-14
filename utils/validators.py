"""
Sistema de Validación de Entrada para StockWare

Este módulo proporciona validadores reutilizables para asegurar
la integridad de los datos antes de procesarlos o guardarlos en la DB.
"""

import re
from datetime import datetime, date
from typing import Union, Optional, List
from utils.logger import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Excepción lanzada cuando falla una validación"""
    pass


def validate_sku(sku: str, allow_empty: bool = False) -> str:
    """
    Valida el formato de un SKU.
    
    Args:
        sku: Código SKU a validar
        allow_empty: Si True, permite strings vacíos
        
    Returns:
        SKU limpio y validado
        
    Raises:
        ValidationError: Si el SKU es inválido
        
    Ejemplo:
        >>> validate_sku("1-2-16")
        "1-2-16"
        >>> validate_sku("  7-1-171  ")
        "7-1-171"
    """
    if sku is None:
        raise ValidationError("SKU no puede ser None")
    
    sku = str(sku).strip()
    
    if not sku:
        if allow_empty:
            return ""
        raise ValidationError("SKU no puede estar vacío")
    
    # Formato esperado: X-Y-Z donde X, Y, Z son números
    # Ejemplos: 1-2-16, 7-1-171, U4-4-633
    if not re.match(r'^[U]?\d+-\d+-\d+$', sku):
        raise ValidationError(f"Formato de SKU inválido: '{sku}'. Esperado: 'X-Y-Z' (ej: 1-2-16)")
    
    return sku


def validate_quantity(cantidad: Union[int, float, str], 
                     allow_zero: bool = True,
                     allow_negative: bool = False,
                     max_value: Optional[float] = None) -> float:
    """
    Valida una cantidad.
    
    Args:
        cantidad: Cantidad a validar
        allow_zero: Si True, permite 0
        allow_negative: Si True, permite valores negativos
        max_value: Valor máximo permitido (opcional)
        
    Returns:
        Cantidad validada como float
        
    Raises:
        ValidationError: Si la cantidad es inválida
        
    Ejemplo:
        >>> validate_quantity(10)
        10.0
        >>> validate_quantity("5.5")
        5.5
        >>> validate_quantity(-1)  # Error si allow_negative=False
    """
    try:
        cantidad = float(cantidad)
    except (ValueError, TypeError):
        raise ValidationError(f"Cantidad inválida: '{cantidad}'. Debe ser un número")
    
    if not allow_zero and cantidad == 0:
        raise ValidationError("La cantidad no puede ser cero")
    
    if not allow_negative and cantidad < 0:
        raise ValidationError(f"La cantidad no puede ser negativa: {cantidad}")
    
    if max_value is not None and cantidad > max_value:
        raise ValidationError(f"La cantidad {cantidad} excede el máximo permitido: {max_value}")
    
    return cantidad


def validate_date(fecha: Union[str, date, datetime, None], 
                 allow_future: bool = True,
                 allow_none: bool = False) -> Optional[str]:
    """
    Valida y normaliza una fecha.
    
    Args:
        fecha: Fecha a validar (string, date, datetime o None)
        allow_future: Si True, permite fechas futuras
        allow_none: Si True, permite None (retorna None)
        
    Returns:
        Fecha en formato 'YYYY-MM-DD' o None
        
    Raises:
        ValidationError: Si la fecha es inválida
        
    Ejemplo:
        >>> validate_date("2026-02-10")
        "2026-02-10"
        >>> validate_date(date.today())
        "2026-02-10"
    """
    if fecha is None:
        if allow_none:
            return None
        raise ValidationError("La fecha no puede ser None")
    
    # Convertir a date si es necesario
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    elif isinstance(fecha, str):
        try:
            # Intentar parsear diferentes formatos
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                try:
                    fecha = datetime.strptime(fecha.strip(), fmt).date()
                    break
                except ValueError:
                    continue
            else:
                raise ValueError("Formato no reconocido")
        except ValueError:
            raise ValidationError(f"Formato de fecha inválido: '{fecha}'. Use YYYY-MM-DD")
    elif not isinstance(fecha, date):
        raise ValidationError(f"Tipo de fecha inválido: {type(fecha)}")
    
    # Validar fecha futura
    if not allow_future and fecha > date.today():
        raise ValidationError(f"La fecha no puede ser futura: {fecha}")
    
    return fecha.isoformat()


def validate_movil(movil: str, moviles_disponibles: List[str]) -> str:
    """
    Valida que un móvil exista en la lista de móviles disponibles.
    
    Args:
        movil: Nombre del móvil
        moviles_disponibles: Lista de móviles válidos
        
    Returns:
        Nombre del móvil validado
        
    Raises:
        ValidationError: Si el móvil no existe
        
    Ejemplo:
        >>> validate_movil("Movil 200", ["Movil 200", "Movil 201"])
        "Movil 200"
    """
    if movil is None:
        raise ValidationError("Móvil no puede ser None")
    
    movil = str(movil).strip()
    
    if not movil:
        raise ValidationError("Móvil no puede estar vacío")
    
    # Normalizar espacios y capitalización
    movil_normalized = ' '.join(movil.split())
    
    # Buscar coincidencia case-insensitive
    for movil_disponible in moviles_disponibles:
        if movil_normalized.lower() == movil_disponible.lower():
            return movil_disponible  # Retornar versión canónica
    
    raise ValidationError(
        f"Móvil '{movil}' no encontrado. Móviles disponibles: {', '.join(moviles_disponibles)}"
    )


def validate_tipo_movimiento(tipo: str, tipos_validos: List[str]) -> str:
    """
    Valida un tipo de movimiento.
    
    Args:
        tipo: Tipo de movimiento
        tipos_validos: Lista de tipos válidos
        
    Returns:
        Tipo de movimiento validado
        
    Raises:
        ValidationError: Si el tipo es inválido
    """
    if tipo is None:
        raise ValidationError("Tipo de movimiento no puede ser None")
    
    tipo = str(tipo).strip().upper()
    
    if not tipo:
        raise ValidationError("Tipo de movimiento no puede estar vacío")
    
    if tipo not in tipos_validos:
        raise ValidationError(
            f"Tipo de movimiento inválido: '{tipo}'. Tipos válidos: {', '.join(tipos_validos)}"
        )
    
    return tipo


def sanitize_string(texto: str, max_length: int = 500) -> str:
    """
    Limpia y sanitiza un string de entrada.
    
    Args:
        texto: Texto a limpiar
        max_length: Longitud máxima permitida
        
    Returns:
        Texto sanitizado
        
    Ejemplo:
        >>> sanitize_string("  Hola   mundo  ")
        "Hola mundo"
        >>> sanitize_string("<script>alert('xss')</script>")
        "scriptalert('xss')/script"
    """
    if texto is None:
        return ""
    
    texto = str(texto).strip()
    
    # Remover/escapar caracteres peligrosos
    texto = texto.replace('<', '&lt;').replace('>', '&gt;')
    texto = texto.replace(';', ',')  # Evitar SQL injection simple
    texto = texto.replace('--', '-')  # Evitar SQL comments
    
    # Normalizar espacios múltiples
    texto = ' '.join(texto.split())
    
    # Truncar si es muy largo
    if len(texto) > max_length:
        logger.warning(f"Texto truncado de {len(texto)} a {max_length} caracteres")
        texto = texto[:max_length]
    
    return texto


def validate_producto_exists(sku: str, conn) -> bool:
    """
    Valida que un producto exista en la base de datos.
    
    Args:
        sku: SKU del producto
        conn: Conexión a la base de datos
        
    Returns:
        True si existe, False si no
        
    Raises:
        ValidationError: Si hay error en la consulta
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM productos WHERE sku = ? LIMIT 1", (sku,))
        exists = cursor.fetchone() is not None
        cursor.close()
        
        if not exists:
            raise ValidationError(f"Producto con SKU '{sku}' no existe en la base de datos")
        
        return True
    except Exception as e:
        logger.error(f"Error validando existencia de producto {sku}: {e}")
        raise ValidationError(f"Error verificando producto: {e}")


def validate_observaciones(observaciones: Optional[str], max_length: int = 1000) -> Optional[str]:
    """
    Valida y sanitiza el campo de observaciones.
    
    Args:
        observaciones: Texto de observaciones
        max_length: Longitud máxima
        
    Returns:
        Observaciones sanitizadas o None
    """
    if observaciones is None or not observaciones.strip():
        return None
    
    return sanitize_string(observaciones, max_length)


def validate_paquete(paquete: str, paquetes_disponibles: dict) -> str:
    """
    Valida que un paquete exista.
    
    Args:
        paquete: Nombre del paquete
        paquetes_disponibles: Diccionario de paquetes disponibles
        
    Returns:
        Nombre del paquete validado
        
    Raises:
        ValidationError: Si el paquete no existe
    """
    if paquete is None:
        raise ValidationError("Paquete no puede ser None")
    
    paquete = str(paquete).strip()
    
    if not paquete:
        raise ValidationError("Paquete no puede estar vacío")
    
    if paquete not in paquetes_disponibles:
        raise ValidationError(
            f"Paquete '{paquete}' no existe. Paquetes disponibles: {', '.join(paquetes_disponibles.keys())}"
        )
    
    return paquete


# Función de validación compuesta para movimientos
def validate_movimiento_data(sku: str, cantidad: float, tipo_movimiento: str,
                             movil: Optional[str] = None,
                             fecha: Optional[str] = None) -> dict:
    """
    Valida todos los datos necesarios para registrar un movimiento.
    
    Args:
        sku: SKU del producto
        cantidad: Cantidad del movimiento
        tipo_movimiento: Tipo de movimiento
        movil: Móvil afectado (opcional)
        fecha: Fecha del movimiento (opcional)
        
    Returns:
        Diccionario con datos validados
        
    Raises:
        ValidationError: Si algún dato es inválido
    """
    from config import TIPOS_MOVIMIENTO, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, CURRENT_CONTEXT
    
    return {
        'sku': validate_sku(sku),
        'cantidad': validate_quantity(cantidad, allow_zero=False, allow_negative=False),
        'tipo_movimiento': validate_tipo_movimiento(tipo_movimiento, TIPOS_MOVIMIENTO),
        'movil': validate_movil(movil, CURRENT_CONTEXT['MOVILES']) if movil else None,
        'fecha': validate_date(fecha, allow_none=True)
    }
