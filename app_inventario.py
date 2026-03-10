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
from utils.logger import get_logger, log_startup

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
        
        # CONFIGURAR ICONO - NUEVO: Agregar ícono del programa
        self.configurar_icono()
        
        # Configurar estilos modernos
        self.setup_styles()
        
        # CORRECCIÓN: Mantener ventana principal en pantalla completa
        try: 
            master.state('zoomed')
        except tk.TclError: 
            master.wm_attributes('-fullscreen', True)

        # Crear interfaz moderna
        self.create_modern_gui()
        
        # Inicializar mejoras de UX
        self.theme_manager = create_theme_manager(self.master)
        self.keyboard_shortcuts = setup_keyboard_shortcuts(self.master, self)
        
        # Mostrar alerta de recordatorios al iniciar (en segundo plano)
        self.master.after(1000, lambda: threading.Thread(target=self.mostrar_alerta_inicial, daemon=True).start())

    def mostrar_alerta_inicial(self):
        """Muestra una alerta con los recordatorios pendientes para hoy al iniciar la aplicación"""
        fecha_hoy = date.today().isoformat()
        recordatorios = obtener_recordatorios_pendientes(fecha_hoy)
        
        if not recordatorios:
            return
        
        # Contar recordatorios por tipo
        retornos_pendientes = [r for r in recordatorios if r[3] == 'RETORNO']
        conciliaciones_pendientes = [r for r in recordatorios if r[3] == 'CONCILIACION']
        
        mensaje = "🔔 RECORDATORIOS PENDIENTES PARA HOY:\n\n"
        
        if retornos_pendientes:
            mensaje += f"🔄 RETORNOS PENDIENTES: {len(retornos_pendientes)}\n"
            for r in retornos_pendientes:
                mensaje += f"   • {r[1]} - Paquete {r[2]}\n"
            mensaje += "\n"
        
        if conciliaciones_pendientes:
            mensaje += f"⚖️ CONCILIACIONES PENDIENTES: {len(conciliaciones_pendientes)}\n"
            for r in conciliaciones_pendientes:
                mensaje += f"   • {r[1]} - Paquete {r[2]}\n"
        
        # Mostrar alerta solo si hay recordatorios pendientes
        if retornos_pendientes or conciliaciones_pendientes:
            self.mostrar_alerta_recordatorios_unica(mensaje)

    def mostrar_alerta_recordatorios_unica(self, mensaje):
        """Muestra una alerta única con los recordatorios pendientes (solo se muestra una vez)"""
        # Crear ventana de alerta
        ventana_alerta = tk.Toplevel(self.master)
        ventana_alerta.title("🔔 Recordatorios Pendientes - Hoy")
        ventana_alerta.geometry("500x400")
        ventana_alerta.configure(bg='#FFF3E0')
        ventana_alerta.resizable(False, False)
        
        # Centrar la ventana
        ventana_alerta.update_idletasks()
        x = (ventana_alerta.winfo_screenwidth() // 2) - (500 // 2)
        y = (ventana_alerta.winfo_screenheight() // 2) - (400 // 2)
        ventana_alerta.geometry(f"500x400+{x}+{y}")
        
        # Icono y título
        tk.Label(ventana_alerta, text="🔔", font=('Segoe UI', 48), 
                bg='#FFF3E0', fg=self.warning_color).pack(pady=(20, 10))
        
        tk.Label(ventana_alerta, text="RECORDATORIOS PENDIENTES PARA HOY", 
                font=('Segoe UI', 16, 'bold'), bg='#FFF3E0', fg=self.warning_color).pack()
        
        # Mensaje
        frame_mensaje = tk.Frame(ventana_alerta, bg='#FFF3E0', padx=20, pady=20)
        frame_mensaje.pack(fill='both', expand=True)
        
        tk.Label(frame_mensaje, text=mensaje, font=('Segoe UI', 11),
                bg='#FFF3E0', fg=self.dark_text, justify='left').pack(anchor='w')
        
        # Botones - CORREGIDO: Los botones ahora funcionan correctamente
        frame_botones = tk.Frame(ventana_alerta, bg='#FFF3E0')
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

    def setup_styles(self):
        """Configura estilos modernos para la aplicación"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Colores modernos
        self.primary_color = '#2c3e50'
        self.secondary_color = '#3498db'
        self.accent_color = '#e74c3c'
        self.success_color = '#27ae60'
        self.warning_color = '#f39c12'
        self.info_color = '#17a2b8'
        self.light_bg = '#ecf0f1'
        self.dark_text = '#2c3e50'
        self.light_text = '#ecf0f1'
        
        # Configurar estilos
        style.configure('Modern.TFrame', background=self.light_bg)
        style.configure('Header.TFrame', background=self.primary_color)
        style.configure('Card.TFrame', background='white', relief='raised', borderwidth=0)
        
        style.configure('Title.TLabel', 
                       background=self.primary_color, 
                       foreground='white',
                       font=('Segoe UI', 18, 'bold'))
        
        style.configure('Subtitle.TLabel',
                       background=self.light_bg,
                       foreground=self.dark_text,
                       font=('Segoe UI', 12, 'bold'))
        
        style.configure('Modern.TButton',
                       background=self.secondary_color,
                       foreground='white',
                       font=('Segoe UI', 10, 'bold'),
                       borderwidth=0,
                       focuscolor='none',
                       padding=(15, 8))
        
        style.map('Modern.TButton',
                 background=[('active', '#2980b9'), ('pressed', '#21618c')])
        
        style.configure('Success.TButton',
                       background=self.success_color,
                       foreground='white',
                       font=('Segoe UI', 10, 'bold'))
        
        style.map('Success.TButton',
                 background=[('active', '#219a52'), ('pressed', '#1e7e48')])
        
        style.configure('Warning.TButton',
                       background=self.warning_color,
                       foreground='white',
                       font=('Segoe UI', 10, 'bold'))
        
        style.configure('Danger.TButton',
                       background=self.accent_color,
                       foreground='white',
                       font=('Segoe UI', 10, 'bold'))
        
        style.configure('Info.TButton',
                       background=self.info_color,
                       foreground='white',
                       font=('Segoe UI', 10, 'bold'))
        
        style.configure('Modern.TEntry',
                       fieldbackground='white',
                       borderwidth=1,
                       relief='flat',
                       padding=(8, 6))
        
        style.configure('Modern.TCombobox',
                       fieldbackground='white',
                       background=self.secondary_color,
                       arrowcolor='white')
        
        style.configure('Modern.Treeview',
                       background='white',
                       fieldbackground='white',
                       foreground=self.dark_text,
                       rowheight=25)
        
        style.configure('Modern.Treeview.Heading',
                       background=self.primary_color,
                       foreground='white',
                       font=('Segoe UI', 10, 'bold'))
        
        style.map('Modern.Treeview',
                 background=[('selected', self.secondary_color)])

    def create_modern_gui(self):
        """Crea la interfaz gráfica moderna"""
        # Header principal
        header_frame = ttk.Frame(self.master, style='Header.TFrame', height=100)
        header_frame.pack(fill='x', padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Frame Principal
        main_frame = tk.Frame(self.master, bg='#f8f9fa')
        main_frame.pack(fill='both', expand=True)

        # Configurar Grid
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Sidebar Navigation
        self.sidebar = tk.Frame(main_frame, bg='#2c3e50', width=220)
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
            "Material Dañado": {
                "loaded": False,
                "module": "gui.santiago_danados",
                "class": "SantiagoDanadosTab",
                "icon": "⚠️",
                "btn_text": "Dañados"
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
            "btn_text": "Historial" if is_santiago_direct else "Historial de Instalaciones"
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

        # BIND EVENTO DE CAMBIO DE PESTAÑA
        self.main_notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        # CARGAR DASHBOARD INMEDIATAMENTE (Para que no esté vacío al inicio)
        self.load_tab("Dashboard")

    def create_sidebar_header(self):
        header = tk.Frame(self.sidebar, bg='#2c3e50', pady=20)
        header.pack(fill='x')
        
        tk.Label(header, text="STOCKWARE", font=('Segoe UI', 16, 'bold'), 
                bg='#2c3e50', fg='white').pack()
        tk.Label(header, text="Enterprise Edition", font=('Segoe UI', 8), 
                bg='#2c3e50', fg='#bdc3c7').pack()

    def create_nav_button(self, text, icon, tab_name):
        btn = tk.Button(self.sidebar, text=f"  {icon}  {text}", anchor='w',
                       font=('Segoe UI', 11), bg='#2c3e50', fg='#ecf0f1',
                       activebackground='#34495e', activeforeground='white',
                       relief='flat', bd=0, padx=20, pady=12,
                       command=lambda: self.switch_to_tab(tab_name))
        btn.pack(fill='x', pady=2)
        return btn

    def switch_to_tab(self, tab_name):
        # Encontrar índice
        for i, name in enumerate(self.tabs_data.keys()):
            if name == tab_name:
                self.main_notebook.select(i)
                break
                
    def on_tab_changed(self, event):
        # Identificar pestaña actual
        try:
            current_tab_index = self.main_notebook.index(self.main_notebook.select())
            tab_name = self.main_notebook.tab(current_tab_index, "text")
            
            # Actualizar estilo botones
            for name, btn in self.nav_buttons.items():
                if name == tab_name:
                    btn.configure(bg='#34495e', fg='#3498db', font=('Segoe UI', 11, 'bold'))
                else:
                    btn.configure(bg='#2c3e50', fg='#ecf0f1', font=('Segoe UI', 11))
                    
            # Cargar módulo si no está cargado
            self.load_tab(tab_name)
        except Exception:
            pass

    def load_tab(self, tab_name):
        data = self.tabs_data.get(tab_name)
        if not data: return
        
        if data['loaded']:
            return # Ya cargado
            
        # =================================================================
        # ADAPTER: Inyectar método .add() al frame contenedor
        # =================================================================
        # Esto permite que los tabs (Dashboard, etc.) usen este frame como si fuera 
        # un Notebook (llamando a .add) y como master (para crear widgets hijos).
        if not hasattr(data['frame'], 'add'):
            def _fake_add(self, child, **kwargs):
                child.pack(fill='both', expand=True)
            
            # Monkey-patch del método add en la instancia del frame
            import types
            data['frame'].add = types.MethodType(_fake_add, data['frame'])

        # Mostrar indicador de carga (opcional, si es muy lento)
        logger.info(f"Lazy loading tab: {tab_name}...")
        
        try:
            import importlib
            module = importlib.import_module(data['module'])
            cls = getattr(module, data['class'])
            
            # Limpiar cualquier cosa previa en el frame (no debería haber)
            for widget in data['frame'].winfo_children():
                widget.destroy()
                
            # Instanciar clase dentro del frame placeholder
            instance = None
            
            # TABS ESTÁNDAR
            # Pasamos data['frame'] que ahora tiene .add() y es un Widget válido
            instance = cls(data['frame'], self)
                
            # Si la instancia es un Widget (como Reportes o Recordatorios que heredan de Frame),
            # necesitamos empacarla dentro del placeholder.
            # Los controladores (Dashboard, Inventario) no son widgets, sus vistas se empacan vía Adapter.
            if isinstance(instance, tk.Widget):
                instance.pack(fill='both', expand=True)
            
            # Guardar referencia
            setattr(self, f"{data['class'].lower()}", instance) 
            
            # Mapeos específicos legado
            if tab_name == "Dashboard": self.dashboard_tab = instance
            elif tab_name == "Inventario": self.inventory_tab = instance
            elif tab_name == "Historial": self.audit_tab = instance
            elif tab_name == "Productos": self.products_tab = instance
            elif tab_name == "Configuración": self.settings_tab = instance
            elif tab_name == "Registro Global": self.history_tab = instance
            
            data['loaded'] = True
            logger.info(f"Tab {tab_name} loaded successfully.")
            
        except Exception as e:
            logger.error(f"Error loading tab {tab_name}: {e}")
            import traceback
            traceback.print_exc()
            tk.Label(data['frame'], text=f"Error cargando módulo:\n{e}", fg='red').pack()



    def perform_inventory_action(self, method_name):
        """Ejecuta una acción del tab de inventario, cargándolo si es necesario"""
        try:
            # Asegurar que Inventario esté cargado
            self.load_tab("Inventario")
            
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
        root.configure(bg='#2c3e50')
        
        # Centrar
        root.withdraw()
        root.update_idletasks()
        x = (root.winfo_screenwidth() - 400) // 2
        y = (root.winfo_screenheight() - 350) // 2
        root.geometry(f"+{x}+{y}")
        root.deiconify()

        # UI
        main_frame = tk.Frame(root, bg='#2c3e50', padx=20, pady=20)
        main_frame.pack(fill='both', expand=True)

        tk.Label(main_frame, text="STOCKWARE", font=('Segoe UI', 20, 'bold'), fg='#ecf0f1', bg='#2c3e50').pack(pady=(10, 5))
        tk.Label(main_frame, text="Seleccione su Ubicación", font=('Segoe UI', 12), fg='#bdc3c7', bg='#2c3e50').pack(pady=(0, 20))

        # Botón CHIRIQUÍ
        btn_chiriqui = tk.Button(main_frame, text="📍 CHIRIQUÍ\n(Bodega Principal)", 
                                command=lambda: self.seleccionar("CHIRIQUI"),
                                bg='#3498db', fg='white', font=('Segoe UI', 12, 'bold'),
                                relief='flat', pady=10, cursor='hand2')
        btn_chiriqui.pack(fill='x', pady=10)

        # Botón SANTIAGO
        btn_santiago = tk.Button(main_frame, text="📍 SANTIAGO\n(Sucursal)", 
                                command=lambda: self.seleccionar("SANTIAGO"),
                                bg='#e67e22', fg='white', font=('Segoe UI', 12, 'bold'),
                                relief='flat', pady=10, cursor='hand2')
        btn_santiago.pack(fill='x', pady=10)

        tk.Label(main_frame, text="v2.5.0 Enterprise", font=('Segoe UI', 8), fg='#7f8c8d', bg='#2c3e50').pack(side='bottom', pady=10)

    def seleccionar(self, sucursal):
        set_branch_context(sucursal)
        self.root.destroy()
        self.on_select_callback()

def main():
    """
    Punto de entrada principal.
    Fuerza CHIRIQUI por defecto, a menos que se defina la variable de entorno FORCE_BRANCH (como hace app_santiago.py).
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
    """Inicia el flujo normal Login -> App, una vez configurada la sucursal"""
    root = tk.Tk()
    root.withdraw() # Ocultar ventana principal hasta login
    
    # 1. VERIFICAR DB
    db_existe = os.path.exists(DATABASE_NAME) # Nota: Esto verifica la SQLite local base, para MySQL no importa tanto
    # Si estamos en modo Local-Santiago, quizá debamos checkear esa DB.
    # Pero `inicializar_bd` usará `get_db_connection` que ya conoce el contexto.
    
    try:
        inicializar_bd()
    except Exception as e:
        messagebox.showerror("Error de Inicio", f"No se pudo conectar a la Base de Datos:\\n{e}")
        root.destroy()
        return

    # Si es SQLite y no existía, poblar (Solo para la default por ahora)
    # Mejorar lógica si se requiere poblar Santiago independiente.
    
    # 3. EJECUTAR LIMPIEZA EN SEGUNDO PLANO
    def iniciar_tareas_segundo_plano():
        def run_optimization():
            try:
                # logger.info("Ejecutando tareas de optimización en segundo plano...")
                # verificar_y_corregir_duplicados_completo(silent=True)
                pass # Desactivado temporalmente para agilizar inicio
            except Exception as e:
                logger.error(f"Error en tareas de optimización: {e}")
        
        thread = threading.Thread(target=run_optimization, daemon=True)
        thread.start()
    
    def bootstrap_app():
        logger.info("Bootstrap Start")
        try:
            logger.info("[INIT] Iniciando aplicación principal")
            
            logger.info("Local Web Server is disabled. Using Render Portal.")
            
            # Inicializar App principal (SIN importar módulos GUI pesados aún)
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

    # Iniciar aplicación directamente (login removido)
    logger.info("Iniciando aplicación sin sistema de login")
    root.after(100, bootstrap_app)
 
    
    # MANEJADOR GLOBAL DE EXCEPCIONES GUI
    def report_callback_exception(exc, val, tb):
        import traceback
        err_msg = "".join(traceback.format_exception(exc, val, tb))
        logger.error(f"UNHANDLED GUI EXCEPTION:\n{err_msg}")
        messagebox.showerror("Error Inesperado", f"Se ha producido un error inesperado:\n\n{val}\n\nRevise el log para más detalles.")
        
    root.report_callback_exception = report_callback_exception

    root.after(1000, iniciar_tareas_segundo_plano)
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