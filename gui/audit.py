import tkinter as tk
import threading

from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
from .styles import Styles
from .utils import mostrar_mensaje_emergente
from database import (
    obtener_consumos_pendientes,
    procesar_auditoria_consumo,
    obtener_stock_actual_y_moviles,
    eliminar_auditoria_completa
)
import pandas as pd
import difflib
from config import PRODUCTOS_INICIALES

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
        
        # Filtros de fecha
        dates_frame = tk.Frame(top_frame, bg='#f8f9fa')
        dates_frame.pack(side='left', padx=20)

        tk.Label(dates_frame, text="Desde:", bg='#f8f9fa', font=('Segoe UI', 9)).pack(side='left')
        self.fecha_inicio = tk.Entry(dates_frame, width=12, font=('Segoe UI', 9))
        self.fecha_inicio.pack(side='left', padx=5)
        # Default: Hace 7 días
        self.fecha_inicio.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))

        tk.Label(dates_frame, text="Hasta:", bg='#f8f9fa', font=('Segoe UI', 9)).pack(side='left', padx=(10, 0))
        self.fecha_fin = tk.Entry(dates_frame, width=12, font=('Segoe UI', 9))
        self.fecha_fin.pack(side='left', padx=5)
        # Default: Hoy
        self.fecha_fin.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        btn_frame = tk.Frame(top_frame, bg='#f8f9fa')
        btn_frame.pack(side='right')

        tk.Button(btn_frame, text="📈 Importar Excel Producción", command=self.importar_excel,
                 bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 9, 'bold'), relief='flat', padx=15, pady=8).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="🔍 Filtrar/Cargar", command=self.cargar_datos_pendientes,
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

        tk.Button(bottom_frame, text="🗑️ Limpiar Todo", 
                  command=self.limpiar_datos_audit,
                  bg=Styles.ACCENT_COLOR, fg='white', font=('Segoe UI', 10),
                  relief='flat', padx=15, pady=8).pack(side='right', padx=20)

        tk.Label(bottom_frame, text="* Seleccione los registros que coinciden con el físico y el Excel para procesar.", 
                font=('Segoe UI', 9, 'italic'), bg='#f8f9fa', fg='#666').pack(side='left')

    def limpiar_datos_audit(self):
        """Limpia todos los consumos pendientes de la tabla y de la BD."""
        if not messagebox.askyesno("Confirmar Limpieza", "¿Está seguro de que desea eliminar TODOS los reportes pendientes de auditoría?\nEsta acción no se puede deshacer."):
            return

        exito, msg = eliminar_auditoria_completa()
        if exito:
            mostrar_mensaje_emergente(self, "Limpieza Exitosa", msg, "success")
            self.datos_excel = None # También limpiar el excel cargado en memoria
            self.cargar_datos_pendientes()
        else:
            mostrar_mensaje_emergente(self, "Error", msg, "error")

    def cargar_datos_pendientes(self):
        """Carga los datos pendientes en un hilo separado filtrando por fecha"""
        inicio = self.fecha_inicio.get().strip()
        fin = self.fecha_fin.get().strip()

        def run_load():
            try:
                # Obtener consumos con filtro de fecha
                consumos = obtener_consumos_pendientes(fecha_inicio=inicio, fecha_fin=fin)
                
                # Programar actualización de la UI en el hilo principal
                self.after(0, lambda: self._aplicar_pendientes_ui(consumos))
            except Exception as e:
                print(f"⚠️ Error al cargar auditoría: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def _aplicar_pendientes_ui(self, consumos):
        """Aplica los consumos pendientes a la tabla (hilo principal)"""
        if not self.tabla.winfo_exists():
            return

        # Limpiar
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        
        if not consumos:
            self.btn_validar.config(state='disabled')
            return

        for c in consumos:
            # c = (id, movil, sku, nombre, cantidad, tecnico, ticket, fecha, colilla, contrato, ayudante)
            id_c, movil, sku, nombre, qty, tecnico, ticket, fecha, colilla, contrato, ayudante = c
            
            val_excel = "---"
            dif = "---"
            
            # Si hay excel cargado, intentar cruzar por SKU y CONTRATO (si existe)
            if self.datos_excel is not None:
                # Intentar match por (SKU, Contrato) o solo SKU
                sku_str = str(sku)
                contrato_str = str(contrato) if contrato else None
                
                match = pd.DataFrame()
                if contrato_str and 'CONTRATO' in self.datos_excel.columns:
                    mask = (self.datos_excel['SKU'] == sku_str) & (self.datos_excel['CONTRATO'] == contrato_str)
                    match = self.datos_excel[mask]
                
                # Fallback a solo SKU si no hay match por contrato o no hay col contrato
                if match.empty:
                    match = self.datos_excel[self.datos_excel['SKU'] == sku_str]
                
                if not match.empty:
                    val_excel = int(match['CANTIDAD'].sum())
                    dif = qty - val_excel
            
            # Orden: ID, Fecha, Móvil, Colilla, Contrato, SKU, Producto, Cant, Técnico, Ayudante, Excel, Dif
            self.tabla.insert('', 'end', values=(id_c, fecha, movil, colilla, contrato, sku, nombre, qty, tecnico, ayudante, val_excel, dif))
        
        self.btn_validar.config(state='normal')

    def importar_excel(self):
        filename = filedialog.askopenfilename(title="Seleccionar Excel de Producción", filetypes=[("Excel", "*.xlsx *.xls")])
        if filename:
            try:
                df = pd.read_excel(filename)
                df_procesado = self._detectar_y_procesar_audit_excel(df)
                
                if not df_procesado.empty:
                    self.datos_excel = df_procesado
                    mostrar_mensaje_emergente(self, "Éxito", "Excel cargado y cruzado con el reporte móvil.", "success")
                    self.cargar_datos_pendientes()
                else:
                    mostrar_mensaje_emergente(self, "Error", "No se detectaron datos válidos en el Excel.", "error")
            except Exception as e:
                mostrar_mensaje_emergente(self, "Error", f"No se pudo leer el Excel: {e}", "error")

    def _detectar_y_procesar_audit_excel(self, df):
        """Procesa el Excel de auditoría soportando formato ancho y nombres en lugar de SKUs"""
        # Limpiar columnas
        df.columns = [str(c).strip() for c in df.columns]
        
        # 1. Identificar columna de CONTRATO
        col_contrato = None
        for col in df.columns:
            cl = col.upper()
            if cl in ['CONTRATO', 'NUM_CONTRATO', 'BILL_ID', 'ACCOUNT', 'ID']:
                col_contrato = col
                break
        
        # 2. Mapear columnas de productos (Headers) a SKUs
        mapa_sku_columna = {}
        # Mapa de referencia desde config
        mapa_nombres_sistema = {n.lower().strip(): sku for n, sku, _ in PRODUCTOS_INICIALES}
        
        columnas_materiales = []
        for col in df.columns:
            if col == col_contrato: continue
            
            cl_clean = col.lower().strip()
            
            # Match exacto o fuzzy
            best_match_sku = None
            if cl_clean in mapa_nombres_sistema:
                best_match_sku = mapa_nombres_sistema[cl_clean]
            else:
                # Fuzzy match básico (SequenceMatcher)
                best_ratio = 0
                for sn, ss in mapa_nombres_sistema.items():
                    ratio = difflib.SequenceMatcher(None, cl_clean, sn).ratio()
                    if ratio > 0.7: # Umbral de coincidencia
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_match_sku = ss
            
            if best_match_sku:
                mapa_sku_columna[col] = best_match_sku
                columnas_materiales.append(col)
        
        if not columnas_materiales:
            return pd.DataFrame()
            
        # 3. Transformar a formato largo (Melt)
        id_vars = [col_contrato] if col_contrato else []
        df_melt = df.melt(id_vars=id_vars, value_vars=columnas_materiales, var_name='original_name', value_name='cantidad')
        
        # Mapear SKUs y limpiar
        df_melt['SKU'] = df_melt['original_name'].map(mapa_sku_columna)
        df_melt['CANTIDAD'] = pd.to_numeric(df_melt['cantidad'], errors='coerce').fillna(0).astype(int)
        
        if col_contrato:
            df_melt['CONTRATO'] = df_melt[col_contrato].astype(str).str.strip()
            return df_melt[['SKU', 'CONTRATO', 'CANTIDAD']][df_melt['CANTIDAD'] > 0]
        else:
            return df_melt[['SKU', 'CANTIDAD']][df_melt['CANTIDAD'] > 0]

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
