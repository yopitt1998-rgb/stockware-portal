import sqlite3
import mysql.connector
from mysql.connector import pooling
import os
import sys
import csv
import shutil
from datetime import datetime, date, timedelta

from utils.logger import get_logger
from utils.validators import validate_sku, validate_quantity, validate_date, validate_movil, validate_tipo_movimiento, validate_observaciones, ValidationError
from config import DATABASE_NAME, DB_TYPE, MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB, MYSQL_PORT, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, UBICACION_DESCARTE, TIPO_MOVIMIENTO_DESCARTE, TIPOS_CONSUMO, TIPOS_ABASTO, PAQUETES_MATERIALES, PRODUCTOS_INICIALES, MATERIALES_COMPARTIDOS
from utils.db_connector import get_db_connection, close_connection, db_session

from data_layer.core import *
from data_layer.inventory import *
from data_layer.movements import *
from data_layer.mobile import *
from data_layer.reminders import *
