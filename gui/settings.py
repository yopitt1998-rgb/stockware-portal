import tkinter as tk
from tkinter import ttk, filedialog
from database import obtener_configuracion, guardar_configuracion, crear_respaldo_bd
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
        # Main container with padding
        container = ttk.Frame(self, style='Modern.TFrame')
        container.pack(fill='both', expand=True, padx=50, pady=30)
        
        # Title
        tk.Label(container, text="⚙️ CONFIGURACIÓN DE LA EMPRESA", 
                font=('Segoe UI', 16, 'bold'), bg='#f8f9fa', fg=Styles.PRIMARY_COLOR).pack(pady=(0, 20), anchor='w')
        
        # Form grid
        form_frame = tk.Frame(container, bg='#f8f9fa')
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
        btn_frame = tk.Frame(container, bg='#f8f9fa')
        btn_frame.pack(fill='x', pady=30)
        
        self.btn_guardar = tk.Button(btn_frame, text="💾 Guardar Cambios", command=self.guardar_datos,
                                   bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 12, 'bold'),
                                   relief='flat', padx=30, pady=10, cursor='hand2')
        self.btn_guardar.pack(side='left')
        
        # Preview info
        info_frame = tk.Frame(container, bg='#E8F5E9', padx=15, pady=15, relief='raised', borderwidth=0, highlightthickness=1, highlightbackground='#C8E6C9')
        info_frame.pack(fill='x', pady=10)
        
        tk.Label(info_frame, text="ℹ️ Estos datos se utilizarán automáticamente en:", 
                font=('Segoe UI', 10, 'bold'), bg='#E8F5E9', fg='#2E7D32').pack(anchor='w')
        tk.Label(info_frame, text="• Encabezados de reportes PDF y Excel\n• Ticket de salida de material\n• Documentos de inventario", 
                font=('Segoe UI', 9), bg='#E8F5E9', fg='#2E7D32', justify='left').pack(anchor='w', pady=(5, 0))

        # --- SECCIÓN DE RESPALDO (NUEVO) ---
        tk.Label(container, text="📦 RESPALDO DE SEGURIDAD", 
                font=('Segoe UI', 13, 'bold'), bg='#f8f9fa', fg='#d35400').pack(pady=(30, 10), anchor='w')
        
        backup_frame = tk.Frame(container, bg='#FFF3E0', padx=20, pady=20, highlightthickness=1, highlightbackground='#FFE0B2')
        backup_frame.pack(fill='x')
        
        tk.Label(backup_frame, text="Crea una copia exacta de tu base de datos actual para evitar pérdida de información.", 
                font=('Segoe UI', 10), bg='#FFF3E0').pack(side='left')
        
        tk.Button(backup_frame, text="🧱 Crear Copia de Seguridad", command=self.crear_respaldo,
                 bg='#e67e22', fg='white', font=('Segoe UI', 10, 'bold'),
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

