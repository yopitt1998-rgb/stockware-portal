import sqlite3
import sys
import tkinter as tk
from tkinter import ttk 
from tkinter import messagebox 
from tkinter import filedialog 
from datetime import datetime, date, timedelta
import os 
import csv 
from collections import defaultdict
from dateutil import parser as dateparser
import threading


# =================================================================
# 1. CONFIGURACIÓN DE CONEXIÓN Y DATOS INICIALES
# =================================================================

from config import *
from database import *

# GUI Modules
from gui.utils import darken_color
from gui.login import LoginWindow




# =================================================================
# 3. FUNCIONES DE EXPORTACIÓN
# =================================================================

# exportar_a_csv importado desde database




# =================================================================
# 5. LÓGICA DE LA INTERFAZ GRÁFICA (GUI) - MODERNA
# =================================================================

class ModernInventarioApp:
    def __init__(self, master, usuario=None):
        self.master = master
        self.usuario_actual = usuario
        self.master.title(f"🚀 StockWare - Gestión de Inventario ({usuario.get('usuario') if usuario else ''})")
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
                        print("No se pudo cargar el ícono PNG, usando ícono por defecto")
                print(f"Ícono cargado: {icon_path}")
            else:
                print("No se encontró el archivo logo-StockWare.ico o logo-StockWare.png")
        except Exception as e:
            print(f"Error al cargar el ícono: {e}")

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
        
        title_label = ttk.Label(header_frame, 
                               text="🚀 SISTEMA DE GESTIÓN DE INVENTARIO", 
                               style='Title.TLabel')
        title_label.pack(side='left', padx=30, pady=30)
        
        # Frame para información de usuario
        user_frame = ttk.Frame(header_frame, style='Header.TFrame')
        user_frame.pack(side='right', padx=30, pady=30)
        
        user_label = ttk.Label(user_frame, 
                               text="👤 Administrador", 
                               style='Title.TLabel',
                               font=('Segoe UI', 12))
        user_label.pack(side='right')

        # Panel principal con pestañas
        self.main_notebook = ttk.Notebook(self.master, style='Modern.TFrame')
        self.main_notebook.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Pestaña 1: Dashboard Principal
        self.dashboard_tab = DashboardTab(self.main_notebook, self)
        
        # Pestaña 2: Gestión de Inventario
        self.inventory_tab = InventoryTab(self.main_notebook, self)
        
        # Pestaña 3: Movimientos (Mantiene estructura legacy por ahora o usa funciones de inventario)
        self.create_movements_tab(self.main_notebook)
        
        # Pestaña 4: Reportes
        self.reports_tab = ReportsTab(self.main_notebook, open_history_callback=self.inventory_tab.abrir_ventana_historial)
        self.main_notebook.add(self.reports_tab, text="📊 Reportes")
        
        # Pestaña 5: Recordatorios
        self.reminders_tab = RemindersTab(self.main_notebook, inventory_tab=self.inventory_tab)
        self.main_notebook.add(self.reminders_tab, text="🔔 Recordatorios")
        
        # Pestaña 6: Cuadre Contable
        cuadre_frame = ttk.Frame(self.main_notebook, style='Modern.TFrame')
        self.main_notebook.add(cuadre_frame, text="💰 Cuadre Contable")
        self.accounting_tab = CuadreContableMasivo(cuadre_frame)

        # Pestaña 7: Auditoría de Terreno (NUEVO - PUNTO 5)
        self.audit_tab = AuditTab(self.main_notebook, self)
        self.main_notebook.add(self.audit_tab, text="🔍 Auditoría Terreno")
        
        # Pestaña 8: Configuración
        if self.usuario_actual and self.usuario_actual.get('rol') == 'ADMIN':
            self.settings_tab = SettingsTab(self.main_notebook, self)
            self.main_notebook.add(self.settings_tab, text="⚙️ Configuración")


    # create_dashboard_tab moved to gui/dashboard.py

    # create_metric_card moved to gui/dashboard.py

    # create_inventory_tab moved to gui/inventory.py

    def create_movements_tab(self, notebook):
        """Crear pestaña de Movimientos"""
        movements_frame = ttk.Frame(notebook, style='Modern.TFrame')
        notebook.add(movements_frame, text="🔄 Movimientos")
        
        # Implement Scrollable Canvas
        canvas = tk.Canvas(movements_frame, bg=self.light_bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(movements_frame, orient="vertical", command=canvas.yview)
        
        movements_frame_inner = ttk.Frame(canvas, style='Modern.TFrame')
        
        # Configure scrolling
        movements_frame_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=movements_frame_inner, anchor="nw", width=canvas.winfo_reqwidth())
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack layouts
        canvas.pack(side="left", fill="both", expand=True, padx=20, pady=20)
        scrollbar.pack(side="right", fill="y")
        
        # Ensure inner frame resizes with canvas
        def on_canvas_configure(event):
            canvas.itemconfig(canvas.find_withtag("all")[0], width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)

        
        movement_buttons = [
            ("🚚 Abasto Completo", "Registro de entrada de material a bodega", self.inventory_tab.abrir_ventana_abasto, self.success_color),
            ("📂 Gestión de Abastos", "Historial, detalle y edición de abastos", self.inventory_tab.abrir_ventana_gestion_abastos, self.info_color),
            ("🏁 Inventario Inicial", "Carga de stock inicial (solo inicio)", self.inventory_tab.abrir_ventana_inicial, "#3f51b5"),
            ("📤 Salida a Móvil", "Asignación de material a vehículos", self.inventory_tab.abrir_ventana_salida_movil, self.secondary_color),
            ("🔄 Retorno de Móvil", "Devolución de material desde vehículos", self.inventory_tab.abrir_ventana_retorno_movil, self.info_color),
            ("📂 Conciliación Excel", "Comparar consumo contra archivo Excel", self.inventory_tab.abrir_conciliacion, self.primary_color),
            ("⚖️ Conciliación", "Ver y ajustar saldo de móvil (Manual)", self.inventory_tab.abrir_ventana_consiliacion, self.warning_color)
        ]
        
        for i, (title, description, command, color) in enumerate(movement_buttons):
            card = self.create_movement_card(movements_frame_inner, title, description, command, color, i)
        
        movements_frame_inner.columnconfigure(0, weight=1)
        movements_frame_inner.columnconfigure(1, weight=1)

    def create_movement_card(self, parent, title, description, command, color, index):
        """Crear tarjeta de movimiento moderna"""
        row = index // 2
        col = index % 2
        
        card = tk.Frame(parent, bg='white', relief='raised', borderwidth=0,
                       highlightbackground='#e0e0e0', highlightthickness=1)
        card.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
        
        # Título
        title_label = tk.Label(card, text=title, font=('Segoe UI', 14, 'bold'),
                              bg='white', fg=color, justify='left')
        title_label.pack(anchor='w', padx=20, pady=(20, 5))
        
        # Descripción
        desc_label = tk.Label(card, text=description, font=('Segoe UI', 10),
                             bg='white', fg='#666666', justify='left', wraplength=300)
        desc_label.pack(anchor='w', padx=20, pady=(0, 20))
        
        # Botón de acción
        action_btn = tk.Button(card, text="Abrir", command=command,
                              bg=color, fg='white', font=('Segoe UI', 10, 'bold'),
                              relief='flat', bd=0, padx=20, pady=8, cursor='hand2')
        action_btn.pack(anchor='e', padx=20, pady=(0, 15))
        action_btn.bind("<Enter>", lambda e, b=action_btn: b.configure(bg=darken_color(b.cget('bg'))))
        action_btn.bind("<Leave>", lambda e, b=action_btn, c=color: b.configure(bg=c))
        
        return card



# =================================================================
# 6. INICIALIZACIÓN DE LA APLICACIÓN
# =================================================================

if __name__ == "__main__":
    # 1. Crear ventana principal de inmediato para evitar sensación de lentitud
    root = tk.Tk()
    root.withdraw()

    # 2. Inicializar base de datos (con optimización de cache ya aplicada)
    db_existe = os.path.exists(DATABASE_NAME)
    inicializar_bd()
    
    if not db_existe:
        poblar_datos_iniciales()
        print("✅ Base de datos inicializada y poblada con datos iniciales.")
    else:
        print("✅ Base de datos ya existe. Esquema verificado.")
    
    # 3. EJECUTAR LIMPIEZA EN SEGUNDO PLANO
    def iniciar_tareas_segundo_plano():
        def run_optimization():
            try:
                print("⚡ Ejecutando tareas de optimización en segundo plano...")
                verificar_y_corregir_duplicados_completo(silent=True)
                print("✅ Tareas de optimización completadas.")
            except Exception as e:
                print(f"⚠️ Error en tareas de optimización: {e}")
        
        thread = threading.Thread(target=run_optimization, daemon=True)
        thread.start()
    
    def bootstrap_app(usuario):
        print(f"🔐 Sesión iniciada: {usuario['usuario']} ({usuario['rol']})")
        
        # IMPORTACIÓN DIFERIDA (PUNTO 3 - RENDIMIENTO)
        # Cargamos los módulos pesados SOLO después del login exitoso
        global DashboardTab, InventoryTab, ReportsTab, RemindersTab, CuadreContableMasivo, SettingsTab, AuditTab
        from gui.dashboard import DashboardTab
        from gui.inventory import InventoryTab
        from gui.reports import ReportsTab
        from gui.reminders import RemindersTab
        from gui.accounting import CuadreContableMasivo
        from gui.settings import SettingsTab
        from gui.audit import AuditTab
        
        login_top.destroy()
        
        # INICIAR PORTAL MÓVIL (PUNTO 5)
        import web_server
        portal_ip = web_server.start_server_thread()
        print(f"📡 PORTAL MÓVIL ACTIVO: http://{portal_ip}:5000")
        
        # Inicializar App principal
        app = ModernInventarioApp(root, usuario)
        root.deiconify() # Mostrar ventana principal
        
        # Mostrar alerta de portal móvil (opcional pero util)
        # app.mostrar_mensaje_emergente("Portal Móvil", f"Servidor iniciado en http://{portal_ip}:5000", "info")
        
        # Configurar cierre seguro
        def on_closing():
            if messagebox.askokcancel("Salir", "¿Está seguro que desea salir de la aplicación?"):
                root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)

    # Mostrar ventana de Login
    login_top = tk.Toplevel(root)
    login_top.protocol("WM_DELETE_WINDOW", root.destroy) # Si cierran login, cierran todo
    LoginWindow(login_top, bootstrap_app)
    
    # Programar limpieza para 1 segundo después para no bloquear ventana de login
    root.after(1000, iniciar_tareas_segundo_plano)
    
    # Iniciar aplicación
    root.mainloop()