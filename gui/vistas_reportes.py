import tkinter as tk
from tkinter import ttk, messagebox
from .styles import Styles
from .utils import darken_color, mostrar_mensaje_emergente
from database import exportar_a_csv
from tkinter import filedialog

class DataTablePreview(tk.Toplevel):
    """
    Ventana reutilizable para previsualizar datos antes de exportar (Punto 6).
    """
    def __init__(self, master, title, headers, data, filename_default="reporte.csv"):
        super().__init__(master)
        self.title(f"Previsualización: {title}")
        self.geometry("1000x700")
        self.configure(bg='#f8f9fa')
        self.grab_set()
        
        self.headers = headers
        self.data = data
        self.filename_default = filename_default
        
        self.create_widgets(title)
        self.cargar_datos()

    def create_widgets(self, title):
        # Header
        header_frame = tk.Frame(self, bg=Styles.PRIMARY_COLOR, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text=title.upper(), 
                font=('Segoe UI', 16, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
        
        # Frame de contenido
        content_frame = tk.Frame(self, padx=20, pady=20, bg='#f8f9fa')
        content_frame.pack(fill='both', expand=True)
        
        # Informativo
        tk.Label(content_frame, text=f"Total de registros: {len(self.data)}", 
                font=('Segoe UI', 10, 'italic'), bg='#f8f9fa', fg='#666').pack(anchor='w', pady=(0, 10))
        
        # Tabla
        table_frame = tk.Frame(content_frame)
        table_frame.pack(fill='both', expand=True)
        
        self.tabla = ttk.Treeview(table_frame, columns=self.headers, show='headings', style='Modern.Treeview')
        
        for col in self.headers:
            self.tabla.heading(col, text=col.upper())
            # Ajuste de ancho variable (simplificado)
            self.tabla.column(col, anchor='center', width=120)
            
        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tabla.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tabla.xview)
        self.tabla.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.tabla.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
        
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        
        # Buttons
        btn_frame = tk.Frame(self, bg='#f4f4f4', pady=15, padx=20)
        btn_frame.pack(fill='x')
        
        tk.Button(btn_frame, text="📤 Exportar a CSV / Excel", command=self.exportar,
                 bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', padx=20, pady=10, cursor='hand2').pack(side='right')
        
        tk.Button(btn_frame, text="❌ Cerrar", command=self.destroy,
                 bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 10),
                 relief='flat', padx=15, pady=10, cursor='hand2').pack(side='left')

    def cargar_datos(self):
        for row in self.data:
            self.tabla.insert('', tk.END, values=row)

    def exportar(self):
        filename = filedialog.asksaveasfilename(
            title="Guardar Reporte",
            initialfile=self.filename_default,
            defaultextension=".csv",
            filetypes=[("Archivo CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )
        
        if filename:
            exito, mensaje = exportar_a_csv(self.headers, self.data, filename)
            if exito:
                mostrar_mensaje_emergente(self, "Éxito", mensaje, "success")
            else:
                mostrar_mensaje_emergente(self, "Error", mensaje, "error")
