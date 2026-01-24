import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from database import obtener_stock_actual_y_moviles, exportar_a_csv
from .utils import mostrar_mensaje_emergente
import pandas as pd
import difflib
from tkinter import filedialog
from config import PRODUCTOS_INICIALES

class CuadreContableMasivo:
    def __init__(self, parent):
        self.parent = parent
        self.datos_cuadre = {}
        self.create_complete_widgets()
        
    def create_complete_widgets(self):
        """Crea los widgets completos para el cuadre contable masivo"""
        main_frame = tk.Frame(self.parent, bg='#f8f9fa')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header moderno
        header_frame = tk.Frame(main_frame, bg='#f39c12', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="💰 CUADRE CONTABLE MASIVO", 
                font=('Segoe UI', 16, 'bold'), bg='#f39c12', fg='white').pack(pady=20)
        
        # Frame de controles
        controls_frame = tk.Frame(main_frame, bg='#FFF3E0', padx=15, pady=15)
        controls_frame.pack(fill='x')
        
        # Fecha de cuadre
        tk.Label(controls_frame, text="Fecha de Cuadre:", font=('Segoe UI', 10, 'bold'), bg='#FFF3E0').pack(side=tk.LEFT)
        self.fecha_cuadre = tk.Entry(controls_frame, width=15, font=('Segoe UI', 10))
        self.fecha_cuadre.insert(0, date.today().isoformat())
        self.fecha_cuadre.pack(side=tk.LEFT, padx=10)
        
        # Botones de acción
        btn_frame = tk.Frame(controls_frame, bg='#FFF3E0')
        btn_frame.pack(side=tk.RIGHT)
        
        tk.Button(btn_frame, text="🔄 Cargar Datos Sistema", 
                 command=self.cargar_datos_sistema,
                 bg='#3498db', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=15, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="🧮 Calcular Todo", 
                 command=self.calcular_todo,
                 bg='#27ae60', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=15, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="📤 Generar Reporte", 
                 command=self.generar_reporte,
                 bg='#f39c12', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=15, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="🧹 Limpiar", 
                 command=self.limpiar_datos,
                 bg='#e74c3c', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=15, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="📥 Cargar Consumo Excel", 
                 command=self.cargar_consumo_excel,
                 bg='#8e44ad', fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=15, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        # Frame de la tabla
        table_frame = tk.Frame(main_frame)
        table_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Crear tabla con scrollbars
        self.crear_tabla_cuadre(table_frame)
        
        # Frame de totales
        totales_frame = tk.Frame(main_frame, bg='#E8F5E8', padx=15, pady=10)
        totales_frame.pack(fill='x', pady=(10, 0))
        
        tk.Label(totales_frame, text="TOTALES:", font=('Segoe UI', 12, 'bold'), bg='#E8F5E8').pack(side=tk.LEFT)
        self.totales_label = tk.Label(totales_frame, text="INICIAL: 0 | ABASTOS: 0 | MÓVILES: 0 | DEBERÍA: 0 | FÍSICO: 0 | CONSUMIDO: 0 | REALMENTE: 0 | DIFERENCIA: 0", 
                                     font=('Segoe UI', 10), bg='#E8F5E8')
        self.totales_label.pack(side=tk.LEFT, padx=20)
        
    def crear_tabla_cuadre(self, parent):
        """Crea la tabla editable para el cuadre contable"""
        # Frame para tabla y scrollbars
        table_container = tk.Frame(parent)
        table_container.pack(fill='both', expand=True)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(table_container, orient="vertical")
        h_scrollbar = ttk.Scrollbar(table_container, orient="horizontal")
        
        # Crear Treeview
        columns = ("SKU", "Producto", "INICIAL", "ABASTOS", "MÓVILES", "DEBERÍA", "FÍSICO", "CONSUMIDO", "REALMENTE", "DIFERENCIA")
        self.tabla_cuadre = ttk.Treeview(table_container, columns=columns, show='headings', 
                                        yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set,
                                        height=20)
        
        # Configurar scrollbars
        v_scrollbar.config(command=self.tabla_cuadre.yview)
        h_scrollbar.config(command=self.tabla_cuadre.xview)
        
        # Configurar columnas
        column_widths = {
            "SKU": 100, "Producto": 300, "INICIAL": 80, "ABASTOS": 80, 
            "MÓVILES": 80, "DEBERÍA": 80, "FÍSICO": 80, "CONSUMIDO": 80, 
            "REALMENTE": 80, "DIFERENCIA": 80
        }
        
        for col in columns:
            self.tabla_cuadre.heading(col, text=col)
            self.tabla_cuadre.column(col, width=column_widths.get(col, 100), anchor='center')
        
        # Grid layout
        self.tabla_cuadre.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)
        
        # Configurar colores para diferencias
        self.tabla_cuadre.tag_configure('verde', background='#E8F5E8')
        self.tabla_cuadre.tag_configure('amarillo', background='#FFF3E0')
        self.tabla_cuadre.tag_configure('rojo', background='#FFEBEE')
        
        # Bind events para edición
        self.tabla_cuadre.bind('<Double-1>', self.on_double_click_cuadre)

    def on_double_click_cuadre(self, event):
        """Maneja el doble clic para editar celdas"""
        region = self.tabla_cuadre.identify_region(event.x, event.y)
        if region != "cell":
            return
            
        column = self.tabla_cuadre.identify_column(event.x)
        row = self.tabla_cuadre.identify_row(event.y)
        
        # Solo permitir editar columnas editables
        editable_columns = {"INICIAL", "ABASTOS", "FÍSICO", "CONSUMIDO"}
        column_name = self.tabla_cuadre.heading(column)["text"]
        
        if column_name not in editable_columns:
            return
            
        self.editar_celda_cuadre(row, column)

    def editar_celda_cuadre(self, row, column):
        """Crea un entry para editar una celda"""
        # Obtener el valor actual
        item = self.tabla_cuadre.item(row)
        values = item['values']
        col_index = int(column.replace('#', '')) - 1
        
        # Crear entry
        x, y, width, height = self.tabla_cuadre.bbox(row, column)
        
        entry = tk.Entry(self.tabla_cuadre, font=('Segoe UI', 9))
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, str(values[col_index]))
        entry.select_range(0, tk.END)
        entry.focus()
        
        def on_enter(event):
            nuevo_valor = entry.get().strip()
            try:
                if nuevo_valor:  # Permitir vacío
                    int(nuevo_valor)  # Validar que sea número
                actualizar_valor(nuevo_valor)
            except ValueError:
                entry.config(bg='#FFEBEE')  # Rojo claro para error
                return "break"
        
        def actualizar_valor(nuevo_valor):
            # Actualizar valores
            values[col_index] = nuevo_valor if nuevo_valor else "0"
            self.tabla_cuadre.item(row, values=values)
            
            # Recalcular
            self.recalcular_fila(row)
            entry.destroy()
        
        def on_focus_out(event):
            actualizar_valor(entry.get().strip())
        
        entry.bind('<Return>', on_enter)
        entry.bind('<FocusOut>', on_focus_out)
        entry.bind('<Escape>', lambda e: entry.destroy())

    def recalcular_fila(self, row):
        """Recalcula los valores de una fila"""
        item = self.tabla_cuadre.item(row)
        values = item['values']
        
        try:
            # Obtener valores numéricos
            inicial = int(values[2] or 0)
            abastos = int(values[3] or 0)
            moviles = int(values[4] or 0)
            fisico = int(values[6] or 0)
            consumido = int(values[7] or 0)
            
            # Calcular
            deberia = inicial + abastos + moviles
            realmente = fisico + consumido
            diferencia = realmente - deberia
            
            # Actualizar valores calculados
            values[5] = str(deberia)
            values[8] = str(realmente)
            values[9] = str(diferencia)
            
            # Actualizar color según diferencia
            tags = ()
            if abs(diferencia) <= 2:
                tags = ('verde',)
            elif abs(diferencia) <= 10:
                tags = ('amarillo',)
            else:
                tags = ('rojo',)
            
            self.tabla_cuadre.item(row, values=values, tags=tags)
            
        except ValueError:
            # En caso de error en los cálculos
            pass

    def cargar_datos_sistema(self):
        """Carga los datos del sistema para el cuadre contable"""
        fecha = self.fecha_cuadre.get().strip()
        if not fecha:
            mostrar_mensaje_emergente(self.parent, "Error", "Debe ingresar una fecha válida.", "error")
            return
        
        # Obtener datos del sistema
        datos_inventario = obtener_stock_actual_y_moviles()
        
        if not datos_inventario:
            mostrar_mensaje_emergente(self.parent, "Información", "No hay datos de inventario para cargar.", "info")
            return
        
        # Limpiar tabla
        for item in self.tabla_cuadre.get_children():
            self.tabla_cuadre.delete(item)
        
        # Llenar tabla
        for nombre, sku, bodega, moviles, total, consumo, abasto in datos_inventario:
            # Usar datos del sistema como valores iniciales
            inicial = bodega + moviles  # Stock actual como inicial
            deberia = inicial + abasto + moviles
            realmente = bodega + consumo
            diferencia = realmente - deberia
            
            # Determinar color
            tags = ()
            if abs(diferencia) <= 2:
                tags = ('verde',)
            elif abs(diferencia) <= 10:
                tags = ('amarillo',)
            else:
                tags = ('rojo',)
            
            self.tabla_cuadre.insert('', tk.END, values=(
                sku, 
                nombre,
                str(inicial), # INICIAL
                str(abasto),  # ABASTOS
                str(moviles), # MÓVILES
                str(deberia), # DEBERÍA
                str(bodega),  # FÍSICO (asumimos bodega actual como físico inicial)
                str(consumo), # CONSUMIDO
                str(realmente), # REALMENTE
                str(diferencia) # DIFERENCIA
            ), tags=tags)
            
        self.calcular_totales_generales()
        self.mostrar_mensaje_emergente("Éxito", "Datos cargados correctamente.", "info")

    def mostrar_mensaje_emergente(self, title, msg, type_):
         mostrar_mensaje_emergente(self.parent, title, msg, type_)

    def calcular_todo(self):
        """Recalcula todas las filas y totales"""
        for item in self.tabla_cuadre.get_children():
            self.recalcular_fila(item)
        self.calcular_totales_generales()
        mostrar_mensaje_emergente(self.parent, "Éxito", "Cálculos actualizados.", "info")

    def calcular_totales_generales(self):
        """Calcula los totales de todas las columnas"""
        totales = {
            'inicial': 0, 'abastos': 0, 'moviles': 0, 
            'deberia': 0, 'fisico': 0, 'consumido': 0, 
            'realmente': 0, 'diferencia': 0
        }
        
        for item in self.tabla_cuadre.get_children():
            values = self.tabla_cuadre.item(item)['values']
            try:
                totales['inicial'] += int(values[2] or 0)
                totales['abastos'] += int(values[3] or 0)
                totales['moviles'] += int(values[4] or 0)
                totales['deberia'] += int(values[5] or 0)
                totales['fisico'] += int(values[6] or 0)
                totales['consumido'] += int(values[7] or 0)
                totales['realmente'] += int(values[8] or 0)
                totales['diferencia'] += int(values[9] or 0)
            except ValueError:
                pass
                
        self.totales_label.config(text=f"INICIAL: {totales['inicial']} | ABASTOS: {totales['abastos']} | "
                                     f"MÓVILES: {totales['moviles']} | DEBERÍA: {totales['deberia']} | "
                                     f"FÍSICO: {totales['fisico']} | CONSUMIDO: {totales['consumido']} | "
                                     f"REALMENTE: {totales['realmente']} | DIFERENCIA: {totales['diferencia']}")

    def generar_reporte(self):
        """Genera reporte del cuadre contable"""
        datos = []
        for row in self.tabla_cuadre.get_children():
            datos.append(self.tabla_cuadre.item(row)['values'])
        
        encabezados = ["SKU", "Producto", "INICIAL", "ABASTOS", "MÓVILES", "DEBERÍA", "FÍSICO", "CONSUMIDO", "REALMENTE", "DIFERENCIA"]
        
        fecha = self.fecha_cuadre.get().strip()
        nombre_default = f"cuadre_contable_{fecha}.csv"
        
        filename = filedialog.asksaveasfilename(
            parent=self.parent,
            title="Guardar Reporte de Cuadre",
            initialfile=nombre_default,
            defaultextension=".csv",
            filetypes=[("Archivo CSV", "*.csv")]
        )
        
        if not filename:
            return
            
        exito, mensaje = exportar_a_csv(encabezados, datos, filename)
        mostrar_mensaje_emergente(self.parent, "Exportación", mensaje, "success" if exito else "error")

    def limpiar_datos(self):
        """Limpia la tabla"""
        if messagebox.askyesno("Confirmar", "¿Está seguro de limpiar todos los datos?"):
            for item in self.tabla_cuadre.get_children():
                self.tabla_cuadre.delete(item)
            self.calcular_totales_generales()


    def cargar_consumo_excel(self):
        """Carga consumo desde Excel y actualiza la columna CONSUMIDO"""
        filename = filedialog.askopenfilename(
            parent=self.parent,
            title="Seleccionar Archivo de Consumo",
            filetypes=[("Excel Files", "*.xlsx;*.xls")]
        )
        
        if not filename:
            return
            
        try:
            df = pd.read_excel(filename)
            
            # Detectar formato (Lógica adaptada de ReconciliationWindow)
            df_procesado = self._detectar_y_procesar_excel(df)
            
            if df_procesado.empty:
                mostrar_mensaje_emergente(self.parent, "Atención", "No se encontraron datos de consumo válidos en el archivo.", "warning")
                return
                
            # Agrupar por SKU
            consumo_por_sku = df_procesado.groupby('sku')['cantidad'].sum().to_dict()
            
            # Actualizar tabla
            items_updated = 0
            for item in self.tabla_cuadre.get_children():
                values = self.tabla_cuadre.item(item)['values']
                sku = str(values[0])
                
                if sku in consumo_por_sku:
                    nuevo_consumo = int(consumo_por_sku[sku])
                    values[7] = str(nuevo_consumo) # Columna CONSUMIDO (index 7)
                    self.tabla_cuadre.item(item, values=values)
                    self.recalcular_fila(item)
                    items_updated += 1
            
            self.calcular_totales_generales()
            mostrar_mensaje_emergente(self.parent, "Éxito", f"Se actualizó el consumo de {items_updated} productos desde el Excel.", "success")
            
        except Exception as e:
            mostrar_mensaje_emergente(self.parent, "Error", f"Error procesando archivo: {str(e)}", "error")

    def _detectar_y_procesar_excel(self, df):
        """Procesa el Excel intentando detectar formato largo o ancho"""
        # 1. Limpieza preliminar de columnas
        df.columns = [str(c).strip() for c in df.columns]
        df_cols_lower = [str(c).lower().strip() for c in df.columns]
        
        # 2. Mapeo de columnas clave
        col_map = {}
        for col in df.columns:
            cl = str(col).lower().strip()
            if cl in ['sku', 'codigo', 'cod', 'item', 'material']: col_map['sku'] = col
            elif cl in ['cantidad', 'qty', 'cant', 'consumo', 'usado']: col_map['cantidad'] = col
            
        # A) Formato Largo (tiene columna SKU y CANTIDAD explícitas)
        if 'sku' in col_map and 'cantidad' in col_map:
            data = df[[col_map['sku'], col_map['cantidad']]].copy()
            data.columns = ['sku', 'cantidad']
            return self._limpiar_tipos(data)
            
        # B) Formato Ancho (Columnas son nombres de productos)
        # Detectar columnas de productos usando Fuzzy Match con PRODUCTOS_INICIALES
        mapa_sku_columna = {}
        
        # Mapa de referencia para búsqueda
        mapa_sistema_nombres = {n.lower().strip(): sku for n, sku, _ in PRODUCTOS_INICIALES}
        
        for col in df.columns:
            cl = str(col).lower().strip()
            # Ignorar columnas comunes de metadatos si las hubiera
            if cl in ['fecha', 'date', 'movil', 'técnico', 'patente', 'nombre']: continue
            
            # Limpieza para matching
            cl_clean = cl.replace('.', ' ').replace('-', ' ').replace('"', '').replace("'", "").replace('[', '').replace(']', '').replace('(', '').replace(')', '').strip()
            
            best_match_sku = None
            best_ratio = 0
            
            for sn, ss in mapa_sistema_nombres.items():
                sn_clean = sn.replace('.', ' ').replace('-', ' ').replace('"', '').replace("'", "").replace('[', '').replace(']', '').replace('(', '').replace(')', '').strip()
                
                # Check Substring
                if (len(sn_clean) > 2 and len(cl_clean) > 2) and (sn_clean in cl_clean or cl_clean in sn_clean):
                    mapa_sku_columna[col] = ss
                    best_match_sku = None
                    break
                    
                # Check Fuzzy
                ratio = difflib.SequenceMatcher(None, cl_clean, sn_clean).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match_sku = ss
            
            # Aplicar fuzzy si es bueno
            if best_match_sku and col not in mapa_sku_columna and best_ratio > 0.6:
                mapa_sku_columna[col] = best_match_sku
                
        if not mapa_sku_columna:
            raise ValueError("No se detectaron columnas de productos conocidos en el Excel.")
            
        # Melt para convertir a formato largo
        # Asumimos que si no es formato largo, es una tabla donde cada fila es una transaccion y las cols son productos
        # Ojo: Si hay multiples filas, sumaremos todo.
        
        df_melt = df.melt(value_vars=list(mapa_sku_columna.keys()), var_name='original_col', value_name='cantidad')
        df_melt['sku'] = df_melt['original_col'].map(mapa_sku_columna)
        
        return self._limpiar_tipos(df_melt[['sku', 'cantidad']])

    def _limpiar_tipos(self, data):
        data = data.copy()
        def cq(x):
            if str(x).lower().strip() in ['no', 'nan', '', 'none']: return 0
            try: return int(float(x))
            except: return 0
        data['cantidad'] = data['cantidad'].apply(cq)
        data['sku'] = data['sku'].astype(str).str.strip()
        data = data[data['cantidad'] > 0] # Solo consumos positivos
        return data
