# StockWare - Sistema de Gestión de Inventario

## Instalación y Uso

### Opción 1: Ejecutable (Recomendado para usuarios finales)

1. **Descargar** la carpeta `StockWare` completa
2. **Configurar** el archivo `.env` con tus credenciales de base de datos:
   ```
   DB_TYPE=MYSQL
   MYSQL_HOST=tu-servidor.com
   MYSQL_USER=tu-usuario
   MYSQL_PASSWORD=tu-contraseña
   MYSQL_DATABASE=nombre-bd
   MYSQL_PORT=3306
   ```
3. **Ejecutar** `StockWare.exe`

### Opción 2: Desde código fuente (Para desarrolladores)

1. **Instalar Python 3.8+**
2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configurar** archivo `.env` (ver arriba)
4. **Ejecutar:**
   ```bash
   python app_inventario.py
   ```

## Características

- ✅ Gestión de inventario en bodega y móviles
- ✅ Portal web para reportes de campo
- ✅ Auditoría de consumos
- ✅ Reportes y exportación a Excel
- ✅ Control de préstamos y recordatorios
- ✅ Cuadro contable y conciliación

## Requisitos

### Para el ejecutable:
- Windows 10 o superior
- Conexión a base de datos MySQL/TiDB

### Para desarrollo:
- Python 3.8+
- MySQL 5.7+ o TiDB Cloud
- Ver `requirements.txt` para dependencias

## Portal Web

El sistema incluye un portal web que se ejecuta automáticamente en:
- **Local:** http://localhost:5000
- **Red local:** http://[tu-ip]:5000

## Soporte

Para problemas o preguntas, contactar al administrador del sistema.

## Versión

1.0.0 - Sistema de Gestión de Inventario StockWare
