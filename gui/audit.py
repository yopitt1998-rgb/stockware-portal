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
    eliminar_auditoria_completa,
    eliminar_consumo_pendiente,
    obtener_nombres_moviles
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
        top_frame.pack(side='top', fill='x', pady=(0, 20))

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
        
        # Filtro de Móvil (MODIFICADO: MULTI-SELECCIÓN)
        tk.Label(dates_frame, text="Móviles:", bg='#f8f9fa', font=('Segoe UI', 9)).pack(side='left', padx=(10, 0))
        
        self.moviles_seleccionados = [] # Lista de móviles seleccionados (vacío = Todos)
        self.btn_moviles = tk.Button(dates_frame, text="Todos los Móviles", command=self.abrir_selector_moviles,
                                    width=20, font=('Segoe UI', 9), relief='groove', bg='white')
        self.btn_moviles.pack(side='left', padx=5)

        # self.combo_movil removed
        # self._cargar_lista_moviles removed (logic moved to dialog)
        
        btn_frame = tk.Frame(top_frame, bg='#f8f9fa')
        btn_frame.pack(side='right')

        tk.Button(btn_frame, text="📈 Importar Excel Producción", command=self.importar_excel,
                 bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 9, 'bold'), relief='flat', padx=15, pady=8).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="🔍 Filtrar/Cargar", command=self.cargar_datos_pendientes,
                 bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 9, 'bold'), relief='flat', padx=15, pady=8).pack(side='left', padx=5)


        # --- SECCIÓN INFERIOR: ACCIONES DE CIERRE (Mover antes de la tabla para usar pack side=bottom) ---
        bottom_frame = tk.Frame(main_container, bg='#f8f9fa', pady=20)
        bottom_frame.pack(side='bottom', fill='x')

        self.btn_validar = tk.Button(bottom_frame, text="✅ Validar y Descontar del Inventario Real", 
                                    command=self.validar_seleccion,
                                    bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                                    relief='flat', padx=30, pady=12, state='disabled')
        self.btn_validar.pack(side='right')

        tk.Button(bottom_frame, text="❌ Eliminar Seleccionados", 
                  command=self.eliminar_seleccion,
                  bg=Styles.WARNING_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                  relief='flat', padx=15, pady=10).pack(side='right', padx=10)

        tk.Button(bottom_frame, text="🗑️ Limpiar Todo", 
                  command=self.limpiar_datos_audit,
                  bg=Styles.ACCENT_COLOR, fg='white', font=('Segoe UI', 10),
                  relief='flat', padx=15, pady=8).pack(side='right', padx=20)

        tk.Label(bottom_frame, text="* Seleccione los registros que coinciden con el físico y el Excel para procesar.", 
                font=('Segoe UI', 9, 'italic'), bg='#f8f9fa', fg='#666').pack(side='left')

        # --- SECCIÓN CENTRAL: TABLA DE PENDIENTES ---
        self.table_frame = tk.Frame(main_container, bg='white', relief='flat')
        self.table_frame.pack(side='top', fill='both', expand=True)

        # Inicializar con columnas base (se agregarán columnas dinámicas de materiales después)
        self.columnas_base = ["Fecha", "Móvil", "Técnico", "Ayudante", "Colilla", "Contrato"]
        self.columnas_materiales = []  # Se llenará dinámicamente
        self._row_ids = {}  # Diccionario oculto para mapear item_id -> ids_str
        
        # Crear tabla inicial vacía (se recreará con columnas dinámicas al cargar datos)
        self._crear_tabla_con_columnas(self.columnas_base)

    def abrir_selector_moviles(self):
        """Abre un diálogo modal para seleccionar múltiples móviles"""
        dialog = tk.Toplevel(self)
        dialog.title("Seleccionar Móviles")
        dialog.geometry("350x450")
        dialog.transient(self)
        dialog.grab_set()
        
        # Centrar
        x = self.main_app.master.winfo_x() + (self.main_app.master.winfo_width() // 2) - 175
        y = self.main_app.master.winfo_y() + (self.main_app.master.winfo_height() // 2) - 225
        dialog.geometry(f"+{x}+{y}")
        
        # Contenedor principal
        main_fr = tk.Frame(dialog, padx=10, pady=10)
        main_fr.pack(fill='both', expand=True)
        
        # Opciones Rápidas
        btn_fr = tk.Frame(main_fr)
        btn_fr.pack(fill='x', pady=(0, 10))
        
        vars_moviles = {} # {nombre_movil: BooleanVar}
        
        def toggle_all(state):
            for var in vars_moviles.values():
                var.set(state)
        
        tk.Button(btn_fr, text="Seleccionar Todos", command=lambda: toggle_all(True), font=('Segoe UI', 8)).pack(side='left', expand=True, fill='x', padx=2)
        tk.Button(btn_fr, text="Desmarcar Todos", command=lambda: toggle_all(False), font=('Segoe UI', 8)).pack(side='left', expand=True, fill='x', padx=2)
        
        # Lista Scrollable
        canvas = tk.Canvas(main_fr, borderwidth=0, background='#ffffff')
        frame = tk.Frame(canvas, background='#ffffff')
        vsb = tk.Scrollbar(main_fr, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((4,4), window=frame, anchor="nw")

        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        frame.bind("<Configure>", on_frame_configure)
        
        # Cargar Móviles
        try:
            todos_moviles = obtener_nombres_moviles()
        except:
            todos_moviles = []
            
        for movil in todos_moviles:
            var = tk.BooleanVar(value=True if not self.moviles_seleccionados or movil in self.moviles_seleccionados else False)
            # Si la lista estaba vacía (modo "Todos"), marcamos todo por defecto
            if not self.moviles_seleccionados: var.set(True)
            
            chk = tk.Checkbutton(frame, text=movil, variable=var, bg='white', anchor='w')
            chk.pack(fill='x', padx=5, pady=2)
            vars_moviles[movil] = var

        # Botón Aplicar
        def aplicar():
            seleccion = [m for m, var in vars_moviles.items() if var.get()]
            
            # Lógica: Si están todos seleccionados, volvemos a modo "Todos" (lista vacía)
            if len(seleccion) == len(todos_moviles) or len(seleccion) == 0:
                self.moviles_seleccionados = []
                self.btn_moviles.config(text="Todos los Móviles")
            else:
                self.moviles_seleccionados = seleccion
                txt = f"{len(seleccion)} Seleccionados" if len(seleccion) > 1 else seleccion[0]
                self.btn_moviles.config(text=txt)
            
            self.cargar_datos_pendientes()
            dialog.destroy()

        tk.Button(dialog, text="Aplicar Filtro", command=aplicar, 
                 bg=Styles.PRIMARY_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                 pady=5).pack(side='bottom', fill='x', padx=10, pady=10)

    # _cargar_lista_moviles y _show_context_menu siguen igual... espera, _cargar_lista_moviles ya no se usa, lo borré arriba en el comment pero debo asegurarme que no quede código muerto o incoherente.
    # Reutilizaré _show_context_menu.
    
    def _show_context_menu(self, event):
        item = self.tabla.identify_row(event.y)
        if item:
            if item not in self.tabla.selection():
                self.tabla.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def cargar_datos_pendientes(self):
        """Carga los datos pendientes en un hilo separado filtrando por fecha y MÓVILES MÚLTIPLES"""
        inicio = self.fecha_inicio.get().strip()
        fin = self.fecha_fin.get().strip()
        
        # Copia local para el thread
        filtro_moviles = list(self.moviles_seleccionados) if self.moviles_seleccionados else None 

        def run_load():
            try:
                # Obtener consumos con filtro de fecha
                consumos = obtener_consumos_pendientes(fecha_inicio=inicio, fecha_fin=fin)
                
                # Filtrar en memoria por móvil (MULTI-SELECT)
                if filtro_moviles:
                    # c = (id, movil, sku, nombre, cantidad, tecnico, ticket, fecha, colilla, contrato, ayudante)
                    consumos = [c for c in consumos if c[1] in filtro_moviles]
                
                # Programar actualización de la UI en el hilo principal
                self.after(0, lambda: self._aplicar_pendientes_ui(consumos))
            except Exception as e:
                print(f"⚠️ Error al cargar auditoría: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def _aplicar_pendientes_ui(self, consumos):
        """Aplica los consumos pendientes a la tabla con columnas dinámicas por material"""
        if not consumos:
            self.btn_validar.config(state='disabled')
            return

        # AGRUPAR consumos por orden (movil, fecha, tecnico, colilla, contrato)
        from collections import defaultdict
        ordenes = defaultdict(list)
        todos_productos = set()  # Para rastrear todos los productos únicos
        
        for c in consumos:
            # c = (id, movil, sku, nombre, cantidad, tecnico, ticket, fecha, colilla, contrato, ayudante)
            id_c, movil, sku, nombre, qty, tecnico, ticket, fecha, colilla, contrato, ayudante = c
            
            # Clave de agrupación: (movil, fecha, tecnico, colilla, contrato)
            key = (movil, fecha, tecnico, colilla or "", contrato or "", ayudante or "")
            
            ordenes[key].append({
                'id': id_c,
                'sku': sku,
                'nombre': nombre,
                'cantidad': qty
            })
            
            todos_productos.add(nombre)  # Usar nombre del producto, no SKU
        
        # Crear columnas dinámicas: base + productos
        productos_ordenados = sorted(list(todos_productos))
        self.columnas_materiales = productos_ordenados
        columnas_completas = self.columnas_base + productos_ordenados
        
        # Recrear tabla con nuevas columnas
        self._crear_tabla_con_columnas(columnas_completas)
        
        # Insertar una fila por orden con colores alternados
        row_num = 0
        self._row_ids = {}  # Limpiar diccionario de IDs
        
        for key, materiales in ordenes.items():
            movil, fecha, tecnico, colilla, contrato, ayudante = key
            
            # Concatenar todos los IDs (guardar internamente, no mostrar)
            ids = ",".join([str(m['id']) for m in materiales])
            
            # Crear diccionario de cantidades por producto
            cantidades_por_producto = {}
            for m in materiales:
                nombre = m['nombre']
                if nombre in cantidades_por_producto:
                    cantidades_por_producto[nombre] += m['cantidad']
                else:
                    cantidades_por_producto[nombre] = m['cantidad']
            
            # Construir valores de la fila (SIN IDs)
            valores = [
                fecha,
                movil,
                tecnico,
                ayudante,
                colilla,
                contrato
            ]
            
            # Agregar cantidades para cada producto (en orden de columnas)
            for producto in productos_ordenados:
                cant = cantidades_por_producto.get(producto, 0)
                valores.append(cant if cant > 0 else "")
            
            # Aplicar tag de fila alterna para mejor separación visual
            tag = 'evenrow' if row_num % 2 == 0 else 'oddrow'
            item_id = self.tabla.insert('', 'end', values=valores, tags=(tag,))
            
            # Guardar IDs en diccionario oculto
            self._row_ids[item_id] = ids
            
            row_num += 1
        
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
        """Procesa el Excel de auditoría con detección automática e inteligente de columnas"""
        # Limpiar columnas
        df.columns = [str(c).strip() for c in df.columns]
        
        print("\n" + "="*60)
        print("🔍 INICIANDO DETECCIÓN AUTOMÁTICA DE COLUMNAS DEL EXCEL")
        print("="*60)
        print(f"Columnas encontradas en Excel: {list(df.columns)}")
        
        # 1. Identificar columna de CONTRATO/ID con más variaciones
        col_contrato = None
        variaciones_contrato = [
            'CONTRATO', 'NUM_CONTRATO', 'NUMERO_CONTRATO', 'NRO_CONTRATO',
            'BILL_ID', 'BILLID', 'ACCOUNT', 'CUENTA', 'ID', 'CODIGO',
            'COD', 'NUM', 'NUMERO', 'NRO', 'ORDER', 'ORDEN', 'WO', 'WORK_ORDER'
        ]
        
        for col in df.columns:
            col_upper = col.upper().replace(' ', '_').replace('-', '_')
            # Buscar coincidencia exacta o parcial
            for var in variaciones_contrato:
                if var in col_upper or col_upper in var:
                    col_contrato = col
                    print(f"✅ Columna de CONTRATO detectada: '{col}'")
                    break
            if col_contrato:
                break
        
        if not col_contrato:
            print("⚠️ No se detectó columna de CONTRATO/ID. Procesando sin identificador.")
        
        # 2. Construir mapa completo de productos del sistema
        # Incluir nombre principal, SKU, y todas las variaciones
        mapa_nombres_sistema = {}  # {nombre_normalizado: sku}
        mapa_sku_sistema = {}      # {sku: sku} para detectar SKUs directos
        
        for nombre, sku, _ in PRODUCTOS_INICIALES:
            nombre_norm = nombre.lower().strip().replace(' ', '').replace('_', '').replace('-', '')
            mapa_nombres_sistema[nombre_norm] = sku
            # También agregar el SKU como clave
            sku_norm = sku.lower().strip().replace(' ', '').replace('_', '').replace('-', '')
            mapa_sku_sistema[sku_norm] = sku
        
        print(f"\n📦 Productos en sistema: {len(set(mapa_nombres_sistema.values()))} SKUs únicos")
        
        # 3. Detectar columnas de materiales con estrategia múltiple
        mapa_sku_columna = {}
        columnas_materiales = []
        columnas_no_detectadas = []
        
        for col in df.columns:
            if col == col_contrato:
                continue
            
            # Normalizar nombre de columna
            col_norm = col.lower().strip().replace(' ', '').replace('_', '').replace('-', '')
            
            best_match_sku = None
            metodo_deteccion = None
            
            # ESTRATEGIA 1: Match exacto (normalizado)
            if col_norm in mapa_nombres_sistema:
                best_match_sku = mapa_nombres_sistema[col_norm]
                metodo_deteccion = "Exacto"
            
            # ESTRATEGIA 2: Detectar si es un SKU directo
            elif col_norm in mapa_sku_sistema:
                best_match_sku = mapa_sku_sistema[col_norm]
                metodo_deteccion = "SKU Directo"
            
            # ESTRATEGIA 3: Match parcial (columna contiene nombre de producto)
            if not best_match_sku:
                for nombre_norm, sku in mapa_nombres_sistema.items():
                    if len(nombre_norm) >= 4:  # Solo para nombres con al menos 4 caracteres
                        if nombre_norm in col_norm or col_norm in nombre_norm:
                            best_match_sku = sku
                            metodo_deteccion = "Parcial"
                            break
            
            # ESTRATEGIA 4: Fuzzy matching mejorado
            if not best_match_sku:
                best_ratio = 0
                best_nombre = None
                for nombre_norm, sku in mapa_nombres_sistema.items():
                    ratio = difflib.SequenceMatcher(None, col_norm, nombre_norm).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match_sku = sku
                        best_nombre = nombre_norm
                
                # Umbral más bajo pero con validación
                if best_ratio >= 0.6:  # Bajado de 0.7 a 0.6
                    metodo_deteccion = f"Fuzzy ({best_ratio:.2f})"
                else:
                    best_match_sku = None
            
            # Registrar resultado
            if best_match_sku:
                mapa_sku_columna[col] = best_match_sku
                columnas_materiales.append(col)
                print(f"  ✅ '{col}' → SKU {best_match_sku} [{metodo_deteccion}]")
            else:
                columnas_no_detectadas.append(col)
        
        # Mostrar resumen
        print(f"\n📊 RESUMEN DE DETECCIÓN:")
        print(f"  ✅ Columnas detectadas: {len(columnas_materiales)}")
        print(f"  ❌ Columnas no detectadas: {len(columnas_no_detectadas)}")
        if columnas_no_detectadas:
            print(f"     Columnas ignoradas: {columnas_no_detectadas}")
        print("="*60 + "\n")
        
        if not columnas_materiales:
            messagebox.showwarning("Sin Columnas Detectadas", 
                                  f"No se pudieron detectar columnas de materiales en el Excel.\\n\\n"
                                  f"Columnas encontradas: {list(df.columns)}\\n\\n"
                                  f"Verifica que los nombres coincidan con los productos del sistema.")
            return pd.DataFrame()
        
        # 4. Transformar a formato largo (Melt)
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


            return df_melt[['SKU', 'CANTIDAD']][df_melt['CANTIDAD'] > 0]

    def eliminar_seleccion(self):
        items = self.tabla.selection()
        if not items:
            messagebox.showwarning("Atención", "Seleccione al menos un registro para eliminar.")
            return

        # Contar total de consumos individuales
        total_consumos = 0
        for item in items:
            ids_str = self._row_ids.get(item, "")
            if ids_str:
                ids_list = ids_str.split(',')
                total_consumos += len(ids_list)

        if not messagebox.askyesno("Confirmar Eliminación", 
                                   f"¿Está seguro de eliminar {len(items)} órdenes seleccionadas?\\n"
                                   f"Se borrarán un total de {total_consumos} registros de consumo pendientes.\\n\\n"
                                   "Esta acción NO se puede deshacer."):
            return

        exitos = 0
        errores = 0
        
        for item in items:
            ids_str = self._row_ids.get(item, "")
            if ids_str:
                ids_list = ids_str.split(',')
                for id_c in ids_list:
                    exito, _ = eliminar_consumo_pendiente(int(id_c))
                    if exito:
                        exitos += 1
                    else:
                        errores += 1

        if errores > 0:
             mostrar_mensaje_emergente(self.main_app.master, "Eliminación con Errores", 
                                       f"Se eliminaron {exitos} registros, pero fallaron {errores}.", "warning")
        else:
             mostrar_mensaje_emergente(self.main_app.master, "Eliminación Exitosa", 
                                       f"Se eliminaron {exitos} registros correctamente.", "success")
        
        self.cargar_datos_pendientes()

    def validar_seleccion(self):
        items = self.tabla.selection()
        if not items:
            messagebox.showwarning("Atención", "Seleccione al menos un registro para validar.")
            return

        # Contar total de consumos individuales
        total_consumos = 0
        for item in items:
            ids_str = self._row_ids.get(item, "")  # Obtener IDs del diccionario oculto
            if ids_str:
                ids_list = ids_str.split(',')
                total_consumos += len(ids_list)

        if not messagebox.askyesno("Confirmar Validación", 
                                   f"¿Está seguro de validar {len(items)} órdenes ({total_consumos} consumos)?\\nEsto ajustará el inventario real."):
            return

        exitos = 0
        total_procesados = 0
        
        for item in items:
            vals = self.tabla.item(item, 'values')
            # Estructura de la tabla: [Fecha, Móvil, Técnico, Ayudante, Colilla, Contrato, ...materiales]
            # Extraer valores de las columnas base (índices 0-5)
            fecha = vals[0]
            movil = vals[1]
            tecnico = vals[2]
            ayudante = vals[3]
            colilla = vals[4]
            contrato = vals[5]
            
            # Obtener IDs del diccionario oculto
            ids_str = self._row_ids.get(item, "")
            
            # Separar los IDs
            ids_list = [int(id_str.strip()) for id_str in ids_str.split(',')]
            
            # Obtener los consumos originales de la base de datos para procesar cada uno
            from database import obtener_consumos_pendientes
            consumos_orden = obtener_consumos_pendientes()
            
            # Filtrar solo los consumos de esta orden
            consumos_a_procesar = [c for c in consumos_orden if c[0] in ids_list]
            
            # Procesar cada consumo individual
            for c in consumos_a_procesar:
                id_c, movil_c, sku, nombre, qty, tecnico_c, ticket, fecha_c, colilla_c, contrato_c, ayudante_c = c
                
                obs = f"Cierre Auditado - Colilla: {colilla} - Contrato: {contrato} - Técnico: {tecnico} - Ayudante: {ayudante}"
                
                exito, msg = procesar_auditoria_consumo(id_c, sku, int(qty), movil, fecha, contrato, obs)
                if exito: 
                    exitos += 1
                total_procesados += 1

        mostrar_mensaje_emergente(self.main_app.master, "Proceso Completado", 
                                 f"Se validaron {exitos} de {total_procesados} consumos exitosamente.", "success")
        self.cargar_datos_pendientes()
        if hasattr(self.main_app, 'dashboard_tab'):
            self.main_app.dashboard_tab.actualizar_metricas()
