import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from database import obtener_configuracion, guardar_configuracion, crear_respaldo_bd, limpiar_base_datos, resetear_stock_movil
from .styles import Styles
from .utils import mostrar_mensaje_emergente
from datetime import datetime
import os

class SettingsTab(tk.Frame):
    def __init__(self, master, main_app):
        super().__init__(master)
        self.main_app = main_app
        self.configure(bg='#f8f9fa')
        
        self.logo_path = tk.StringVar()
        
        self.create_widgets()
        self.cargar_datos()

    def create_widgets(self):
        # Create a main frame to hold canvas and scrollbar
        main_frame = tk.Frame(self, bg='#f8f9fa')
        main_frame.pack(fill='both', expand=True)

        # Create Canvas and Scrollbar
        canvas = tk.Canvas(main_frame, bg='#f8f9fa', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        
        # Configure scrollbar
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack them
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Create the scrollable frame
        # IMPORTANT: Use a separate frame for the content
        container = ttk.Frame(canvas, style='Modern.TFrame')
        
        # Create window in canvas
        canvas_window = canvas.create_window((0, 0), window=container, anchor="nw")
        
        # Configure scrolling
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Ensure the inner frame is at least as wide as the canvas
            width = event.width
            canvas.itemconfig(canvas_window, width=width)
            
        def on_canvas_configure(event):
            # Update the width of the window to match the canvas
            canvas.itemconfig(canvas_window, width=event.width)
            
        container.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Enable MouseWheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
        # Bind mousewheel to canvas and all its children recursively if needed, 
        # but binding to canvas and frame is usually enough if focused or hovered
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # --- EXISTING CONTENT NOW PACKED INTO 'container' ---
        
        # Add padding to the inner content
        inner_content = tk.Frame(container, bg='#f8f9fa')
        inner_content.pack(fill='both', expand=True, padx=50, pady=30)
        
        # --- SECCIÓN DE SUCURSAL (NUEVO) ---
        tk.Label(inner_content, text="📍 CONFIGURACIÓN DE SUCURSAL", 
                font=('Segoe UI', 16, 'bold'), bg='#f8f9fa', fg=Styles.PRIMARY_COLOR).pack(pady=(0, 20), anchor='w')
        
        branch_frame = tk.Frame(inner_content, bg='white', padx=20, pady=20, highlightthickness=1, highlightbackground='#bdc3c7')
        branch_frame.pack(fill='x', pady=(0, 30))
        
        tk.Label(branch_frame, text="Seleccione la ubicación de trabajo actual:", 
                font=('Segoe UI', 10), bg='white').pack(anchor='w', pady=(0, 10))
        
        # Cargar preferencia actual
        from config import load_branch_preference, save_branch_preference
        self.current_branch = tk.StringVar(value=load_branch_preference())
        
        # Radio Buttons con estilo
        modes_frame = tk.Frame(branch_frame, bg='white')
        modes_frame.pack(fill='x')
        
        rb_chiriqui = tk.Radiobutton(modes_frame, text="CHIRIQUÍ (Bodega Principal)", variable=self.current_branch, 
                                   value="CHIRIQUI", command=self.on_branch_change,
                                   bg='white', font=('Segoe UI', 11), activebackground='white')
        rb_chiriqui.pack(side='left', padx=(0, 20))
        
        rb_santiago = tk.Radiobutton(modes_frame, text="SANTIAGO (Sucursal)", variable=self.current_branch, 
                                   value="SANTIAGO", command=self.on_branch_change,
                                   bg='white', font=('Segoe UI', 11), activebackground='white')
        rb_santiago.pack(side='left')
        
        tk.Label(branch_frame, text="ℹ️ El cambio requerirá reiniciar la aplicación.", 
                font=('Segoe UI', 9, 'italic'), fg='#7f8c8d', bg='white').pack(anchor='w', pady=(10, 0))

        # Divider
        ttk.Separator(inner_content, orient='horizontal').pack(fill='x', pady=20)

        # Title
        tk.Label(inner_content, text="⚙️ DATOS DE LA EMPRESA", 
                font=('Segoe UI', 16, 'bold'), bg='#f8f9fa', fg=Styles.PRIMARY_COLOR).pack(pady=(0, 20), anchor='w')
        
        # Form grid
        form_frame = tk.Frame(inner_content, bg='#f8f9fa')
        form_frame.pack(fill='x')
        
        # Labels and Entries
        fields = [
            ("Nombre de la Empresa:", "nombre_empresa"),
            ("RUT / RUC:", "rut"),
            ("Dirección:", "direccion"),
            ("Teléfono:", "telefono"),
            ("Email:", "email")
        ]
        
        self.entries = {}
        for i, (label_text, key) in enumerate(fields):
            tk.Label(form_frame, text=label_text, font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').grid(row=i, column=0, sticky='w', pady=10)
            entry = ttk.Entry(form_frame, width=50, font=('Segoe UI', 10))
            entry.grid(row=i, column=1, sticky='w', padx=20, pady=10)
            self.entries[key] = entry
            
        # Logo section
        tk.Label(form_frame, text="Logo de la Empresa:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').grid(row=5, column=0, sticky='w', pady=10)
        
        logo_frame = tk.Frame(form_frame, bg='#f8f9fa')
        logo_frame.grid(row=5, column=1, sticky='w', padx=20, pady=10)
        
        ttk.Entry(logo_frame, textvariable=self.logo_path, width=38, font=('Segoe UI', 9), state='readonly').pack(side='left')
        tk.Button(logo_frame, text="📁 Seleccionar", command=self.seleccionar_logo,
                  bg=Styles.SECONDARY_COLOR, fg='white', relief='flat', padx=10).pack(side='left', padx=5)
        
        # Bottom Buttons
        btn_frame = tk.Frame(inner_content, bg='#f8f9fa')
        btn_frame.pack(fill='x', pady=30)
        
        self.btn_guardar = tk.Button(btn_frame, text="💾 Guardar Cambios", command=self.guardar_datos,
                                   bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 12, 'bold'),
                                   relief='flat', padx=30, pady=10, cursor='hand2')
        self.btn_guardar.pack(side='left')
        
        # Botón de cambio de tema
        if hasattr(self.main_app, 'theme_manager'):
            theme_btn = self.main_app.theme_manager.create_theme_toggle_button(btn_frame)
            theme_btn.pack(side='left', padx=20)
        
        # Preview info
        info_frame = tk.Frame(inner_content, bg='#E8F5E9', padx=15, pady=15, relief='raised', borderwidth=0, highlightthickness=1, highlightbackground='#C8E6C9')
        info_frame.pack(fill='x', pady=10)
        
        tk.Label(info_frame, text="ℹ️ Estos datos se utilizarán automáticamente en:", 
                font=('Segoe UI', 10, 'bold'), bg='#E8F5E9', fg='#2E7D32').pack(anchor='w')
        tk.Label(info_frame, text="• Encabezados de reportes PDF y Excel\n• Ticket de salida de material\n• Documentos de inventario", 
                font=('Segoe UI', 9), bg='#E8F5E9', fg='#2E7D32', justify='left').pack(anchor='w', pady=(5, 0))

        # --- SECCIÓN DE RESPALDO (NUEVO) ---
        tk.Label(inner_content, text="📦 RESPALDO DE SEGURIDAD", 
                font=('Segoe UI', 13, 'bold'), bg='#f8f9fa', fg='#d35400').pack(pady=(30, 10), anchor='w')
        
        backup_frame = tk.Frame(inner_content, bg='#FFF3E0', padx=20, pady=20, highlightthickness=1, highlightbackground='#FFE0B2')
        backup_frame.pack(fill='x')
        
        tk.Label(backup_frame, text="Crea una copia exacta de tu base de datos actual para evitar pérdida de información.", 
                font=('Segoe UI', 10), bg='#FFF3E0').pack(side='left')
        
        tk.Button(backup_frame, text="🧱 Crear Copia de Seguridad", command=self.crear_respaldo,
                 bg='#e67e22', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=8, cursor='hand2').pack(side='right')

        # --- SECCIÓN DE LIMPIEZA DE BASE DE DATOS (NUEVO) ---
        tk.Label(inner_content, text="⚠️ LIMPIEZA DE BASE DE DATOS", 
                font=('Segoe UI', 13, 'bold'), bg='#f8f9fa', fg='#c0392b').pack(pady=(30, 10), anchor='w')
        
        cleanup_frame = tk.Frame(inner_content, bg='#FFEBEE', padx=20, pady=20, highlightthickness=1, highlightbackground='#FFCDD2')
        cleanup_frame.pack(fill='x')
        
        warning_text = tk.Label(cleanup_frame, 
                               text="⚠️ ADVERTENCIA: Esta acción eliminará TODOS los movimientos y datos del sistema.\n"
                                    "Solo se mantendrá la estructura de la base de datos. Esta operación es IRREVERSIBLE.\n"
                                    "Se recomienda crear una copia de seguridad antes de continuar.",
                               font=('Segoe UI', 9), bg='#FFEBEE', fg='#c0392b', justify='left')
        warning_text.pack(side='left', fill='x', expand=True)
        
        tk.Button(cleanup_frame, text="🗑️ Limpiar Base de Datos", command=self.limpiar_base_datos,
                 bg='#c0392b', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=8, cursor='hand2').pack(side='right')

        # --- SECCIÓN DE LIMPIEZA DE MÓVIL (NUEVO) ---
        tk.Label(inner_content, text="🧹 LIMPIAR STOCK DE MÓVIL", 
                font=('Segoe UI', 13, 'bold'), bg='#f8f9fa', fg='#00796B').pack(pady=(30, 10), anchor='w')
        
        mobile_cleanup_frame = tk.Frame(inner_content, bg='#E0F2F1', padx=20, pady=20, highlightthickness=1, highlightbackground='#B2DFDB')
        mobile_cleanup_frame.pack(fill='x')
        
        tk.Label(mobile_cleanup_frame, text="Elimina todo el stock asignado a un móvil y paquete específico.\nIdeal para resetear inventarios de técnicos.", 
                font=('Segoe UI', 9), bg='#E0F2F1', justify='left').pack(side='left', fill='x', expand=True)
        
        tk.Button(mobile_cleanup_frame, text="🧹 Limpiar Móvil", command=self.limpiar_movil_dialogo,
                 bg='#00796B', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=8, cursor='hand2').pack(side='right')


    def seleccionar_logo(self):
        filename = filedialog.askopenfilename(
            title="Seleccionar Logo",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp"), ("Todos los archivos", "*.*")]
        )
        if filename:
            self.logo_path.set(filename)

    def cargar_datos(self):
        config = obtener_configuracion()
        if config:
            for key, entry in self.entries.items():
                if config.get(key):
                    entry.delete(0, tk.END)
                    entry.insert(0, str(config[key]))
            
            if config.get('logo_path'):
                self.logo_path.set(config['logo_path'])

    def guardar_datos(self):
        datos = {key: entry.get().strip() for key, entry in self.entries.items()}
        datos['logo_path'] = self.logo_path.get()
        
        if not datos['nombre_empresa']:
            mostrar_mensaje_emergente(self, "Error", "El nombre de la empresa es obligatorio.", "error")
            return
            
        exito, mensaje = guardar_configuracion(datos)
        if exito:
            mostrar_mensaje_emergente(self, "Éxito", mensaje, "success")
            self.cargar_datos()
        else:
            mostrar_mensaje_emergente(self, "Error", mensaje, "error")

    def crear_respaldo(self):
        """Maneja el diálogo para crear una copia de seguridad."""
        fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_default = f"respaldo_inventario_{fecha}.db"
        
        dest_path = filedialog.asksaveasfilename(
            title="Guardar Copia de Seguridad",
            initialfile=nombre_default,
            defaultextension=".db",
            filetypes=[("Base de Datos SQLite", "*.db"), ("Todos los archivos", "*.*")]
        )
        
        if dest_path:
            exito, mensaje = crear_respaldo_bd(dest_path)
            if exito:
                mostrar_mensaje_emergente(self, "Copia Exitosa", mensaje, "success")
            else:
                mostrar_mensaje_emergente(self, "Error en Respaldo", mensaje, "error")

    def limpiar_base_datos(self):
        """Maneja la limpieza completa de la base de datos con confirmación doble."""
        # Primera confirmación
        respuesta1 = messagebox.askokcancel(
            "⚠️ ADVERTENCIA - Limpieza de Base de Datos",
            "Esta acción eliminará TODOS los movimientos y datos del sistema.\n\n"
            "Se eliminarán:\n"
            "• Todos los movimientos de inventario\n"
            "• Asignaciones a móviles\n"
            "• Consumos pendientes\n"
            "• Recordatorios\n"
            "• Préstamos activos\n"
            "• Números de serie registrados (equipos)\n"
            "• Cantidades de productos (se resetearán a 0)\n\n"
            "Esta operación es IRREVERSIBLE.\n\n"
            "¿Está seguro que desea continuar?",
            icon='warning'
        )
        
        if not respuesta1:
            return
        
        # Segunda confirmación (doble check)
        respuesta2 = messagebox.askyesno(
            "⚠️ CONFIRMACIÓN FINAL",
            "ÚLTIMA ADVERTENCIA:\n\n"
            "Está a punto de eliminar TODOS los datos del sistema.\n"
            "Esta acción NO SE PUEDE DESHACER.\n\n"
            "¿Realmente desea proceder con la limpieza?",
            icon='warning'
        )
        
        if not respuesta2:
            return
        
        # Pedir PIN de seguridad
        from tkinter import simpledialog
        pin = simpledialog.askstring("Seguridad", "Ingrese el PIN de seguridad para confirmar el borrado:", 
                                   show='*', parent=self)
        
        if pin is None: # Cancelado
            return
            
        if pin != "0440":
            mostrar_mensaje_emergente(self, "Error de Seguridad", "PIN incorrecto. Operación cancelada.", "error")
            return
        
        # Proceder con la limpieza
        exito, mensaje = limpiar_base_datos()
        if exito:
            mostrar_mensaje_emergente(self, "Limpieza Completada", mensaje, "success")
            # Actualizar dashboard si existe
            if hasattr(self.main_app, 'dashboard_tab'):
                self.main_app.dashboard_tab.actualizar_metricas()
        else:
            mostrar_mensaje_emergente(self, "Error en Limpieza", mensaje, "error")

    def on_branch_change(self):
        """Maneja el cambio de sucursal"""
        new_branch = self.current_branch.get()
        from config import save_branch_preference
        
        save_branch_preference(new_branch)
        
        messagebox.showinfo(
            "Reiniciar Aplicación", 
            f"Se ha cambiado la ubicación a {new_branch}.\n\n" 
            "Por favor, cierre y vuelva a abrir la aplicación para que los cambios surtan efecto.",
            parent=self
        )

    def limpiar_movil_dialogo(self):
        """Maneja el reset de stock de un móvil con PIN y selección."""
        # 1. Pedir PIN de seguridad
        from tkinter import simpledialog
        pin = simpledialog.askstring("Seguridad", "Ingrese el PIN de seguridad (0440):", 
                                   show='*', parent=self)
        
        if pin != "0440":
            if pin is not None:
                mostrar_mensaje_emergente(self, "Error", "PIN incorrecto.", "error")
            return
            
        # 2. Diálogo de selección
        from config import ALL_MOVILES
        
        selection_win = tk.Toplevel(self)
        selection_win.title("Seleccionar Móvil y Paquete")
        selection_win.geometry("400x320")
        selection_win.resizable(False, False)
        selection_win.transient(self)
        selection_win.grab_set()
        selection_win.configure(bg='#f8f9fa')
        
        tk.Label(selection_win, text="🧹 Resetear Stock", font=('Segoe UI', 14, 'bold'), 
                 bg='#f8f9fa', fg='#00796B').pack(pady=20)
        
        # Selección de Móvil
        tk.Label(selection_win, text="Seleccione el Móvil:", bg='#f8f9fa').pack(anchor='w', padx=40)
        movil_var = tk.StringVar(value=ALL_MOVILES[0] if ALL_MOVILES else "")
        combo_movil = ttk.Combobox(selection_win, textvariable=movil_var, values=ALL_MOVILES, state='readonly', width=35)
        combo_movil.pack(pady=5, padx=40)
        
        # Selección de Paquete
        tk.Label(selection_win, text="Seleccione el Paquete:", bg='#f8f9fa').pack(anchor='w', padx=40, pady=(10, 0))
        paquete_var = tk.StringVar(value="TODOS")
        combo_paquete = ttk.Combobox(selection_win, textvariable=paquete_var, 
                                     values=["PAQUETE A", "PAQUETE B", "PERSONALIZADO", "CARRO", "NINGUNO", "TODOS"], 
                                     state='readonly', width=35)
        combo_paquete.pack(pady=5, padx=40)
        
        def ejecutar_limpieza():
            movil = movil_var.get()
            paquete = paquete_var.get()
            
            if not movil or not paquete:
                return
                
            if messagebox.askyesno("Confirmar", f"¿Realmente desea ELIMINAR todo el stock de {movil} en el {paquete}?", parent=selection_win):
                exito, mensaje = resetear_stock_movil(movil, paquete)
                if exito:
                    mostrar_mensaje_emergente(self, "Éxito", mensaje, "success")
                    selection_win.destroy()
                else:
                    mostrar_mensaje_emergente(self, "Error", mensaje, "error")
        
        tk.Button(selection_win, text="🚀 Ejecutar Limpieza", command=ejecutar_limpieza,
                 bg='#00796B', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=10).pack(pady=30)

