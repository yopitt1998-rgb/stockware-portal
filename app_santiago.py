import sys
import os
import threading
import tkinter as tk
from tkinter import messagebox

# Asegurar que el directorio actual esté en el path para importaciones
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 1. Configurar contexto Santiago antes de importar el resto
from config import set_branch_context, save_branch_preference
set_branch_context('SANTIAGO')
save_branch_preference('SANTIAGO')

# 2. Importar lógica principal de app_inventario
from app_inventario import ModernInventarioApp, inicializar_bd, logger

def bootstrap_santiago():
    """Inicia la aplicación directamente en modo Santiago"""
    root = tk.Tk()
    root.withdraw()
    
    # Personalización visual para Santiago (opcional pero recomendado para distinguir)
    logger.info("--- INICIANDO MODO SANTIAGO (CONSUMO DIRECTO) ---")
    
    try:
        inicializar_bd()
    except Exception as e:
        messagebox.showerror("Error Santiago", f"No se pudo conectar a la Base de Datos:\n{e}")
        root.destroy()
        return

    def start_gui():
        try:
            # Establecer flag de entorno por si los módulos GUI necesitan comportamiento especial
            os.environ['SANTIAGO_DIRECT_MODE'] = '1'
            
            app = ModernInventarioApp(root)
            
            # Cambiar título explícitamente para mayor claridad
            root.title(f"🚀 StockWare [SANTIAGO] - Consumo Directo")
            
            root.deiconify()
        except Exception as e:
            logger.critical(f"FATAL SANTIAGO ERROR: {e}")
            import traceback
            logger.critical(traceback.format_exc())
            messagebox.showerror("Error Santiago", str(e))
            root.destroy()

    root.after(100, start_gui)
    root.mainloop()

if __name__ == "__main__":
    bootstrap_santiago()
