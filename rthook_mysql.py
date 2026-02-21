# Runtime hook para mysql-connector-python
# Fuerza la importación de locales antes de que la app los necesite
import mysql.connector.locales.eng.client_error  # noqa: F401
import mysql.connector.locales.eng  # noqa: F401
import mysql.connector.locales  # noqa: F401
