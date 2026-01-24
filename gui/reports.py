import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from database import (
    obtener_reporte_asignacion_moviles, 
    obtener_stock_actual_y_moviles, 
    exportar_a_csv,
    obtener_nombres_moviles
)
from .vistas_reportes import DataTablePreview

from config import COLORS

class ReportsTab(tk.Frame):
    def __init__(self, master=None, open_history_callback=None):
        super().__init__(master)
        self.master = master
        self.open_history_callback = open_history_callback
        self.colors = COLORS
        
        # Configure local styles if needed, but assuming main app or styles.py handles global styles
        
        self.create_widgets()

    def create_widgets(self):
        # Frame principal
        self.configure(bg=self.colors['light_bg'])
        
        # Inner Frame
        reports_frame_inner = ttk.Frame(self, style='Modern.TFrame')
        reports_frame_inner.pack(expand=True, fill='both', padx=50, pady=50)
        
        report_buttons = [
            ("📋 Reporte de Móviles", "Inventario asignado por vehículo", self.abrir_ventana_reporte_moviles, self.colors['secondary']),
            ("📈 Inventario Total", "Stock completo con análisis", self.abrir_ventana_inventario_total, self.colors['success']),
            ("📜 Historial Completo", "Todos los movimientos del sistema", self.open_history_callback, self.colors['info'])
        ]
        
        for i, (title, description, command, color) in enumerate(report_buttons):
            if command: # Only create if command is provided
                self.create_report_card(reports_frame_inner, title, description, command, color, i)
        
        reports_frame_inner.columnconfigure(0, weight=1)
        reports_frame_inner.columnconfigure(1, weight=1)

    def create_report_card(self, parent, title, description, command, color, index):
        """Crear tarjeta de reporte moderna"""
        row = index // 3
        col = index % 3
        
        card = tk.Frame(parent, bg='white', relief='raised', borderwidth=0,
                       highlightbackground='#e0e0e0', highlightthickness=1)
        card.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
        
        # Icono
        icon_label = tk.Label(card, text="📊", font=('Segoe UI', 32),
                             bg='white', fg=color)
        icon_label.pack(pady=(20, 10))
        
        # Título
        title_label = tk.Label(card, text=title, font=('Segoe UI', 12, 'bold'),
                              bg='white', fg='#2c3e50', justify='center')
        title_label.pack(padx=20, pady=(0, 10))
        
        # Descripción
        desc_label = tk.Label(card, text=description, font=('Segoe UI', 9),
                             bg='white', fg='#666666', justify='center', wraplength=200)
        desc_label.pack(padx=20, pady=(0, 20))
        
        # Botón de acción
        action_btn = tk.Button(card, text="Generar Reporte", command=command,
                              bg=color, fg='white', font=('Segoe UI', 10, 'bold'),
                              relief='flat', bd=0, padx=20, pady=8, cursor='hand2')
        action_btn.pack(pady=(0, 15))
        
        # Hover effects
        def on_enter(e):
            e.widget['bg'] = self.darken_color(color)
        def on_leave(e):
            e.widget['bg'] = color
            
        action_btn.bind("<Enter>", on_enter)
        action_btn.bind("<Leave>", on_leave)
        
        return card

    def darken_color(self, color):
        """Oscurece un color hexadecimal"""
        # Simple implementation or import from utils if available
        # Assuming simple version for now
        if not color.startswith('#'):
            return color
        
        color = color.lstrip('#')
        r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        r = max(0, int(r * 0.8))
        g = max(0, int(g * 0.8))
        b = max(0, int(b * 0.8))
        return '#{:02x}{:02x}{:02x}'.format(r, g, b)

    def mostrar_mensaje_emergente(self, titulo, mensaje, tipo="info"):
        if tipo == "success":
            messagebox.showinfo(titulo, mensaje)
        elif tipo == "error":
            messagebox.showerror(titulo, mensaje)
        elif tipo == "warning":
            messagebox.showwarning(titulo, mensaje)
        else:
            messagebox.showinfo(titulo, mensaje)

    def abrir_ventana_reporte_moviles(self):
        """Abre ventana para reporte de móviles con interfaz moderna"""
        ventana = tk.Toplevel(self.master)
        ventana.title("📋 Reporte de Móviles")
        ventana.geometry("1200x700")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        # Header moderno
        header_frame = tk.Frame(ventana, bg=self.colors['secondary'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📋 REPORTE DE MÓVILES", 
                font=('Segoe UI', 16, 'bold'), bg=self.colors['secondary'], fg='white').pack(pady=20)
        
        # Frame de controles
        frame_controles = tk.Frame(ventana, padx=20, pady=20, bg='#E3F2FD')
        frame_controles.pack(fill='x')
        
        tk.Label(frame_controles, text="Seleccionar Móvil:", font=('Segoe UI', 10, 'bold'), bg='#E3F2FD').pack(side=tk.LEFT)
        moviles_db = obtener_nombres_moviles()
        movil_combo = ttk.Combobox(frame_controles, values=["TODOS"] + moviles_db, state="readonly", width=15)
        movil_combo.set("TODOS")
        movil_combo.pack(side=tk.LEFT, padx=10)
        
        def cargar_reporte(event=None):
            movil_seleccionado = movil_combo.get()
            
            # Limpiar tabla
            for item in tabla_reporte.get_children():
                tabla_reporte.delete(item)
            
            # Obtener datos - CORREGIDO: SIN DUPLICADOS
            if movil_seleccionado == "TODOS":
                datos = obtener_reporte_asignacion_moviles()
            else:
                datos = obtener_reporte_asignacion_moviles(movil_seleccionado)
            
            if not datos:
                tabla_reporte.insert('', 'end', values=("No hay datos", "", "", ""))
                return
            
            # Llenar tabla
            for movil, nombre, sku, cantidad in datos:
                tabla_reporte.insert('', 'end', values=(movil, nombre, sku, cantidad))
        
        movil_combo.bind("<<ComboboxSelected>>", cargar_reporte)
        
        # Tabla de reporte
        frame_tabla = tk.Frame(ventana)
        frame_tabla.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ("Móvil", "Producto", "SKU", "Cantidad")
        tabla_reporte = ttk.Treeview(frame_tabla, columns=columns, show='headings', height=20)
        
        # Configurar columnas
        tabla_reporte.heading("Móvil", text="MÓVIL")
        tabla_reporte.heading("Producto", text="PRODUCTO")
        tabla_reporte.heading("SKU", text="SKU")
        tabla_reporte.heading("Cantidad", text="CANTIDAD")
        
        tabla_reporte.column("Móvil", width=120, anchor='center')
        tabla_reporte.column("Producto", width=400)
        tabla_reporte.column("SKU", width=120, anchor='center')
        tabla_reporte.column("Cantidad", width=100, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=tabla_reporte.yview)
        tabla_reporte.configure(yscrollcommand=scrollbar.set)
        
        tabla_reporte.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # MEJORA: Configurar scroll suave del mouse
        def on_mousewheel(event):
            tabla_reporte.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        tabla_reporte.bind("<MouseWheel>", on_mousewheel)
        
        # Botones
        frame_botones = tk.Frame(ventana, bg='#f8f9fa')
        frame_botones.pack(fill='x', pady=10)
        
        def exportar_reporte():
            movil_seleccionado = movil_combo.get()
            datos = obtener_reporte_asignacion_moviles(movil_seleccionado if movil_seleccionado != "TODOS" else None)
            
            encabezados = ["Móvil", "Producto", "SKU", "Cantidad"]
            nombre_archivo = f"reporte_moviles_{movil_seleccionado.lower().replace(' ', '_')}.csv"
            
            # PUNTO 6: Abrir Previsualización
            DataTablePreview(self.master, f"Reporte de Móviles - {movil_seleccionado}", encabezados, datos, nombre_archivo)
        
        tk.Button(frame_botones, text="🔍 Previsualizar y Exportar", 
                  command=exportar_reporte, 
                  bg=self.colors['info'], fg='white', font=('Segoe UI', 10, 'bold'),
                  relief='flat', bd=0, padx=15, pady=8).pack(side=tk.LEFT, padx=20)
        
        # Cargar datos iniciales
        cargar_reporte()

    def abrir_ventana_inventario_total(self):
        """Abre ventana para inventario total con análisis completo"""
        ventana = tk.Toplevel(self.master)
        ventana.title("📈 Inventario Total")
        ventana.geometry("1400x800")
        ventana.configure(bg='#f8f9fa')
        ventana.grab_set()
        
        # Header moderno
        header_frame = tk.Frame(ventana, bg=self.colors['success'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📈 INVENTARIO TOTAL", 
                font=('Segoe UI', 16, 'bold'), bg=self.colors['success'], fg='white').pack(pady=20)
        
        # Frame de contenido
        frame_contenido = tk.Frame(ventana, padx=20, pady=20, bg='#f8f9fa')
        frame_contenido.pack(fill='both', expand=True)
        
        # Obtener datos del inventario total - CORREGIDO: SIN DUPLICADOS
        datos_inventario = obtener_stock_actual_y_moviles()
        
        if not datos_inventario:
            tk.Label(frame_contenido, text="No hay datos de inventario", 
                    font=('Segoe UI', 14), fg='gray', bg='#f8f9fa').pack(expand=True)
            return
        
        # Tabla de inventario total
        columns = ("Producto", "SKU", "Stock Bodega", "Stock Móviles", "Total", "Consumo", "Abasto")
        tabla_inventario = ttk.Treeview(frame_contenido, columns=columns, show='headings', height=20)
        
        # Configurar columnas
        tabla_inventario.heading("Producto", text="PRODUCTO")
        tabla_inventario.heading("SKU", text="SKU")
        tabla_inventario.heading("Stock Bodega", text="STOCK BODEGA")
        tabla_inventario.heading("Stock Móviles", text="STOCK MÓVILES")
        tabla_inventario.heading("Total", text="TOTAL")
        tabla_inventario.heading("Consumo", text="CONSUMO TOTAL")
        tabla_inventario.heading("Abasto", text="ABASTO TOTAL")
        
        tabla_inventario.column("Producto", width=300)
        tabla_inventario.column("SKU", width=120, anchor='center')
        tabla_inventario.column("Stock Bodega", width=120, anchor='center')
        tabla_inventario.column("Stock Móviles", width=120, anchor='center')
        tabla_inventario.column("Total", width=100, anchor='center')
        tabla_inventario.column("Consumo", width=120, anchor='center')
        tabla_inventario.column("Abasto", width=120, anchor='center')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame_contenido, orient="vertical", command=tabla_inventario.yview)
        tabla_inventario.configure(yscrollcommand=scrollbar.set)
        
        tabla_inventario.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # MEJORA: Configurar scroll suave del mouse
        def on_mousewheel(event):
            tabla_inventario.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        tabla_inventario.bind("<MouseWheel>", on_mousewheel)
        
        # Llenar tabla
        for nombre, sku, bodega, moviles, total, consumo, abasto in datos_inventario:
            # Colorear filas según el stock
            tags = ()
            if bodega == 0 and moviles == 0:
                tags = ('agotado',)
            elif bodega < 10:
                tags = ('bajo_stock',)
            
            tabla_inventario.insert('', 'end', values=(nombre, sku, bodega, moviles, total, consumo, abasto), tags=tags)
        
        # Configurar colores para las filas
        tabla_inventario.tag_configure('agotado', background='#FFEBEE')
        tabla_inventario.tag_configure('bajo_stock', background='#FFF3E0')
        
        # Estadísticas
        frame_estadisticas = tk.Frame(ventana, bg='#E8F5E8', padx=15, pady=15)
        frame_estadisticas.pack(fill='x', padx=20, pady=10)
        
        total_productos = len(datos_inventario)
        total_stock = sum(total for _, _, _, _, total, _, _ in datos_inventario)
        productos_agotados = sum(1 for _, _, bodega, moviles, _, _, _ in datos_inventario if bodega == 0 and moviles == 0)
        productos_bajo_stock = sum(1 for _, _, bodega, _, _, _, _ in datos_inventario if bodega < 10 and bodega > 0)
        
        tk.Label(frame_estadisticas, text=f"📊 ESTADÍSTICAS:", font=('Segoe UI', 12, 'bold'), bg='#E8F5E8').pack(anchor='w')
        tk.Label(frame_estadisticas, text=f"• Total Productos: {total_productos}", font=('Segoe UI', 10), bg='#E8F5E8').pack(anchor='w')
        tk.Label(frame_estadisticas, text=f"• Stock Total: {total_stock} unidades", font=('Segoe UI', 10), bg='#E8F5E8').pack(anchor='w')
        tk.Label(frame_estadisticas, text=f"• Productos Agotados: {productos_agotados}", font=('Segoe UI', 10), bg='#E8F5E8').pack(anchor='w')
        tk.Label(frame_estadisticas, text=f"• Productos con Stock Bajo: {productos_bajo_stock}", font=('Segoe UI', 10), bg='#E8F5E8').pack(anchor='w')
        
        # Botones
        frame_botones = tk.Frame(ventana, bg='#f8f9fa')
        frame_botones.pack(fill='x', pady=10)
        
        def exportar_inventario():
            encabezados = ["Producto", "SKU", "Stock Bodega", "Stock Móviles", "Total", "Consumo Total", "Abasto Total"]
            # PUNTO 6: Abrir Previsualización
            DataTablePreview(self.master, "Inventario Total", encabezados, datos_inventario, "inventario_total.csv")
        
        tk.Button(frame_botones, text="🔍 Previsualizar y Exportar", 
                  command=exportar_inventario, 
                  bg=self.colors['info'], fg='white', font=('Segoe UI', 10, 'bold'),
                  relief='flat', bd=0, padx=15, pady=8).pack(side=tk.LEFT, padx=20)
