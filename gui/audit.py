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
    obtener_nombres_moviles,
    actualizar_consumo_pendiente,
    exportar_a_csv,
    obtener_series_por_sku_y_ubicacion
)
import pandas as pd
import difflib
from config import PRODUCTOS_INICIALES, MOVILES_DISPONIBLES, MOVILES_SANTIAGO, ALL_MOVILES

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
        self.moviles_seleccionados = []  # Inicializar lista de móviles seleccionados
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

        # Filtro de Texto (Buscador)
        tk.Label(dates_frame, text="Buscar:", bg='#f8f9fa', font=('Segoe UI', 9)).pack(side='left', padx=(10, 0))
        self.filtro_entry = ttk.Entry(dates_frame, width=25, font=('Segoe UI', 9))
        self.filtro_entry.pack(side='left', padx=5)
        self.filtro_entry.bind('<Return>', lambda e: self.cargar_datos_pendientes())
        
        # Botón Buscar explícito (UX mejora)
        tk.Button(dates_frame, text="🔍", command=self.cargar_datos_pendientes,
                 bg='#00897B', fg='white', font=('Segoe UI', 8, 'bold'), relief='flat').pack(side='left', padx=0)
        
        # Botón de reset filtros
        tk.Button(dates_frame, text="✖", command=lambda: [self.filtro_entry.delete(0, 'end'), self.cargar_datos_pendientes()],
                 bg='#e0e0e0', font=('Segoe UI', 8), relief='flat').pack(side='left', padx=2)

        btn_frame = tk.Frame(top_frame, bg='#f8f9fa')
        btn_frame.pack(side='right')

        tk.Button(btn_frame, text="✅ Exportar XLS", command=self.exportar_excel,
                 bg='#00897B', fg='white', font=('Segoe UI', 9, 'bold'), relief='flat', padx=10, pady=4).pack(side='left', padx=5)

        tk.Button(btn_frame, text="📈 Importar", command=self.importar_excel,
                 bg=Styles.INFO_COLOR, fg='white', font=('Segoe UI', 9, 'bold'), relief='flat', padx=10, pady=4).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="🔍 Filtrar/Cargar", command=self.cargar_datos_pendientes,
                 bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 9, 'bold'), relief='flat', padx=10, pady=4).pack(side='left', padx=5)

        tk.Button(btn_frame, text="📥 Retorno Manual", command=self.abrir_retorno_manual,
                 bg='#FF9800', fg='white', font=('Segoe UI', 9, 'bold'), relief='flat', padx=10, pady=4).pack(side='left', padx=5)


        # --- SECCIÓN INFERIOR: ACCIONES DE CIERRE (Mover antes de la tabla para usar pack side=bottom) ---
        bottom_frame = tk.Frame(main_container, bg='#f8f9fa', pady=20)
        bottom_frame.pack(side='bottom', fill='x')

        self.btn_validar = tk.Button(bottom_frame, text="✅ Validar y Descontar del Inventario Real", 
                                    command=self.validar_seleccion,
                                    bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                                    relief='flat', padx=30, pady=12, state='disabled')
        self.btn_validar.pack(side='right')

        tk.Button(bottom_frame, text="✏️ Editar", 
                  command=self.editar_seleccion,
                  bg='#5C6BC0', fg='white', font=('Segoe UI', 10, 'bold'),
                  relief='flat', padx=15, pady=10).pack(side='right', padx=10)

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

        # --- LAYOUT DE DOS TABLAS: SUPERIOR E INFERIOR ---
        # Contenedor principal dividido en dos partes
        tables_container = tk.Frame(main_container, bg='#f8f9fa')
        tables_container.pack(side='top', fill='both', expand=True, pady=(10, 0))
        
        # === TABLA SUPERIOR: AUDITORÍA DE CONSUMO ===
        top_section = tk.LabelFrame(tables_container, text="📋 AUDITORÍA DE CONSUMO (Reportes del Día)", 
                                    font=('Segoe UI', 11, 'bold'), bg='#f8f9fa', fg=Styles.PRIMARY_COLOR, 
                                    relief='groove', borderwidth=2, padx=5, pady=5)
        top_section.pack(side='top', fill='both', expand=True, pady=(0, 10))
        
        self.table_frame = tk.Frame(top_section, bg='white', relief='flat')
        self.table_frame.pack(fill='both', expand=True)

        # === TABLA INFERIOR: AUDITORÍA FÍSICA ===
        bottom_section = tk.LabelFrame(tables_container, text="📦 AUDITORÍA FÍSICA (Materiales Asignados al Móvil)", 
                                       font=('Segoe UI', 11, 'bold'), bg='#f8f9fa', fg=Styles.ACCENT_COLOR,
                                       relief='groove', borderwidth=2, padx=5, pady=5)
        bottom_section.pack(side='bottom', fill='both', expand=False, pady=(10, 0))
        
        # Frame para tabla física
        self.tabla_fisica_frame = tk.Frame(bottom_section, bg='white')
        self.tabla_fisica_frame.pack(fill='both', expand=True)
        
        # Crear tabla física
        cols_fisica = ('Producto', 'SKU', 'Cantidad Asignada')
        self.tabla_fisica = ttk.Treeview(self.tabla_fisica_frame, columns=cols_fisica, 
                                        show='headings', height=6)
        
        self.tabla_fisica.heading('Producto', text='PRODUCTO')
        self.tabla_fisica.heading('SKU', text='SKU')
        self.tabla_fisica.heading('Cantidad Asignada', text='CANTIDAD ASIGNADA')
        
        self.tabla_fisica.column('Producto', width=300)
        self.tabla_fisica.column('SKU', width=120, anchor='center')
        self.tabla_fisica.column('Cantidad Asignada', width=150, anchor='center')
        
        scroll_fisica = ttk.Scrollbar(self.tabla_fisica_frame, orient='vertical', 
                                     command=self.tabla_fisica.yview)
        self.tabla_fisica.configure(yscrollcommand=scroll_fisica.set)
        
        self.tabla_fisica.pack(side='left', fill='both', expand=True)
        self.tabla_fisica.bind("<Double-1>", self.mostrar_detalle_series)
        scroll_fisica.pack(side='right', fill='y')
        
        # Mensaje inicial
        self.tabla_fisica.insert('', 'end', values=('', 'Seleccione un móvil para ver auditoría física', ''))

        # Inicializar con columnas base (se agregarán columnas dinámicas de materiales después)
        self.columnas_base = ["Fecha", "Móvil", "Técnico", "Ayudante", "Colilla", "Contrato"]
        self.columnas_materiales = []  # Se llenará dinámicamente
        self._row_ids = {}  # Diccionario oculto para mapear item_id -> ids_str
        
        # Crear tabla inicial vacía (se recreará con columnas dinámicas al cargar datos)
        self._crear_tabla_con_columnas(self.columnas_base)

        # Context Menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="✏️ Editar", command=self.editar_seleccion)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="❌ Eliminar Seleccionados", command=self.eliminar_seleccion)

    def abrir_selector_moviles(self):
        """Abre un diálogo modal para seleccionar múltiples móviles"""
        dialog = tk.Toplevel(self)
        dialog.title("Seleccionar Móviles")
        dialog.geometry("350x450")
        dialog.transient(self)
        dialog.grab_set()
        
        # FUNCION APLICAR (Definida antes para usar en protocol)
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
            self.actualizar_auditoria_fisica()  # Actualizar tabla física también
            dialog.destroy()

        # Al cerrar con X, aplicar automáticamente (UX mejora)
        dialog.protocol("WM_DELETE_WINDOW", aplicar)
        
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
        
        # Cargar Móviles: Usar SOLAMENTE los móviles del contexto actual
        from config import CURRENT_CONTEXT
        todos_moviles = CURRENT_CONTEXT.get('MOVILES', [])
        
        # Si la lista está vacía (fallback), intentar cargar DB (aunque debería estar llena por contexto)
        if not todos_moviles:
             try:
                todos_moviles = obtener_nombres_moviles()
             except:
                todos_moviles = []
            
        todos_moviles = sorted(list(set(todos_moviles)))
            
        for movil in todos_moviles:
            var = tk.BooleanVar(value=True if not self.moviles_seleccionados or movil in self.moviles_seleccionados else False)
            # Si la lista estaba vacía (modo "Todos"), marcamos todo por defecto
            if not self.moviles_seleccionados: var.set(True)
            
            chk = tk.Checkbutton(frame, text=movil, variable=var, bg='white', anchor='w')
            chk.pack(fill='x', padx=5, pady=2)
            vars_moviles[movil] = var

        # Botón Aplicar


        tk.Button(dialog, text="✅ APLICAR FILTRO", command=aplicar, 
                  bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                  pady=8).pack(side='bottom', fill='x', padx=10, pady=10)


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
    
    def _crear_tabla_con_columnas(self, columnas):
        """Recrea el widget Treeview con las columnas especificadas"""
        # Limpiar frame de la tabla
        for widget in self.table_frame.winfo_children():
            widget.destroy()
            
        # Scrollbars
        scroll_y = ttk.Scrollbar(self.table_frame, orient="vertical")
        scroll_x = ttk.Scrollbar(self.table_frame, orient="horizontal")

        # Treeview
        self.tabla = ttk.Treeview(self.table_frame, columns=columnas, show='headings',
                                 yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        scroll_y.config(command=self.tabla.yview)
        scroll_x.config(command=self.tabla.xview)
        
        scroll_y.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')
        self.tabla.pack(side='left', fill='both', expand=True, padx=2, pady=2)
        
        # Configurar columnas
        for col in columnas:
            self.tabla.heading(col, text=col)
            # Ancho dinámico básico
            width = 100
            if col in ["Técnico", "Ayudante", "Móvil"]: width = 150
            if col == "Fecha": width = 120
            self.tabla.column(col, width=width, anchor='center')

        # Bindings
        self.tabla.bind("<Button-3>", self._show_context_menu)
        self.tabla.tag_configure('match', background='#d4edda') # Verde claro para coincidencias
        self.tabla.tag_configure('mismatch', background='#f8d7da') # Rojo claro para diferencias


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
        texto_buscar = self.filtro_entry.get().strip().upper()
        
        # Copialoc para el thread
        filtro_moviles = list(self.moviles_seleccionados) if self.moviles_seleccionados else None 

        def run_load():
            try:
                # OPTIMIZADO: Determinar móviles permitidos (manual o por sucursal)
                moviles_sql = filtro_moviles
                
                if not moviles_sql:
                    # FIX: Data Isolation by Branch (Si no hay filtro MANUAL, usar contexto de SUCURSAL)
                    from config import CURRENT_CONTEXT
                    allowed_moviles = CURRENT_CONTEXT.get('MOVILES', [])
                    if allowed_moviles:
                        moviles_sql = allowed_moviles
                
                # OPTIMIZADO: Pasar filtro de móviles directamente a la query SQL
                # Ya no filtramos en memoria, lo hace la base de datos
                consumos = obtener_consumos_pendientes(
                    fecha_inicio=inicio, 
                    fecha_fin=fin,
                    moviles_filtro=moviles_sql
                )
                
                # Filtrar por texto de búsqueda si existe (esto es rápido comparado con filtrar móviles)
                if texto_buscar:
                    consumos_filtrados = []
                    for c in consumos:
                        # c = (id, movil, sku, nombre, cantidad, tecnico, ticket, fecha, colilla, contrato, ayudante)
                        datos_fila = [
                            str(c[1]), # Movil
                            str(c[5]), # Tecnico
                            str(c[6]), # Ticket
                            str(c[8]), # Colilla
                            str(c[9]), # Contrato
                            str(c[10]) # Ayudante
                        ]
                        if any(texto_buscar in d.upper() for d in datos_fila if d):
                            consumos_filtrados.append(c)
                    consumos = consumos_filtrados
                
                # Programar actualización de la UI en el hilo principal
                self.after(0, lambda: self._aplicar_pendientes_ui(consumos))
            except Exception as e:
                print(f"⚠️ Error al cargar auditoría: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def _aplicar_pendientes_ui(self, consumos):
        """Aplica los consumos pendientes a la tabla con columnas dinámicas por material"""
        # Si no hay consumos, limpiar tabla y salir
        if not consumos:
            self._crear_tabla_con_columnas(self.columnas_base) # Restablecer tabla vacía
            self.btn_validar.config(state='disabled')
            return

        # AGRUPAR consumos por orden (movil, fecha, tecnico, colilla, contrato)
        from collections import defaultdict
        ordenes = defaultdict(list)
        todos_productos = set()  # Para rastrear todos los productos únicos
        
        for c in consumos:
            # c = (id, movil, sku, nombre, cantidad, tecnico, ticket, fecha, colilla, contrato, ayudante)
            id_c, movil, sku, nombre, qty, tecnico, ticket, fecha, colilla, contrato, ayudante, seriales_usados = c
            
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
                id_c, movil_c, sku, nombre, qty, tecnico_c, ticket, fecha_c, colilla_c, contrato_c, ayudante_c, seriales_usados = c
                
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

    def exportar_excel(self):
        """Exporta la vista actual de la tabla a Excel"""
        if not self.tabla.get_children():
            messagebox.showinfo("Información", "No hay datos para exportar.")
            return

        filename = filedialog.asksaveasfilename(
            title="Exportar Auditoría",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")]
        )
        if not filename:
            return

        # Recopilar datos de la tabla
        columnas = self.columnas_base + self.columnas_materiales
        datos_tabla = []
        for item in self.tabla.get_children():
            datos_tabla.append(self.tabla.item(item)['values'])

        try:
            import pandas as pd
            
            # Verificar dependencias opcionales
            try:
                import openpyxl
            except ImportError:
                if messagebox.askyesno("Falta Dependencia", "Se requiere 'openpyxl' para exportar a Excel.\n¿Desea instalarlo ahora?"):
                    import subprocess, sys
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
                    import openpyxl # Reintentar
                else:
                    return

            df = pd.DataFrame(datos_tabla, columns=columnas)
            
            if filename.endswith('.csv'):
                df.to_csv(filename, index=False, encoding='utf-8-sig') # UTF-8-SIG para Excel
            else:
                # Usar engine openpyxl explícitamente y manejar errores de escritura
                with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Auditoria')
            
            mostrar_mensaje_emergente(self, "Éxito", f"Exportado correctamente a:\n{filename}", "success")
        except Exception as e:
            msg = f"Fallo al exportar: {e}"
            print(msg)
            mostrar_mensaje_emergente(self, "Error", msg, "error")

    def editar_seleccion(self):
        """Abre dialogo para editar cabeceras de la orden seleccionada"""
        selected = self.tabla.selection()
        if not selected:
            messagebox.showwarning("Editar", "Seleccione una fila para editar.")
            return
        
        if len(selected) > 1:
            messagebox.showwarning("Editar", "Seleccione solo una fila para editar.")
            return

        item = selected[0]
        values = self.tabla.item(item, 'values')
        ids_str = self._row_ids.get(item, "")
        
        # values: [Fecha, Móvil, Técnico, Ayudante, Colilla, Contrato, ...]
        # Índices fijos según `_aplicar_pendientes_ui`:
        # 0: Fecha, 1: Movil, 2: Tecnico, 3: Ayudante, 4: Colilla, 5: Contrato
        
        fecha_orig = values[0]
        movil_orig = values[1]
        tecnico_orig = values[2]
        ayudante_orig = values[3]
        colilla_orig = values[4]
        contrato_orig = values[5]
        
        # Dialogo de Edición
        dialog = tk.Toplevel(self)
        dialog.title("✏️ Editar Orden de Auditoría")
        dialog.geometry("400x500")
        dialog.transient(self)
        dialog.grab_set()
        
        # Formulario
        tk.Label(dialog, text="Editar Datos Generales", font=('Segoe UI', 12, 'bold')).pack(pady=10)
        
        frame_form = tk.Frame(dialog, padx=20)
        frame_form.pack(fill='both', expand=True)
        
        def add_field(label, val):
            tk.Label(frame_form, text=label, anchor='w').pack(fill='x', pady=(5,0))
            entry = tk.Entry(frame_form)
            entry.insert(0, val)
            entry.pack(fill='x')
            return entry

        e_fecha = add_field("Fecha (YYYY-MM-DD):", fecha_orig)
        e_movil = add_field("Móvil:", movil_orig) # Podría ser un combobox, pero dejemos entry por flexibilidad
        e_tecnico = add_field("Técnico:", tecnico_orig)
        e_ayudante = add_field("Ayudante:", ayudante_orig)
        e_colilla = add_field("Colilla:", colilla_orig)
        e_contrato = add_field("Contrato / Ref:", contrato_orig)
        
        # Helper para guardar
        def guardar_cambios():
            n_fecha = e_fecha.get().strip()
            n_movil = e_movil.get().strip()
            n_tecnico = e_tecnico.get().strip()
            n_ayudante = e_ayudante.get().strip()
            n_colilla = e_colilla.get().strip()
            n_contrato = e_contrato.get().strip()
            
            if not n_fecha or not n_movil:
                messagebox.showerror("Error", "Fecha y Móvil son obligatorios")
                return

            if not ids_str:
                return # Should not happen
                
            ids_list = ids_str.split(',')
            exitos = 0
            errores = 0
            
            for id_c in ids_list:
                ok, msg = actualizar_consumo_pendiente(
                    id_c, n_tecnico, n_fecha, n_contrato, n_colilla, n_ayudante, n_movil
                )
                if ok: exitos +=1
                else: errores += 1
            
            if errores > 0:
                messagebox.showwarning("Resultados", f"Actualizados: {exitos}, Errores: {errores}")
            else:
                mostrar_mensaje_emergente(self, "Editado", "Registro actualizado correctamente.", "success")
            
            dialog.destroy()
            self.cargar_datos_pendientes()

        tk.Button(dialog, text="💾 Guardar Cambios", command=guardar_cambios,
                 bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 10, 'bold'), pady=10).pack(fill='x', padx=20, pady=20)

    def actualizar_auditoria_fisica(self):
        """Actualiza la tabla de auditoría física con materiales del móvil MENOS consumo reportado"""
        # Limpiar tabla
        for item in self.tabla_fisica.get_children():
            self.tabla_fisica.delete(item)
        
        # Si hay exactamente UN móvil seleccionado, mostrar sus materiales
        if len(self.moviles_seleccionados) == 1:
            movil = self.moviles_seleccionados[0]
            
            # Importar funciones
            from database import obtener_asignacion_movil_activa, obtener_consumos_pendientes
            from collections import defaultdict
            
            # 1. Obtener materiales asignados
            materiales = obtener_asignacion_movil_activa(movil)
            
            # 2. Obtener consumos reportados del día (fecha de filtro)
            fecha_inicio = self.fecha_inicio.get().strip()
            fecha_fin = self.fecha_fin.get().strip()
            consumos = obtener_consumos_pendientes(fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
            
            # 3. Calcular total consumido por SKU para este móvil
            consumo_por_sku = defaultdict(int)
            for c in consumos:
                # c = (id, movil, sku, nombre, cantidad, tecnico, ticket, fecha, colilla, contrato, ayudante)
                movil_consumo = str(c[1]).strip().upper()
                if movil_consumo == movil.strip().upper():
                    sku = c[2]
                    cantidad = c[4]
                    consumo_por_sku[sku] += cantidad
            
            # 4. Calcular stock físico esperado (Asignado - Consumido)
            stock_fisico = []
            for sku, nombre, cantidad_asignada in materiales:
                consumido = consumo_por_sku.get(sku, 0)
                stock_esperado = cantidad_asignada - consumido
                stock_fisico.append((sku, nombre, cantidad_asignada, consumido, stock_esperado))
            
            if stock_fisico:
                # Mostrar con columnas que incluyan el descuento
                # Primero, actualizar las columnas de la tabla
                for col in self.tabla_fisica['columns']:
                    self.tabla_fisica.heading(col, text='')
                
                self.tabla_fisica.configure(columns=('Producto', 'SKU', 'Asignado', 'Consumido', 'Stock Físico'))
                
                self.tabla_fisica.heading('Producto', text='PRODUCTO')
                self.tabla_fisica.heading('SKU', text='SKU')
                self.tabla_fisica.heading('Asignado', text='ASIGNADO')
                self.tabla_fisica.heading('Consumido', text='CONSUMIDO HOY')
                self.tabla_fisica.heading('Stock Físico', text='STOCK FÍSICO')
                
                self.tabla_fisica.column('Producto', width=200)
                self.tabla_fisica.column('SKU', width=100, anchor='center')
                self.tabla_fisica.column('Asignado', width=100, anchor='center')
                self.tabla_fisica.column('Consumido', width=120, anchor='center')
                self.tabla_fisica.column('Stock Físico', width=120, anchor='center')
                
                for sku, nombre, asignado, consumido, fisico in stock_fisico:
                    # Resaltar si hay discrepancias
                    tag = 'normal'
                    if consumido > 0:
                        tag = 'consumo' if fisico >= 0 else 'alerta'
                    
                    self.tabla_fisica.insert('', 'end', 
                                            values=(nombre, sku, asignado, consumido, fisico),
                                            tags=(tag,))
                
                # Agregar resumen
                total_asignado = sum(a for _, _, a, _, _ in stock_fisico)
                total_consumido = sum(c for _, _, _, c, _ in stock_fisico)
                total_fisico = sum(f for _, _, _, _, f in stock_fisico)
                
                self.tabla_fisica.insert('', 'end', values=('', '', '', '', ''), tags=('separator',))
                self.tabla_fisica.insert('', 'end', 
                                        values=(f'TOTALES ({len(stock_fisico)} productos)', '', 
                                               total_asignado, total_consumido, total_fisico),
                                        tags=('total',))
                
                # Configurar tags
                self.tabla_fisica.tag_configure('total', background='#E3F2FD', font=('Segoe UI', 9, 'bold'))
                self.tabla_fisica.tag_configure('separator', background='#f0f0f0')
                self.tabla_fisica.tag_configure('consumo', background='#FFF9C4')  # Amarillo si hay consumo
                self.tabla_fisica.tag_configure('alerta', background='#FFCDD2')  # Rojo si stock negativo
                self.tabla_fisica.tag_configure('normal', background='white')
            else:
                self.tabla_fisica.configure(columns=('Producto', 'SKU', 'Cantidad'))
                self.tabla_fisica.heading('Producto', text='PRODUCTO')
                self.tabla_fisica.heading('SKU', text='SKU')
                self.tabla_fisica.heading('Cantidad', text='CANTIDAD')
                
                self.tabla_fisica.insert('', 'end', 
                                        values=('', f'📭 {movil} no tiene materiales asignados', ''))
        elif len(self.moviles_seleccionados) == 0:
            self.tabla_fisica.configure(columns=('Producto', 'SKU', 'Cantidad'))
            self.tabla_fisica.insert('', 'end', 
                                    values=('', 'Seleccione un móvil para ver auditoría física', ''))
        else:
            self.tabla_fisica.configure(columns=('Producto', 'SKU', 'Cantidad'))
            self.tabla_fisica.insert('', 'end', 
                                    values=('', f'⚠️ Seleccione solo UN móvil ({len(self.moviles_seleccionados)} seleccionados)', ''))

    def abrir_retorno_manual(self):
        """Abre diálogo para registrar un retorno manual desde móvil a bodega"""
        from collections import defaultdict
        from database import obtener_asignacion_movil_activa, procesar_retorno_manual
        
        ventana = tk.Toplevel(self)
        ventana.title("📥 Retorno Manual de Materiales")
        ventana.geometry("600x650")
        ventana.transient(self.main_app.master)
        ventana.grab_set()
        ventana.configure(bg='#f8f9fa')
        
        # Centrar ventana
        ventana.update_idletasks()
        x = (ventana.winfo_screenwidth() // 2) - (600 // 2)
        y = (ventana.winfo_screenheight() // 2) - (650 // 2)
        ventana.geometry(f"+{x}+{y}")
        
        # Frame superior: Información
        info_frame = tk.Frame(ventana, bg='#E3F2FD', padx=15, pady=10)
        info_frame.pack(fill='x', padx=20, pady=(20, 10))
        
        tk.Label(info_frame, text="ℹ️ RETORNO MANUAL", 
                font=('Segoe UI', 12, 'bold'), bg='#E3F2FD', fg=Styles.PRIMARY_COLOR).pack()
        tk.Label(info_frame, 
                text="Devuelve materiales desde un móvil a la bodega.\nUsado para equipos no consumidos.",
                font=('Segoe UI', 9), bg='#E3F2FD', fg='#555').pack(pady=5)
        
        # Frame formulario
        form_frame = tk.LabelFrame(ventana, text="Datos del Retorno", 
                                  font=('Segoe UI', 10, 'bold'), bg='#f8f9fa', padx=20, pady=15)
        form_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # 1. Selector de Móvil
        tk.Label(form_frame, text="Móvil:", font=('Segoe UI', 10, 'bold'), 
                bg='#f8f9fa').grid(row=0, column=0, sticky='w', pady=5)
        
        from config import CURRENT_CONTEXT
        moviles_disponibles = CURRENT_CONTEXT.get('MOVILES', obtener_nombres_moviles())
        
        movil_var = tk.StringVar()
        movil_combo = ttk.Combobox(form_frame, textvariable=movil_var, 
                                  values=moviles_disponibles, state='readonly', width=30)
        movil_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # 2. Fecha
        tk.Label(form_frame, text="Fecha:", font=('Segoe UI', 10, 'bold'), 
                bg='#f8f9fa').grid(row=1, column=0, sticky='w', pady=5)
        
        fecha_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        fecha_entry = tk.Entry(form_frame, textvariable=fecha_var, width=32)
        fecha_entry.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))

        # --- SECCIÓN DE ESCÁNER ---
        scan_frame = tk.Frame(form_frame, bg='#E8EAF6', padx=10, pady=5, relief='groove', bd=1)
        scan_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(10, 5))
        
        tk.Label(scan_frame, text="🔫 Escáner / Código de Barra:", font=('Segoe UI', 10, 'bold'), bg='#E8EAF6').pack(side='left')
        scan_entry = tk.Entry(scan_frame, font=('Segoe UI', 11))
        scan_entry.pack(side='left', fill='x', expand=True, padx=10)
        scan_entry.focus_set()
        
        # 3. Frame para materiales disponibles
        materiales_frame = tk.LabelFrame(form_frame, text="Materiales Disponibles en Móvil", 
                                        font=('Segoe UI', 9, 'bold'), bg='#f8f9fa')
        materiales_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=10)
        
        # TreeView para mostrar materiales
        cols = ('Producto', 'SKU', 'Disponible', 'Retornar')
        tree_materiales = ttk.Treeview(materiales_frame, columns=cols, show='headings', height=8)
        
        tree_materiales.heading('Producto', text='Producto')
        tree_materiales.heading('SKU', text='SKU')
        tree_materiales.heading('Disponible', text='Disponible')
        tree_materiales.heading('Retornar', text='Cantidad a Retornar')
        
        tree_materiales.column('Producto', width=200)
        tree_materiales.column('SKU', width=80, anchor='center')
        tree_materiales.column('Disponible', width=80, anchor='center')
        tree_materiales.column('Retornar', width=120, anchor='center')
        
        tree_materiales.pack(fill='both', expand=True, padx=5, pady=5)
        
        # ScrollBar
        scroll_y = ttk.Scrollbar(materiales_frame, orient='vertical', command=tree_materiales.yview)
        tree_materiales.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side='right', fill='y')
        
        # Diccionario para almacenar entries de cantidad
        entries_cantidad = {}
        
        def cargar_materiales_movil():
            """Carga los materiales asignados al móvil seleccionado"""
            # Limpiar tabla
            for item in tree_materiales.get_children():
                tree_materiales.delete(item)
            entries_cantidad.clear()
            
            movil = movil_var.get()
            if not movil:
                return
            
            materiales = obtener_asignacion_movil_activa(movil)
            
            if not materiales:
                messagebox.showinfo("Sin Materiales", 
                                  f"El móvil {movil} no tiene materiales asignados actualmente.")
                return
            
            for sku, nombre, cantidad in materiales:
                item_id = tree_materiales.insert('', 'end', 
                                               values=(nombre, sku, cantidad, '0'))
                entries_cantidad[item_id] = {'sku': sku, 'nombre': nombre, 'max': cantidad}
            
            # Limpiar y enfocar escáner al cargar móvil
            scan_entry.delete(0, tk.END)
            scan_entry.focus_set()

        # Lógica de Escaneo
        def procesar_scan(event=None):
            codigo = scan_entry.get().strip().upper()
            if not codigo: return

            found = False
            
            # 1. Buscar como SKU directo O Código de Barra asociado
            from database import obtener_info_serial, obtener_sku_por_codigo_barra
            
            sku_objetivo = codigo
            # Intentar resolver barcode a SKU
            sku_barcode = obtener_sku_por_codigo_barra(codigo)
            if sku_barcode:
                sku_objetivo = sku_barcode

            for item_id in tree_materiales.get_children():
                vals = tree_materiales.item(item_id, 'values')
                sku_row = str(vals[1]).upper()
                
                # Check match with scanned code OR resolved SKU
                if sku_row == sku_objetivo:
                    # Encontrado SKU -> Preguntar cantidad
                    from tkinter import simpledialog
                    p_nombre = vals[0]
                    p_max = int(vals[2])
                    
                    cant = simpledialog.askinteger("Input Escáner", 
                                                 f"Producto: {p_nombre}\nSKU: {codigo}\n\nIngrese cantidad a retornar:",
                                                 parent=ventana,
                                                 minvalue=1, maxvalue=p_max)
                    if cant:
                        nuevos_vals = list(vals)
                        nuevos_vals[3] = str(cant)
                        tree_materiales.item(item_id, values=nuevos_vals)
                        tree_materiales.tag_configure('returning', background='#e8f5e9')
                        tree_materiales.item(item_id, tags=('returning',))
                        scan_entry.delete(0, tk.END)
                    return # Terminar si encontró SKU

            # 2. Buscar como Serial (Producto Seriado)
            # Primero consultar DB para ver a qué SKU pertenece el serial
            # 2. Buscar como Serial (Producto Seriado)
            # Primero consultar DB para ver a qué SKU pertenece el serial
            sku_serial, _ = obtener_info_serial(codigo)
            
            if sku_serial:
                # Buscar ese SKU en la tabla
                 for item_id in tree_materiales.get_children():
                    vals = tree_materiales.item(item_id, 'values')
                    sku_row = str(vals[1])
                    
                    if str(sku_serial) == sku_row:
                        # Encontrado SKU del serial -> Sumar 1
                        current_return = int(vals[3])
                        max_qty = int(vals[2])
                        
                        if current_return < max_qty:
                            nuevos_vals = list(vals)
                            nuevos_vals[3] = str(current_return + 1)
                            tree_materiales.item(item_id, values=nuevos_vals)
                            tree_materiales.tag_configure('returning', background='#e8f5e9')
                            tree_materiales.item(item_id, tags=('returning',))
                            
                            # Feedback visual rápido (opcional, o solo limpiar)
                            scan_entry.delete(0, tk.END)
                            found = True
                            return
                        else:
                            messagebox.showwarning("Límite Alcanzado", 
                                                 f"Ya se están retornando todas las unidades de {vals[0]}", parent=ventana)
                            scan_entry.delete(0, tk.END)
                            return

            if not found:
                messagebox.showerror("No Encontrado", 
                                   f"El código '{codigo}' no coincide con SKU ni serial de productos asignados a este móvil.", 
                                   parent=ventana)
                scan_entry.select_range(0, tk.END)
        
        scan_entry.bind('<Return>', procesar_scan)

        # Bind de selección de móvil
        movil_combo.bind('<<ComboboxSelected>>', lambda e: cargar_materiales_movil())
        
        # Variable para controlar edición activa
        self.active_editor = None
        self.active_save_callback = None

        def on_double_click(event):
            item = tree_materiales.identify_row(event.y)
            column = tree_materiales.identify_column(event.x)
            
            if not item or column != '#4': # Solo columna 'Cantidad a Retornar' (index 3, id #4)
                return
                
            # Si ya hay un editor activo, guardarlo
            if self.active_editor and self.active_editor.winfo_exists():
                if self.active_save_callback:
                    self.active_save_callback()

            # Obtener posición y valores
            bbox = tree_materiales.bbox(item, column)
            if not bbox: return
            
            valores = tree_materiales.item(item, 'values')
            valor_actual = valores[3]
            
            # Crear entry
            entry_edit = tk.Entry(tree_materiales, width=10, justify='center')
            entry_edit.place(x=bbox[0], y=bbox[1], w=bbox[2], h=bbox[3])
            entry_edit.insert(0, valor_actual)
            entry_edit.select_range(0, tk.END)
            entry_edit.focus_set()
            
            self.active_editor = entry_edit # Guardar referencia
            
            def guardar_valor(event=None):
                try:
                    if not entry_edit.winfo_exists(): return
                    
                    nuevo_valor_str = entry_edit.get().strip()
                    if not nuevo_valor_str:
                        entry_edit.destroy()
                        self.active_editor = None
                        return
                        
                    nuevo_valor = int(nuevo_valor_str)
                    
                    # Validar contra cantidad asignada
                    cantidad_asignada = int(valores[2])
                    if nuevo_valor < 0:
                        nuevo_valor = 0
                    if nuevo_valor > cantidad_asignada:
                        messagebox.showwarning("Valor Inválido", 
                                             f"La cantidad a retornar ({nuevo_valor}) no puede ser mayor que lo asignado ({cantidad_asignada}).")
                        nuevo_valor = cantidad_asignada
                        
                    # Actualizar valos en el treeview
                    nuevos_valores = list(valores)
                    nuevos_valores[3] = str(nuevo_valor)
                    tree_materiales.item(item, values=nuevos_valores)
                    
                    # Colorear fila si se va a retornar algo
                    if nuevo_valor > 0:
                        tree_materiales.tag_configure('returning', background='#e8f5e9') # Verde claro
                        tree_materiales.item(item, tags=('returning',))
                    else:
                        tree_materiales.item(item, tags=())

                except ValueError:
                    messagebox.showerror("Error", "Debe ingresar un número entero válido.")
                finally:
                    if entry_edit.winfo_exists():
                        entry_edit.destroy()
                    self.active_editor = None
                    self.active_save_callback = None
            
            self.active_save_callback = guardar_valor
            
            entry_edit.bind('<Return>', guardar_valor)
            entry_edit.bind('<FocusOut>', lambda e: guardar_valor()) # Lambda helps avoid event arg issues sometimes
            entry_edit.bind('<Escape>', lambda e: entry_edit.destroy())
        
        tree_materiales.bind('<Double-1>', on_double_click)
        
        # 4. Observaciones
        tk.Label(form_frame, text="Observaciones:", font=('Segoe UI', 10, 'bold'), 
                bg='#f8f9fa').grid(row=3, column=0, sticky='nw', pady=5)
        
        obs_text = tk.Text(form_frame, height=3, width=32, font=('Segoe UI', 9))
        obs_text.grid(row=3, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        form_frame.columnconfigure(1, weight=1)
        
        # Botones de acción
        btn_frame = tk.Frame(ventana, bg='#f8f9fa')
        btn_frame.pack(fill='x', padx=20, pady=20)
        
        def procesar_retornos():
            """Procesa todos los retornos marcados"""
            # Guardar cualquier edición activa explícitamente
            if self.active_editor and self.active_editor.winfo_exists() and self.active_save_callback:
                self.active_save_callback()
                # Pequeña pausa para permitir que la UI se actualice
                self.master.update_idletasks() 
            
            movil = movil_var.get()
            fecha = fecha_var.get()
            obs = obs_text.get('1.0', tk.END).strip()
            
            if not movil:
                messagebox.showerror("Error", "Debe seleccionar un móvil")
                return
            
            if not fecha:
                messagebox.showerror("Error", "Debe ingresar una fecha")
                return
            
            # Recopilar items a retornar
            retornos = []
            for item in tree_materiales.get_children():
                valores = tree_materiales.item(item, 'values')
                cantidad_retornar = int(valores[3])
                
                if cantidad_retornar > 0:
                    sku = entries_cantidad[item]['sku']
                    nombre = entries_cantidad[item]['nombre']
                    retornos.append((sku, nombre, cantidad_retornar))
            
            if not retornos:
                messagebox.showwarning("Sin Retornos", 
                                     "Debe especificar al menos un material a retornar.\n\n"
                                     "Doble click en la columna 'Cantidad a Retornar' para editar")
                return
            
            # Confirmar
            total_items = sum(r[2] for r in retornos)
            if not messagebox.askyesno("Confirmar Retornos",
                                       f"¿Confirma retornar {total_items} unidades de {len(retornos)} productos\n"
                                       f"desde {movil} a BODEGA?"):
                return
            
            # Procesar retornos
            exitos = 0
            errores = 0
            errores_detalle = []
            
            for sku, nombre, cantidad in retornos:
                exito, mensaje = procesar_retorno_manual(movil, sku, cantidad, fecha, obs)
                
                if exito:
                    exitos += cantidad
                else:
                    errores += cantidad
                    errores_detalle.append(f"{nombre}: {mensaje}")
            
            # Mostrar resultado
            if errores == 0:
                mostrar_mensaje_emergente(self.main_app.master, "Retornos Completados",
                                         f"Se retornaron {exitos} unidades exitosamente a BODEGA.",
                                         "success")
                ventana.destroy()
                self.cargar_datos_pendientes()
                if hasattr(self.main_app, 'dashboard_tab'):
                    self.main_app.dashboard_tab.actualizar_metricas()
            else:
                msg = f"Éxitos: {exitos} | Errores: {errores}\n\nDetalles:\n"
                msg += "\n".join(errores_detalle[:3])
                if len(errores_detalle) > 3:
                    msg += f"\n... y {len(errores_detalle) - 3} más"
                mostrar_mensaje_emergente(ventana, "Proceso Completado con Errores", msg, "warning")
        
        tk.Button(btn_frame, text="✅ Procesar Retornos", command=procesar_retornos,
                 bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                 relief='flat', padx=30, pady=10).pack(side='right')
        
        tk.Button(btn_frame, text="❌ Cancelar", command=ventana.destroy,
                 bg='#9E9E9E', fg='white', font=('Segoe UI', 10),
                 relief='flat', padx=20, pady=8).pack(side='right', padx=10)


    


    def mostrar_detalle_series(self, event):
        """Muestra las series (MACs) asignadas al producto seleccionado"""
        item = self.tabla_fisica.identify_row(event.y)
        if not item: return
        
        vals = self.tabla_fisica.item(item, 'values')
        if not vals or len(vals) < 2: return
        
        # Validar si es una fila de datos (no separador o mensaje)
        tags = self.tabla_fisica.item(item, 'tags')
        if 'separator' in tags or 'total' in tags: return
        
        nombre = vals[0]
        sku = vals[1]
        
        # Obtener móvil seleccionado (asumiendo uno solo seleccionado para ver esta tabla)
        if len(self.moviles_seleccionados) != 1:
            return
            
        movil = self.moviles_seleccionados[0]
        
        # Consultar series
        series = obtener_series_por_sku_y_ubicacion(sku, movil)
        
        if not series:
            messagebox.showinfo("Sin Series", f"No se encontraron series registradas para {sku} en {movil}.")
            return
            
        # Mostrar Popup
        popup = tk.Toplevel(self)
        popup.title(f"Series de {sku}")
        popup.geometry("400x400")
        popup.transient(self)
        popup.grab_set()
        
        tk.Label(popup, text=f"Series Asignadas: {len(series)}", font=('Segoe UI', 10, 'bold')).pack(pady=10)
        tk.Label(popup, text=f"{nombre}", font=('Segoe UI', 9)).pack(pady=0)
        
        # Listbox con scroll
        frame_list = tk.Frame(popup)
        frame_list.pack(fill='both', expand=True, padx=10, pady=10)
        
        listbox = tk.Listbox(frame_list, font=('Consolas', 10))
        scroll = tk.Scrollbar(frame_list, orient='vertical', command=listbox.yview)
        listbox.config(yscrollcommand=scroll.set)
        
        scroll.pack(side='right', fill='y')
        listbox.pack(side='left', fill='both', expand=True)
        
        for s in series:
            listbox.insert('end', s)
            
        tk.Button(popup, text="Cerrar", command=popup.destroy).pack(pady=10)
