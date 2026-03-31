"""
Tests básicos para StockWare — data_layer/movements.py
Usa SQLite en memoria para no tocar MySQL de producción.
Ejecutar con: pytest tests/ -v
"""
import sqlite3
import sys
import os
import pytest
from datetime import date

# Asegurar que el path raíz esté en sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ──────────────────────────────────────────────
# Fixtures: BD SQLite en memoria aislada por test
# ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_db_type(monkeypatch):
    """Fuerza DB_TYPE=SQLITE para todos los tests."""
    import config
    monkeypatch.setattr(config, 'DB_TYPE', 'SQLITE')
    monkeypatch.setattr(config, 'DATABASE_NAME', ':memory:')


@pytest.fixture
def in_memory_conn():
    """Crea una BD SQLite en memoria con el esquema mínimo necesario."""
    conn = sqlite3.connect(':memory:')
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre VARCHAR(255) NOT NULL,
            sku VARCHAR(50) NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            ubicacion VARCHAR(50) NOT NULL,
            minimo_stock INTEGER DEFAULT 10,
            categoria VARCHAR(100) DEFAULT 'General',
            marca VARCHAR(100) DEFAULT 'N/A',
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
            secuencia_vista VARCHAR(20),
            sucursal VARCHAR(50) DEFAULT 'CHIRIQUI',
            UNIQUE (sku, ubicacion, sucursal)
        );
        CREATE TABLE asignacion_moviles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_producto VARCHAR(50) NOT NULL,
            movil VARCHAR(100) NOT NULL,
            paquete VARCHAR(50),
            cantidad INTEGER NOT NULL DEFAULT 0,
            sucursal VARCHAR(50) DEFAULT 'CHIRIQUI',
            UNIQUE (sku_producto, movil, paquete, sucursal)
        );
        CREATE TABLE movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_producto VARCHAR(50) NOT NULL,
            tipo_movimiento VARCHAR(50) NOT NULL,
            cantidad_afectada INTEGER NOT NULL,
            movil_afectado VARCHAR(100),
            fecha_movimiento DATETIME DEFAULT CURRENT_TIMESTAMP,
            fecha_evento DATE,
            paquete_asignado VARCHAR(50),
            documento_referencia TEXT,
            observaciones TEXT,
            sucursal VARCHAR(50) DEFAULT 'CHIRIQUI'
        );
        CREATE TABLE series_registradas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku VARCHAR(50) NOT NULL,
            serial_number VARCHAR(100) NOT NULL,
            mac_number VARCHAR(100),
            ubicacion VARCHAR(100) DEFAULT 'BODEGA',
            movil VARCHAR(100),
            contrato VARCHAR(255),
            fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
            sucursal VARCHAR(50) DEFAULT 'CHIRIQUI',
            paquete VARCHAR(50),
            estado VARCHAR(50) DEFAULT 'DISPONIBLE'
        );
        CREATE TABLE recordatorios_pendientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movil VARCHAR(100) NOT NULL,
            paquete VARCHAR(50) NOT NULL,
            tipo_recordatorio VARCHAR(50) NOT NULL,
            fecha_recordatorio DATE NOT NULL,
            completado INTEGER DEFAULT 0,
            fecha_completado DATETIME
        );
        -- Datos iniciales de prueba
        INSERT INTO productos (nombre, sku, cantidad, ubicacion, sucursal, secuencia_vista)
            VALUES ('Cable Fiber', '1-2-16', 100, 'BODEGA', 'CHIRIQUI', '001');
        INSERT INTO productos (nombre, sku, cantidad, ubicacion, sucursal, secuencia_vista)
            VALUES ('ONT Huawei', '4-4-644', 10, 'BODEGA', 'CHIRIQUI', '018');
    """)
    conn.commit()
    return conn


# ──────────────────────────────────────────────
# Tests de registrar_movimiento_gui
# ──────────────────────────────────────────────

class TestRegistrarMovimiento:

    def test_salida_movil_reduce_bodega_y_suma_asignacion(self, in_memory_conn, monkeypatch):
        """SALIDA_MOVIL debe restar del stock en BODEGA y sumar a asignacion_moviles."""
        from data_layer.movements import registrar_movimiento_gui

        # Parchear get_db_connection para usar nuestra BD en memoria
        monkeypatch.setattr(
            'utils.db_connector.get_db_connection',
            lambda **kw: in_memory_conn
        )

        ok, msg = registrar_movimiento_gui(
            sku='1-2-16',
            tipo_movimiento='SALIDA_MOVIL',
            cantidad_afectada=10,
            movil_afectado='Movil 200',
            fecha_evento=date.today().isoformat(),
            sucursal_context='CHIRIQUI',
            existing_conn=in_memory_conn
        )

        assert ok, f"Se esperaba éxito, pero falló: {msg}"

        cur = in_memory_conn.cursor()
        cur.execute("SELECT cantidad FROM productos WHERE sku='1-2-16' AND ubicacion='BODEGA'")
        stock_bodega = cur.fetchone()[0]
        assert stock_bodega == 90, f"Esperado 90, obtenido {stock_bodega}"

        cur.execute("SELECT cantidad FROM asignacion_moviles WHERE sku_producto='1-2-16' AND movil='Movil 200'")
        asignado = cur.fetchone()
        assert asignado is not None, "No se encontró fila en asignacion_moviles"
        assert asignado[0] == 10, f"Esperado 10 asignado, obtenido {asignado[0]}"

    def test_salida_movil_falla_stock_insuficiente(self, in_memory_conn, monkeypatch):
        """SALIDA_MOVIL debe fallar si no hay suficiente stock en BODEGA."""
        from data_layer.movements import registrar_movimiento_gui

        monkeypatch.setattr(
            'utils.db_connector.get_db_connection',
            lambda **kw: in_memory_conn
        )

        ok, msg = registrar_movimiento_gui(
            sku='1-2-16',
            tipo_movimiento='SALIDA_MOVIL',
            cantidad_afectada=999,  # más del stock disponible (100)
            movil_afectado='Movil 200',
            fecha_evento=date.today().isoformat(),
            sucursal_context='CHIRIQUI',
            existing_conn=in_memory_conn
        )

        assert not ok, "Se esperaba fallo por stock insuficiente"
        assert 'insuficiente' in msg.lower() or 'Stock' in msg

    def test_retorno_movil_devuelve_a_bodega(self, in_memory_conn, monkeypatch):
        """RETORNO_MOVIL debe devolver unidades a BODEGA y restar de asignacion_moviles."""
        from data_layer.movements import registrar_movimiento_gui

        monkeypatch.setattr(
            'utils.db_connector.get_db_connection',
            lambda **kw: in_memory_conn
        )

        # Primero asignamos 20 unidades al móvil
        in_memory_conn.execute(
            "INSERT OR IGNORE INTO asignacion_moviles (sku_producto, movil, cantidad, sucursal) VALUES (?, ?, ?, ?)",
            ('1-2-16', 'Movil 201', 20, 'CHIRIQUI')
        )
        in_memory_conn.commit()

        ok, msg = registrar_movimiento_gui(
            sku='1-2-16',
            tipo_movimiento='RETORNO_MOVIL',
            cantidad_afectada=15,
            movil_afectado='Movil 201',
            fecha_evento=date.today().isoformat(),
            sucursal_context='CHIRIQUI',
            existing_conn=in_memory_conn
        )

        assert ok, f"Se esperaba éxito: {msg}"

        cur = in_memory_conn.cursor()
        cur.execute("SELECT cantidad FROM productos WHERE sku='1-2-16' AND ubicacion='BODEGA'")
        stock_bodega = cur.fetchone()[0]
        assert stock_bodega == 115, f"Esperado 115 en bodega, obtenido {stock_bodega}"

    def test_movimiento_registra_en_tabla_movimientos(self, in_memory_conn, monkeypatch):
        """Cualquier movimiento exitoso debe generar un registro en la tabla movimientos."""
        from data_layer.movements import registrar_movimiento_gui

        monkeypatch.setattr(
            'utils.db_connector.get_db_connection',
            lambda **kw: in_memory_conn
        )

        ok, _ = registrar_movimiento_gui(
            sku='1-2-16',
            tipo_movimiento='SALIDA_MOVIL',
            cantidad_afectada=5,
            movil_afectado='Movil 202',
            fecha_evento=date.today().isoformat(),
            sucursal_context='CHIRIQUI',
            existing_conn=in_memory_conn
        )

        assert ok
        cur = in_memory_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM movimientos WHERE sku_producto='1-2-16'")
        count = cur.fetchone()[0]
        assert count >= 1, f"Se esperaba al menos 1 registro en movimientos, se encontraron {count}"

    def test_sku_invalido_retorna_false(self, in_memory_conn, monkeypatch):
        """SKU vacío o None debe retornar False sin tocar la BD."""
        from data_layer.movements import registrar_movimiento_gui

        monkeypatch.setattr(
            'utils.db_connector.get_db_connection',
            lambda **kw: in_memory_conn
        )

        ok, msg = registrar_movimiento_gui(
            sku='',
            tipo_movimiento='SALIDA_MOVIL',
            cantidad_afectada=5,
            movil_afectado='Movil 200',
            fecha_evento=date.today().isoformat(),
            sucursal_context='CHIRIQUI',
            existing_conn=in_memory_conn
        )

        assert not ok


# ──────────────────────────────────────────────
# Tests de validators
# ──────────────────────────────────────────────

class TestValidators:

    def test_validate_sku_vacio_lanza_error(self):
        from utils.validators import validate_sku, ValidationError
        with pytest.raises(ValidationError):
            validate_sku('')

    def test_validate_sku_valido(self):
        from utils.validators import validate_sku
        assert validate_sku('1-2-16') == '1-2-16'

    def test_validate_quantity_negativa_lanza_error(self):
        from utils.validators import validate_quantity, ValidationError
        with pytest.raises(ValidationError):
            validate_quantity(-5, allow_negative=False)

    def test_validate_quantity_cero_con_flag(self):
        from utils.validators import validate_quantity
        # Si allow_zero=False, cantidad 0 debe lanzar error
        from utils.validators import ValidationError
        with pytest.raises(ValidationError):
            validate_quantity(0, allow_zero=False)
