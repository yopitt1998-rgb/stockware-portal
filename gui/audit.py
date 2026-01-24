import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .styles import Styles
from .utils import mostrar_mensaje_emergente
from database import (
    obtener_consumos_pendientes,
    procesar_auditoria_consumo,
    obtener_stock_actual_y_moviles
)
import pandas as pd

class AuditTab(tk.Frame):
    """
    Pestaña de Auditoría de Terreno (Punto 5).
    Cruza información de Móviles, Excel y Stock Real.
    """
    def __init__(self, master, main_app):
        super().__init__(master)
        self.main_app = main_app
        self.configure(bg='#f8f9fa')
        
        self.datos_excel = None
        self.create_widgets()
        self.cargar_datos_pendientes()

    def create_widgets(self):
        # Layout principal
        main_container = tk.Frame(self, bg='#f8f9fa', padx=20, pady=20)
        main_container.pack(fill='both', expand=True)

        # --- SECCIÓN SUPERIOR: ACCIONES ---
        top_frame = tk.Frame(main_container, bg='#f8f9fa')
        top_frame.pack(fill='x', pady=(0, 20))

        tk.Label(top_frame, text="🔍 AUDITORÍA DE TERRENO", font=('Segoe UI', 16, 'bold'), bg='#f8f9fa', fg=Styles.PRIMARY_COLOR).pack(side='left')
        
        btn_frame = tk.Frame(top_frame, bg='#f8f9fa')
        btn_frame.pack(side='right')

        tk.Button(btn_frame, text="📈 Importar Excel Producción", command=self.importar_excel,
                 bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 9, 'bold'), relief='flat', padx=15, pady=8).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="🔄 Recargar Pendientes", command=self.cargar_datos_pendientes,
                 bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 9, 'bold'), relief='flat', padx=15, pady=8).pack(side='left', padx=5)

        # --- SECCIÓN CENTRAL: TABLA DE PENDIENTES ---
        table_frame = tk.Frame(main_container, bg='white', relief='flat')
        table_frame.pack(fill='both', expand=True)

        columns = ("ID", "Fecha", "Móvil", "Colilla", "Contrato", "SKU", "Producto", "Cant. Reportada", "Técnico", "Ayudante", "Excel", "Dif.")
        self.tabla = ttk.Treeview(table_frame, columns=columns, show='headings', style='Modern.Treeview', height=15)
        
        widths = [40, 90, 100, 80, 80, 100, 220, 110, 120, 120, 80, 60]
        for col, width in zip(columns, widths):
            self.tabla.heading(col, text=col.upper())
            self.tabla.column(col, width=width, anchor='center')
        
        self.tabla.column("Producto", anchor='w')
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)
        
        self.tabla.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # --- SECCIÓN INFERIOR: ACCIONES DE CIERRE ---
        bottom_frame = tk.Frame(main_container, bg='#f8f9fa', pady=20)
        bottom_frame.pack(fill='x')

        self.btn_validar = tk.Button(bottom_frame, text="✅ Validar y Descontar del Inventario Real", 
                                    command=self.validar_seleccion,
                                    bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                                    relief='flat', padx=30, pady=12, state='disabled')
        self.btn_validar.pack(side='right')

        tk.Label(bottom_frame, text="* Seleccione los registros que coinciden con el físico y el Excel para procesar.", 
                font=('Segoe UI', 9, 'italic'), bg='#f8f9fa', fg='#666').pack(side='left')

    def cargar_datos_pendientes(self):
        # Limpiar
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        
        consumos = obtener_consumos_pendientes()
        if not consumos:
            self.btn_validar.config(state='disabled')
            return

        for c in consumos:
            # c = (id, movil, sku, nombre, cantidad, tecnico, ticket, fecha, colilla, contrato, ayudante)
            id_c, movil, sku, nombre, qty, tecnico, ticket, fecha, colilla, contrato, ayudante = c
            
            val_excel = "---"
            dif = "---"
            
            # Si hay excel cargado, intentar cruzar
            if self.datos_excel is not None:
                match = self.datos_excel[self.datos_excel['SKU'] == str(sku)]
                if not match.empty:
                    val_excel = int(match.iloc[0]['CANTIDAD'])
                    dif = qty - val_excel
            
            # Orden: ID, Fecha, Móvil, Colilla, Contrato, SKU, Producto, Cant, Técnico, Ayudante, Excel, Dif
            self.tabla.insert('', 'end', values=(id_c, fecha, movil, colilla, contrato, sku, nombre, qty, tecnico, ayudante, val_excel, dif))
        
        self.btn_validar.config(state='normal')

    def importar_excel(self):
        filename = filedialog.askopenfilename(title="Seleccionar Excel de Producción", filetypes=[("Excel", "*.xlsx *.xls")])
        if filename:
            try:
                df = pd.read_excel(filename)
                # Normalizar columnas (esperamos SKU y CANTIDAD)
                df.columns = [c.upper().strip() for c in df.columns]
                if 'SKU' in df.columns and 'CANTIDAD' in df.columns:
                    self.datos_excel = df[['SKU', 'CANTIDAD']]
                    self.datos_excel['SKU'] = self.datos_excel['SKU'].astype(str)
                    mostrar_mensaje_emergente(self, "Éxito", "Excel cargado y cruzado con el reporte móvil.", "success")
                    self.cargar_datos_pendientes()
                else:
                    mostrar_mensaje_emergente(self, "Error", "El Excel debe tener columnas 'SKU' y 'CANTIDAD'.", "error")
            except Exception as e:
                mostrar_mensaje_emergente(self, "Error", f"No se pudo leer el Excel: {e}", "error")

    def validar_seleccion(self):
        items = self.tabla.selection()
        if not items:
            messagebox.showwarning("Atención", "Seleccione al menos un registro para validar.")
            return

        if not messagebox.askyesno("Confirmar Validación", f"¿Está seguro de validar {len(items)} consumos?\nEsto ajustará el inventario real."):
            return

        exitos = 0
        for item in items:
            vals = self.tabla.item(item, 'values')
            # vals indices: 0:id, 1:fecha, 2:movil, 3:colilla, 4:contrato, 5:sku, 6:nombre, 7:qty, 8:tecnico, 9:ayudante...
            id_c, fecha, movil, colilla, contrato, sku, qty, tecnico, ayudante = vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], vals[7], vals[8], vals[9]
            
            obs = f"Cierre Auditado - Colilla: {colilla} - Contrato: {contrato} - Técnico: {tecnico} - Ayudante: {ayudante}"
            
            exito, msg = procesar_auditoria_consumo(id_c, sku, int(qty), movil, fecha, contrato, obs)
            if exito: exitos += 1

        mostrar_mensaje_emergente(self.main_app.master, "Proceso Completado", f"Se validaron {exitos} registros de consumo exitosamente.", "success")
        self.cargar_datos_pendientes()
        if hasattr(self.main_app, 'dashboard_tab'):
            self.main_app.dashboard_tab.actualizar_metricas()
