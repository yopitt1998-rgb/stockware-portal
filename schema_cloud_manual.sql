
USE test;

-- SCHEMA FOR STOCKWARE CLOUD (TiDB/MySQL)
-- Run this in your Cloud DB Console if the application cannot create tables automatically.

CREATE TABLE IF NOT EXISTS productos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    cantidad INTEGER NOT NULL DEFAULT 0,
    ubicacion VARCHAR(50) NOT NULL,
    minimo_stock INTEGER DEFAULT 10,
    categoria VARCHAR(100) DEFAULT 'General',
    marca VARCHAR(100) DEFAULT 'N/A',
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    secuencia_vista VARCHAR(20),
    codigo_barra VARCHAR(100),
    codigo_barra_maestro VARCHAR(100),
    UNIQUE (sku, ubicacion)
);

CREATE TABLE IF NOT EXISTS asignacion_moviles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku_producto VARCHAR(50) NOT NULL,
    movil VARCHAR(100) NOT NULL,
    paquete VARCHAR(50),
    cantidad INTEGER NOT NULL DEFAULT 0,
    UNIQUE (sku_producto, movil, paquete)
);

CREATE TABLE IF NOT EXISTS moviles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    patente VARCHAR(20),
    conductor VARCHAR(255),
    ayudante VARCHAR(255),
    activo INTEGER DEFAULT 1,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS movimientos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku_producto VARCHAR(50) NOT NULL,
    tipo_movimiento VARCHAR(50) NOT NULL,
    cantidad_afectada INTEGER NOT NULL,
    movil_afectado VARCHAR(100),
    fecha_movimiento DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_evento DATE,
    paquete_asignado VARCHAR(50),
    documento_referencia LONGTEXT,
    observaciones LONGTEXT
);

CREATE TABLE IF NOT EXISTS series_registradas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    serial_number VARCHAR(100) NOT NULL UNIQUE,
    fecha_ingreso DATETIME DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) DEFAULT 'DISPONIBLE',
    ubicacion VARCHAR(100) DEFAULT 'BODEGA'
);

CREATE TABLE IF NOT EXISTS consumos_pendientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    movil VARCHAR(100) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    cantidad INTEGER NOT NULL,
    tecnico_nombre VARCHAR(255),
    ayudante_nombre VARCHAR(255),
    ticket VARCHAR(255),
    colilla VARCHAR(255),
    num_contrato VARCHAR(255),
    fecha DATE,
    estado VARCHAR(20) DEFAULT 'PENDIENTE',
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    seriales_usados LONGTEXT
);

-- Indices optimization
CREATE INDEX idx_productos_sku ON productos(sku);
CREATE INDEX idx_asig_sku ON asignacion_moviles(sku_producto);
CREATE INDEX idx_asig_movil ON asignacion_moviles(movil);
