import sqlite3
import sys
import os
from datetime import datetime, date, timedelta

# SOPORTE PARA DPI ALTO (Windows)
if os.name == 'nt':
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# Sistema de Logging Centralizado
from utils.logger import get_logger

logger = get_logger(__name__)
logger.info("Inicializando app_inventario...")


import tkinter as tk
from tkinter import ttk
from tkinter import messagebox 
from tkinter import filedialog

import threading


# =================================================================
# 1. CONFIGURACIÓN DE CONEXIÓN Y DATOS INICIALES
# =================================================================

from config import *
from config import set_branch_context # Explicit import

from database import *

# GUI Modules
from gui.utils import darken_color
from gui.keyboard_shortcuts import setup_keyboard_shortcuts
from gui.theme_manager import create_theme_manager
from gui.styles import Styles
from gui.tab_manager import TabManager
from gui.services.notification_service import NotificationService
from gui.services.cache_service import CacheService
from gui.components.log_viewer import LogViewerWindow
from functools import wraps




# Global placeholders for lazy loaded modules
DashboardTab = None
InventoryTab = None
SettingsTab = None
AuditTab = None
ProductsTab = None

# =================================================================
# 3. FUNCIONES DE EXPORTACIÓN
# =================================================================

# exportar_a_csv importado desde database




# =================================================================
# 5. LÓGICA DE LA INTERFAZ GRÁFICA (GUI) - MODERNA
# =================================================================

class ModernInventarioApp:
    def __init__(self, master):
        self.master = master
        
        # Obtener contexto actual
        from config import CURRENT_CONTEXT
        branch_name = CURRENT_CONTEXT.get('BRANCH', 'Desconocido')
        
        branch_display = f" | 📍 SUCURSAL: {branch_name}" 
        self.master.title(f"🚀 StockWare - Gestión de Inventario{branch_display}")
        self.master.configure(bg='#f8f9fa')
        
        # Initialize Services
        self.cache_service = CacheService()
        
        # CONFIGURAR ICONO - NUEVO: Agregar ícono del programa
        self.configurar_icono()
        
        # Configurar estilos modernos
        Styles.setup_styles()
        
        # Color attributes for easier access (compatibility)
        self.primary_color = Styles.PRIMARY_COLOR
        self.secondary_color = Styles.SECONDARY_COLOR
        self.accent_color = Styles.ACCENT_COLOR
        self.success_color = Styles.SUCCESS_COLOR
        self.warning_color = Styles.WARNING_COLOR
        self.info_color = Styles.INFO_COLOR
        self.light_bg = Styles.LIGHT_BG
        self.dark_text = Styles.DARK_TEXT
        self.light_text = Styles.LIGHT_TEXT
        self.text_color = Styles.TEXT_COLOR
        
        # CORRECCIÓN: Mantener ventana principal en pantalla completa
        try: 
            master.state('zoomed')
        except tk.TclError: 
            master.wm_attributes('-fullscreen', True)

        # Crear interfaz moderna
        self.create_modern_gui()
        
        # CARGAR DASHBOARD INMEDIATAMENTE (Para que no esté vacío al inicio)
        self.tab_manager.load_tab("Dashboard")
        
        # Sincronizar Cache al inicio
        self.refresh_app_cache()
        
        # Initialize keyboard shortcuts
        self.keyboard_shortcuts = setup_keyboard_shortcuts(self.master, self)
        
        # Mostrar alerta de recordatorios al iniciar (en segundo plano)
        self.master.after(1000, lambda: threading.Thread(target=self.mostrar_alerta_inicial, daemon=True).start())

    def mostrar_alerta_inicial(self):
        """Muestra una alerta con los recordatorios para hoy"""
        mensaje = NotificationService.get_todays_reminders_message()
        if mensaje:
            self.master.after(0, lambda: self.mostrar_alerta_recordatorios_unica(mensaje))

    def refresh_app_cache(self):
        """Refresca los datos en caché y actualiza la barra de estado"""
        self.set_status("🔄 Sincronizando datos...", is_busy=True)
        def on_done(success, error=None):
            if success:
                self.set_status("✅ Sincronización exitosa", timeout=3000)
            else:
                self.set_status(f"⚠️ Error de sincronización: {error}", timeout=5000)
        
        self.cache_service.refresh_cache(callback=on_done)

    def mostrar_alerta_recordatorios_unica(self, mensaje):
        """Muestra una alerta única con los recordatorios pendientes (solo se muestra una vez)"""
        # Crear ventana de alerta
        ventana_alerta = tk.Toplevel(self.master)
        ventana_alerta.title("🔔 Recordatorios Pendientes - Hoy")
        ventana_alerta.geometry("500x400")
        ventana_alerta.configure(bg=self.light_bg)
        ventana_alerta.resizable(False, False)
        
        # Centrar la ventana
        ventana_alerta.update_idletasks()
        x = (ventana_alerta.winfo_screenwidth() // 2) - (500 // 2)
        y = (ventana_alerta.winfo_screenheight() // 2) - (400 // 2)
        ventana_alerta.geometry(f"500x400+{x}+{y}")
        
        # Icono y título
        tk.Label(ventana_alerta, text="🔔", font=('Segoe UI', 48), 
                bg=self.light_bg, fg=self.warning_color).pack(pady=(20, 10))
        
        tk.Label(ventana_alerta, text="RECORDATORIOS PENDIENTES PARA HOY", 
                font=('Segoe UI', 16, 'bold'), bg=self.light_bg, fg=self.warning_color).pack()
        
        # Mensaje
        frame_mensaje = tk.Frame(ventana_alerta, bg=self.light_bg, padx=20, pady=20)
        frame_mensaje.pack(fill='both', expand=True)
        
        tk.Label(frame_mensaje, text=mensaje, font=('Segoe UI', 11),
                bg=self.light_bg, fg=self.dark_text, justify='left').pack(anchor='w')
        
        # Botones - CORREGIDO: Los botones ahora funcionan correctamente
        frame_botones = tk.Frame(ventana_alerta, bg=self.light_bg)
        frame_botones.pack(pady=(0, 20))
        
        # Botón "Ir a Recordatorios" - CORREGIDO
        btn_recordatorios = tk.Button(frame_botones, text="Ir a Recordatorios", 
                 command=lambda: self.ir_a_pestaña_recordatorios(ventana_alerta),
                 bg=self.warning_color, fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=20, pady=8, cursor='hand2')
        btn_recordatorios.pack(side='left', padx=10)
        
        # Botón "Cerrar" - CORREGIDO
        btn_cerrar = tk.Button(frame_botones, text="Cerrar", 
                 command=ventana_alerta.destroy,
                 bg=self.secondary_color, fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=20, pady=8, cursor='hand2')
        btn_cerrar.pack(side='left', padx=10)
        
        # Hacer que la ventana sea modal (obligar al usuario a interactuar)
        ventana_alerta.transient(self.master)
        ventana_alerta.grab_set()
        ventana_alerta.focus_set()

    def ir_a_pestaña_recordatorios(self, ventana_alerta=None):
        """Navega a la pestaña de Recordatorios"""
        # Buscar el notebook principal
        for widget in self.master.winfo_children():
            if isinstance(widget, ttk.Notebook):
                # Buscar la pestaña de Recordatorios
                for i, tab_id in enumerate(widget.tabs()):
                    tab_text = widget.tab(tab_id, "text")
                    if "🔔" in tab_text or "Recordatorios" in tab_text:
                        # Seleccionar la pestaña de Recordatorios
                        widget.select(i)
                        break
                break
        
        # Cerrar la ventana de alerta si está abierta
        if ventana_alerta:
            ventana_alerta.destroy()

    def configurar_icono(self):
        """Configura el ícono del programa - NUEVO"""
        try:
            # Buscar el archivo de ícono en diferentes ubicaciones y formatos
            icon_paths = [
                "logo-StockWare.ico",
                "logo-StockWare.png",
                os.path.join(application_path, "logo-StockWare.ico"),
                os.path.join(application_path, "logo-StockWare.png"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo-StockWare.ico"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo-StockWare.png")
            ]
            
            # Si estamos en modo congelado (ejecutable), agregar ruta interna _MEIPASS
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                icon_paths.insert(0, os.path.join(sys._MEIPASS, "logo-StockWare.ico"))
                icon_paths.insert(0, os.path.join(sys._MEIPASS, "logo-StockWare.png"))
            
            icon_path = None
            for path in icon_paths:
                if os.path.exists(path):
                    icon_path = path
                    break
            
            if icon_path:
                if icon_path.endswith('.ico'):
                    self.master.iconbitmap(icon_path)
                elif icon_path.endswith('.png'):
                    # Para PNG, necesitamos convertirlo (en sistemas Windows)
                    try:
                        icon = tk.PhotoImage(file=icon_path)
                        self.master.iconphoto(True, icon)
                    except:
                        logger.warning("No se pudo cargar el ícono PNG, usando ícono por defecto")
                logger.info(f"Ícono cargado: {icon_path}")
            else:
                logger.warning("No se encontró el archivo logo-StockWare.ico o logo-StockWare.png")
        except Exception as e:
            logger.error(f"Error al cargar el ícono: {e}")


    def create_modern_gui(self):
        """Crea la interfaz gráfica moderna"""
        # Header principal
        header_frame = ttk.Frame(self.master, style='Header.TFrame', height=100)
        header_frame.pack(fill='x', padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Frame Principal
        main_frame = tk.Frame(self.master, bg=self.light_bg)
        main_frame.pack(fill='both', expand=True)

        # Configurar Grid
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Sidebar Navigation
        self.sidebar = tk.Frame(main_frame, bg=self.primary_color, width=220)
        self.sidebar.grid(row=0, column=0, sticky='ns')
        self.sidebar.pack_propagate(False)

        # Header Sidebar
        self.create_sidebar_header()

        # Botones de Navegación
        self.nav_buttons = {}
        
        # NOTEBOOK PRINCIPAL
        self.main_notebook = ttk.Notebook(main_frame)
        self.main_notebook.grid(row=0, column=1, sticky='nsew', padx=(10, 20), pady=10)
        
        # DETECTAR SI ESTAMOS EN MODO SANTIAGO DIRECTO
        is_santiago_direct = os.environ.get('SANTIAGO_DIRECT_MODE') == '1'
        
        # DICCIONARIO DE PESTAÑAS (Nombre -> {frame, loaded, module_path, class_name})
        self.tabs_data = {
            "Dashboard": {
                "loaded": False, 
                "module": "gui.dashboard", 
                "class": "DashboardTab",
                "icon": "📊",
                "btn_text": "Dashboard"
            },
            "Bajas y Consumos": {
                "loaded": False,
                "module": "gui.santiago_danados",
                "class": "SantiagoDanadosTab",
                "icon": "📑",
                "btn_text": "Bajas"
            },
            "Auditoría Bodega": {
                "loaded": False,
                "module": "gui.warehouse_audit",
                "class": "WarehouseAuditTab",
                "icon": "🏢",
                "btn_text": "Auditoría Bodega"
            }
        }

        # REGLA DE NEGOCIO: Santiago usa un subconjunto de pestañas.
        # Quitamos "Consumo" porque el usuario ahora prefiere que los técnicos usen la web.
        if is_santiago_direct:
            # Pestañas activas para Santiago
            self.tabs_data["Auditoría Física"] = {
                "loaded": False,
                "module": "gui.santiago_audit_phys",
                "class": "SantiagoAuditPhysTab",
                "icon": "🔫",
                "btn_text": "Auditoría"
            }
            # Mantenemos "Inventario" en el diccionario pero NO lo agregaremos al notebook ni al sidebar
            # Esto permite que perform_inventory_action (Abasto) funcione cargándolo en 'background'
            self.tabs_data["Inventario"] = {
                "loaded": False,
                "module": "gui.inventory",
                "class": "InventoryTab",
                "icon": "📦",
                "btn_text": "Inventario",
                "hidden": True
            }
        else:
            self.tabs_data["Inventario"] = {
                "loaded": False,
                "module": "gui.inventory",
                "class": "InventoryTab",
                "icon": "📦",
                "btn_text": "Inventario"
            }

        self.tabs_data["Productos"] = {
            "loaded": False,
            "module": "gui.products",
            "class": "ProductsTab",
            "icon": "🏷️",
            "btn_text": "Productos"
        }
        
        self.tabs_data["Historial"] = {
            "loaded": False,
            "module": "gui.audit",
            "class": "AuditTab",
            "icon": "📋",
            "btn_text": "Historial"
        }

        self.tabs_data["Registro Global"] = {
            "loaded": False,
            "module": "gui.inventory.history_log",
            "class": "HistoryLogTab",
            "icon": "📜",
            "btn_text": "Registro"
        }

        # Configuración solo para David
        if not is_santiago_direct:
            self.tabs_data["Configuración"] = {
                "loaded": False,
                "module": "gui.settings",
                "class": "SettingsTab",
                "icon": "⚙️",
                "btn_text": "Configuración"
            }
        
        # CREAR PLACEHOLDERS (Omitir los marcados como 'hidden')
        for name, data in self.tabs_data.items():
            frame = ttk.Frame(self.main_notebook)
            
            # Solo agregar al notebook y sidebar si NO es oculto
            if not data.get('hidden'):
                self.main_notebook.add(frame, text=name)
                btn = self.create_nav_button(data['btn_text'], data['icon'], name)
                self.nav_buttons[name] = btn
            
            data['frame'] = frame # Referencia al frame (aunque no esté en el notebook)

        # BARRA DE ESTADO (NUEVO)
        self.status_bar_frame = tk.Frame(main_frame, bg='#e2e8f0', height=25)
        self.status_bar_frame.grid(row=1, column=0, columnspan=2, sticky='ew')
        
        self.status_label = tk.Label(self.status_bar_frame, text="Listo", 
                                    bg='#e2e8f0', fg='#475569', font=('Segoe UI', 8),
                                    padx=10)
        self.status_label.pack(side='left')
        
        self.sync_info_label = tk.Label(self.status_bar_frame, text="", 
                                       bg='#e2e8f0', fg='#64748b', font=('Segoe UI', 8, 'italic'),
                                       padx=10)
        self.sync_info_label.pack(side='right')
        
        # Botón de logs al final del sidebar (NUEVO)
        btn_logs = tk.Button(self.sidebar, text="  🔍  Logs del Sistema", anchor='w',
                            font=('Segoe UI', 9), bg=self.primary_color, fg='#94a3b8',
                            activebackground='#334155', activeforeground='white',
                            relief='flat', bd=0, padx=20, pady=8,
                            command=self.show_log_viewer)
        btn_logs.pack(side='bottom', fill='x', pady=10)

        # INICIALIZAR EL GESTOR DE PESTAÑAS (DEBE IR AL FINAL DE create_modern_gui)
        self.tab_manager = TabManager(self)

    def show_log_viewer(self):
        """Abre la ventana del visor de logs."""
        LogViewerWindow(self.master)

    def set_status(self, text, is_busy=False, timeout=None):
        """Actualiza el mensaje de la barra de estado."""
        self.status_label.config(text=text)
        if is_busy:
            self.master.config(cursor="wait")
        else:
            self.master.config(cursor="")
            
        if timeout:
            self.master.after(timeout, lambda: self.status_label.config(text="Listo"))

    @staticmethod
    def wait_cursor(func):
        """Decorador para mostrar el cursor de espera durante una operación."""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            self.master.config(cursor="wait")
            self.master.update_idletasks()
            try:
                return func(self, *args, **kwargs)
            finally:
                self.master.config(cursor="")
        return wrapper


    def create_sidebar_header(self):
        header = tk.Frame(self.sidebar, bg=self.primary_color, pady=20)
        header.pack(fill='x')
        
        tk.Label(header, text="STOCKWARE", font=('Segoe UI', 16, 'bold'), 
                bg=self.primary_color, fg='white').pack()
        tk.Label(header, text="Enterprise Edition", font=('Segoe UI', 8), 
                bg=self.primary_color, fg='#bdc3c7').pack()

    def create_nav_button(self, text, icon, tab_name):
        btn = tk.Button(self.sidebar, text=f"  {icon}  {text}", anchor='w',
                       font=('Segoe UI', 11), bg=self.primary_color, fg='#ecf0f1',
                       activebackground='#34495e', activeforeground='white',
                       relief='flat', bd=0, padx=20, pady=12,
                       command=lambda: self.tab_manager.switch_to_tab(tab_name))
        btn.pack(fill='x', pady=2)
        return btn




    def perform_inventory_action(self, method_name):
        """Ejecuta una acción del tab de inventario, cargándolo si es necesario"""
        try:
            # Asegurar que Inventario esté cargado
            self.tab_manager.load_tab("Inventario")
            
            # Obtener referencia
            if not hasattr(self, 'inventory_tab'):
                 messagebox.showerror("Error", "No se pudo cargar el módulo de Inventario.")
                 return
                 
            # Ejecutar método
            if hasattr(self.inventory_tab, method_name):
                method = getattr(self.inventory_tab, method_name)
                method()
            else:
                messagebox.showerror("Error", f"Método {method_name} no encontrado en Inventario.")
        except Exception as e:
            logger.error(f"Error executing inventory action {method_name}: {e}")
            messagebox.showerror("Error", f"Error ejecutando acción: {e}")






# =================================================================
# 6. INICIALIZACIÓN DE LA APLICACIÓN
# =================================================================

# =================================================================
# 0. SELECTOR DE SUCURSAL
# =================================================================
class BranchSelectorWindow:
    def __init__(self, root, on_select_callback):
        self.root = root
        self.on_select_callback = on_select_callback
        
        root.title("Seleccionar Sucursal")
        root.geometry("400x350")
        root.configure(bg=Styles.PRIMARY_COLOR)
        
        # Centrar
        root.withdraw()
        root.update_idletasks()
        x = (root.winfo_screenwidth() - 400) // 2
        y = (root.winfo_screenheight() - 350) // 2
        root.geometry(f"+{x}+{y}")
        root.deiconify()
 
        # UI
        main_frame = tk.Frame(root, bg=Styles.PRIMARY_COLOR, padx=20, pady=20)
        main_frame.pack(fill='both', expand=True)
 
        tk.Label(main_frame, text="STOCKWARE", font=('Segoe UI', 20, 'bold'), fg='#ecf0f1', bg=Styles.PRIMARY_COLOR).pack(pady=(10, 5))
        tk.Label(main_frame, text="Seleccione su Ubicación", font=('Segoe UI', 12), fg='#bdc3c7', bg=Styles.PRIMARY_COLOR).pack(pady=(0, 20))

        # Botón CHIRIQUÍ
        btn_chiriqui = tk.Button(main_frame, text="📍 CHIRIQUÍ\n(Bodega Principal)", 
                                command=lambda: self.seleccionar("CHIRIQUI"),
                                bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 12, 'bold'),
                                relief='flat', pady=10, cursor='hand2')
        btn_chiriqui.pack(fill='x', pady=10)

        # Botón SANTIAGO
        btn_santiago = tk.Button(main_frame, text="📍 SANTIAGO\n(Sucursal)", 
                                command=lambda: self.seleccionar("SANTIAGO"),
                                bg='#e67e22', fg='white', font=('Segoe UI', 12, 'bold'),
                                relief='flat', pady=10, cursor='hand2')
        btn_santiago.pack(fill='x', pady=10)

        tk.Label(main_frame, text="v2.5.0 Enterprise", font=('Segoe UI', 8), fg='#7f8c8d', bg=Styles.PRIMARY_COLOR).pack(side='bottom', pady=10)

    def seleccionar(self, sucursal):
        set_branch_context(sucursal)
        self.root.destroy()
        self.on_select_callback()

def main():
    """
    Punto de entrada principal.
    Fuerza CHIRIQUI por defecto, a menos que se defina la variable de entorno FORCE_BRANCH.
    """
    from config import set_branch_context
    
    # Prioridad 1: Variable de entorno (Para ejecutables separados, ej: app_santiago.py)
    forced_branch = os.environ.get('FORCE_BRANCH')
    
    if forced_branch:
        logger.info(f"Fuerza de sucursal detectada: {forced_branch}")
        set_branch_context(forced_branch)
    else:
        # Prioridad Default: Siempre CHIRIQUI para la app principal
        logger.info("Iniciando app principal. Forzando contexto predeterminado a: CHIRIQUI")
        set_branch_context('CHIRIQUI')
    
    # Iniciar aplicación directamente
    iniciar_aplicacion_principal()

def iniciar_aplicacion_principal():
    """Inicia el flujo normal -> App. La conexión DB se realiza en segundo plano."""
    root = tk.Tk()
    root.withdraw()

    # --- PANTALLA DE CARGA (Splash) ---
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)  # Sin bordes
    splash.configure(bg='#2c3e50')
    sw, sh = 360, 200
    x = (splash.winfo_screenwidth() - sw) // 2
    y = (splash.winfo_screenheight() - sh) // 2
    splash.geometry(f"{sw}x{sh}+{x}+{y}")

    tk.Label(splash, text="🚀 StockWare", font=('Segoe UI', 22, 'bold'),
             bg='#2c3e50', fg='white').pack(pady=(30, 5))
    tk.Label(splash, text="Conectando a la base de datos...", font=('Segoe UI', 10),
             bg='#2c3e50', fg='#95a5a6').pack()
    splash_status = tk.Label(splash, text="⏳ Iniciando...", font=('Segoe UI', 9),
                             bg='#2c3e50', fg='#3498db')
    splash_status.pack(pady=5)
    tk.Label(splash, text="v2.5.0 Enterprise", font=('Segoe UI', 8),
             bg='#2c3e50', fg='#566573').pack(side='bottom', pady=10)
    splash.lift()
    splash.update()

    def iniciar_tareas_segundo_plano():
        def run_optimization():
            try:
                pass  # Desactivado temporalmente para agilizar inicio
            except Exception as e:
                logger.error(f"Error en tareas de optimización: {e}")
        thread = threading.Thread(target=run_optimization, daemon=True)
        thread.start()

    def bootstrap_app():
        logger.info("Bootstrap Start")
        try:
            logger.info("[INIT] Iniciando aplicación principal")
            logger.debug("Instantiating ModernInventarioApp...")
            app = ModernInventarioApp(root)
            logger.debug("App Instantiated. Deiconifying root.")
        except Exception as e:
            msg = f"FATAL BOOTSTRAP ERROR: {e}"
            logger.critical(msg)
            import traceback
            logger.critical(traceback.format_exc())
            messagebox.showerror("Fatal Error", msg)
            root.destroy()
            return

        root.deiconify()

        def on_closing():
            if messagebox.askokcancel("Salir", "¿Está seguro que desea salir de la aplicación?"):
                root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)

    def _init_db_en_background():
        """Ejecuta la inicialización de DB en hilo secundario y luego lanza la app."""
        db_ok = False
        error_msg = None
        try:
            root.after(0, lambda: splash_status.config(text="🔌 Conectando a MySQL..."))
            inicializar_bd()
            db_ok = True
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error en inicializar_bd: {e}")

        def _continuar():
            try:
                splash.destroy()
            except Exception:
                pass

            if not db_ok:
                messagebox.showerror(
                    "Error de Conexión",
                    f"No se pudo conectar a la Base de Datos:\n\n{error_msg}\n\n"
                    "Verifique su conexión a Internet y vuelva a intentarlo."
                )
                root.destroy()
                return

            # DB lista — lanzar app
            bootstrap_app()

        root.after(0, _continuar)

    hilo_db = threading.Thread(target=_init_db_en_background, daemon=True)
    hilo_db.start()

    # MANEJADOR GLOBAL DE EXCEPCIONES GUI
    def report_callback_exception(exc, val, tb):
        import traceback
        err_msg = "".join(traceback.format_exception(exc, val, tb))
        logger.error(f"UNHANDLED GUI EXCEPTION:\n{err_msg}")
        messagebox.showerror("Error Inesperado", f"Se ha producido un error inesperado:\n\n{val}\n\nRevise el log para más detalles.")

    root.report_callback_exception = report_callback_exception

    root.after(2000, iniciar_tareas_segundo_plano)
    root.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        with open("crash_log.txt", "w") as f:
            f.write(traceback.format_exc())
            
        # Intentar loguear si es posible
        try:
            from utils.logger import get_logger
            logger = get_logger("CRASH")
            logger.critical(f"APP CRASHED: {e}")
            logger.critical(traceback.format_exc())
        except:
            print("CRASHED:", e)
            
        # Si hay GUI, mostrar error
        try:
            import tkinter.messagebox
            tkinter.messagebox.showerror("Fatal Error", f"La aplicación se cerró inesperadamente:\n{e}")
        except:
            pass
            
        # input("Press Enter to exit...") # Desactivado para producción