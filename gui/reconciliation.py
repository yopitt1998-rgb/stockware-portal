import tkinter as tk
import os
from tkinter import ttk, messagebox, filedialog
import pandas as pd
# Suppress FutureWarning for clear logs
pd.set_option('future.no_silent_downcasting', True)
from datetime import datetime, timedelta
from tkcalendar import DateEntry
from database import obtener_movimientos_por_rango, obtener_asignacion_movil, registrar_movimiento_gui
from config import PRODUCTOS_INICIALES
import sqlite3 
import difflib
from config import DATABASE_NAME 

class ReconciliationWindow:
    def __init__(self, master_app, mode='excel'):
        self.master_app = master_app
        self.mode = mode # 'excel' or 'manual'
        
        self.top = tk.Toplevel(master_app.master)
        title = "Conciliación de Consumo (Excel vs Sistema)" if mode == 'excel' else "Consulta de Inventario Móvil (Conciliación Manual)"
        self.top.title(title)
        self.top.geometry("1100x700")
        
        # UI Tweak: Maximize
        try:
            self.top.state('zoomed')
        except: pass
        
        # Estado
        self.current_df_excel = None
        self.col_map_cache = None
        
        # --- UI LAYOUT ---
        
        # Frame Superior: Carga de Archivo y Fechas
        frame_top = ttk.LabelFrame(self.top, text="Configuración", padding=10)
        frame_top.pack(fill='x', padx=10, pady=5)
        
        if self.mode == 'excel':
            # File Loader
            btn_load = ttk.Button(frame_top, text="📂 Cargar Excel Consumo", command=self.cargar_archivo)
            btn_load.pack(side='left', padx=5)
            
            self.lbl_file = ttk.Label(frame_top, text="Ningún archivo cargado")
            self.lbl_file.pack(side='left', padx=5)
            
            # Separator
            ttk.Separator(frame_top, orient='vertical').pack(side='left', fill='y', padx=10)
        else:
            self.lbl_file = None
        
        # Manual Mobile Selection (Now Primary Control)
        ttk.Label(frame_top, text="Seleccionar Móvil:").pack(side='left', padx=5)
        self.combo_movil_manual = ttk.Combobox(frame_top, values=self._get_lista_moviles(), width=20, state="readonly")
        self.combo_movil_manual.pack(side='left', padx=5)
        self.combo_movil_manual.bind("<<ComboboxSelected>>", self.on_movil_selected)
        
        # Date Range Selection (Visual mainly)
        if self.mode == 'excel':
             ttk.Label(frame_top, text="Rango Fecha (Visual):").pack(side='left', padx=5)
             self.date_start = DateEntry(frame_top, width=12, background='darkblue', foreground='white', borderwidth=2, date_pattern='y-mm-dd')
             self.date_start.pack(side='left', padx=2)
             ttk.Label(frame_top, text="a").pack(side='left', padx=2)
             self.date_end = DateEntry(frame_top, width=12, background='darkblue', foreground='white', borderwidth=2, date_pattern='y-mm-dd')
             self.date_end.pack(side='left', padx=2)
        
        # Recalculate Button
        btn_recalc = ttk.Button(frame_top, text="🔄 Consultar / Recalcular", command=self.recalcular_con_fechas)
        btn_recalc.pack(side='left', padx=10)

        # Process Button (New!)
        frame_action = ttk.Frame(self.top)
        frame_action.pack(fill='x', padx=10, pady=5)
        
        if self.mode == 'excel':
            self.btn_process = ttk.Button(frame_action, text="✅ PROCESAR CONSUMO", command=self.procesar_consumo_confirmado, state='disabled')
            self.btn_process.pack(side='right', padx=10)
            ttk.Label(frame_action, text="Nota: 'Procesar' descontará del inventario los ítems reportados en Excel.").pack(side='left', padx=5)
        else:
             self.btn_process = None
             ttk.Label(frame_action, text="Vista de Inventario Actual del Móvil.").pack(side='left', padx=5)
        
        # Frame Principal: Tabla de Resultados
        frame_main = ttk.Frame(self.top)
        frame_main.pack(fill='both', expand=True, padx=10, pady=5)
        
        if self.mode == 'excel':
            cols = ('Fecha', 'Movil', 'Producto', 'Sistema (Pendiente)', 'Excel (Reportado)', 'Saldo Teórico', 'Estado', 'SKU_HIDDEN')
        else:
            cols = ('Fecha', 'Movil', 'Producto', 'Sistema (Pendiente)', 'SKU_HIDDEN') # Simplified cols
            
        self.tree = ttk.Treeview(frame_main, columns=cols, show='headings')
        
        self.tree.heading('Fecha', text='Fecha', anchor='center'); self.tree.column('Fecha', width=100, anchor='center')
        self.tree.heading('Movil', text='Móvil', anchor='center'); self.tree.column('Movil', width=120, anchor='center')
        self.tree.heading('Producto', text='Producto', anchor='w'); self.tree.column('Producto', width=300, anchor='w')
        self.tree.heading('Sistema (Pendiente)', text='Asignado', anchor='center'); self.tree.column('Sistema (Pendiente)', width=100, anchor='center')
        
        if self.mode == 'excel':
            self.tree.heading('Excel (Reportado)', text='Consumo (Excel)', anchor='center'); self.tree.column('Excel (Reportado)', width=120, anchor='center')
            self.tree.heading('Saldo Teórico', text='Saldo Teórico', anchor='center'); self.tree.column('Saldo Teórico', width=100, anchor='center')
            self.tree.heading('Estado', text='Estado', anchor='center'); self.tree.column('Estado', width=150, anchor='center')
            
        self.tree.heading('SKU_HIDDEN', text=''); self.tree.column('SKU_HIDDEN', width=0, stretch=False) # Hidden ID
        
        
        # Scrollbar
        vsb = ttk.Scrollbar(frame_main, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        # Tags de colores
        # Tags de colores
        self.tree.tag_configure('match', background='#ccffcc') # Vivid Green
        self.tree.tag_configure('mismatch', background='#ffcccc') # Vivid Red
        self.tree.tag_configure('missing_system', background='#ffffcc') # Yellow/Orange (Sin Asignar)
        self.tree.tag_configure('missing_excel', background='#e6f0ff') # Blueish
        
        # Status Bar
        self.lbl_status = ttk.Label(self.top, text="Listo.", relief='sunken', anchor='w')
        self.lbl_status.pack(fill='x', side='bottom')


    def _get_lista_moviles(self):
        try:
            # DIRECT CONNECTION TO FIX EMPTY LIST
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT movil FROM asignacion_moviles ORDER BY movil")
            moviles = [r[0] for r in cursor.fetchall()]
            conn.close()
            return moviles
        except Exception as e:
            print(f"Error fetching mobiles: {e}")
            return []

    def on_movil_selected(self, event):
        """Triggered when user manually selects a mobile."""
        self.recalcular_con_fechas()

    def _force_focus(self):
        """Forces the window to the front."""
        self.top.attributes('-topmost', True)
        self.top.update()
        self.top.attributes('-topmost', False)
        self.top.lift()
        self.top.focus_force()

    def cargar_archivo(self):
        filename = filedialog.askopenfilename(
            parent=self.top,
            filetypes=[("Excel Files", "*.xlsx;*.xls")]
        )
        
        # Fix Focus: Force window to top after dialog closes
        self.top.after(100, lambda: self._force_focus())
        
        if not filename:
            return
            
        self.lbl_file.config(text=f"Cargando: {os.path.basename(filename)} ...")
        self.top.update()
        
        try:
            df = pd.read_excel(filename)
            col_map = self._mapear_columnas(df)
            
            self.current_df_excel = df
            self.col_map_cache = col_map
            self.lbl_file.config(text=f"Archivo: {filename}")
            
            # self.procesar_datos(df, col_map, auto_set_dates=True)
            self.lbl_status.config(text="Archivo cargado. Por favor, seleccione un Móvil para ver la conciliación.")
            messagebox.showinfo("Archivo Cargado", "El archivo se ha cargado correctamente.\n\nPor favor, seleccione un MÓVIL del desplegable para realizar la comparación.", parent=self.top)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error leyendo archivo: {e}", parent=self.top)
            self.lbl_file.config(text="Error de carga")

    def recalcular_con_fechas(self):
        """Re-runs processing. Handles case where no Excel is loaded (System Inspection)."""
        movil_manual = self.combo_movil_manual.get()
        if not movil_manual: movil_manual = None
        
        if self.current_df_excel is not None:
             self.procesar_datos(self.current_df_excel, self.col_map_cache, movil_manual=movil_manual, auto_set_dates=False)
        elif movil_manual:
             # System Inspection Mode (No Excel)
             self.procesar_datos(None, None, movil_manual=movil_manual, auto_set_dates=False)
        else:
             # No mobile, no file
             pass

    def _mapear_columnas(self, df):
        keywords = {
            'fecha': ['fecha', 'date', 'dia', 'time'],
            'movil': ['movil', 'patente', 'camion', 'resource', 'técnico'],
            'sku': ['sku', 'codigo', 'cod', 'item', 'material'],
            'cantidad': ['cantidad', 'qty', 'cant', 'consumo', 'usado']
        }
        found_map = {}
        for key, possible_names in keywords.items():
            for col in df.columns:
                if str(col).lower().strip() in possible_names:
                    found_map[key] = col
                    break
        return found_map

    def procesar_datos(self, df, col_map, movil_manual=None, auto_set_dates=True):
        # Clear table
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        if self.btn_process:
            self.btn_process.config(state='disabled') # Disable until valid results
        
        final_df = pd.DataFrame()
        
        # --- SCENARIO A: System Inspection Only (No Excel) ---
        if df is None and movil_manual:
             print(f"DEBUG: System Inspection for {movil_manual}")
             # Fetch system data
             try:
                asignacion = obtener_asignacion_movil(movil_manual)
                data_rows = []
                for nombre, sku, cantidad in asignacion:
                    data_rows.append({
                        'fecha': 'HOY',
                        'movil': movil_manual,
                        'sku': sku,
                        'cantidad_sistema': cantidad,
                        'cantidad_excel': 0 # No report
                    })
                final_df = pd.DataFrame(data_rows)
                
                # If everything is 0/Empty
                if final_df.empty:
                     messagebox.showinfo("Info", f"El móvil {movil_manual} no tiene asignación pendiente en sistema.")
                     return

             except Exception as e:
                 print(f"Error fetching assignment: {e}")
                 return
        
        # --- SCENARIO B: Reconciliation (Excel Loaded) ---
        elif df is not None:
            df_procesado = None
            
            # 1. Try Long Format
            required_keys = ['fecha', 'movil', 'sku', 'cantidad']
            if all(k in col_map for k in required_keys):
                try:
                    data = df.rename(columns={col_map[k]: k for k in required_keys})
                    # Clean proper types
                    fecha_clean = pd.to_datetime(data['fecha'], errors='coerce')
                    data = data.assign(fecha=fecha_clean.dt.strftime('%Y-%m-%d'))
                    data = self._limpiar_tipos(data)
                    df_procesado = data
                except Exception as e:
                    print(f"Error Long Format: {e}")
            
            # 2. Try Wide Format
            if df_procesado is None:
                try:
                    df_procesado = self.detectar_y_procesar_formato(df, col_map)
                except Exception as e:
                    messagebox.showerror("Error de Formato", f"No se pudo interpretar el formato.\n{e}")
                    return

            # --- FILTERING LOGIC ---
            # If User selected a specific mobile, FILTER Excel to only show that mobile.
            if movil_manual:
                # Check if Excel actually has mobile column
                if 'movil' in df_procesado.columns:
                    unique_excels = df_procesado['movil'].unique()
                    if movil_manual in unique_excels:
                        df_procesado = df_procesado[df_procesado['movil'] == movil_manual]
                    else:
                        # Case: user wants to force this file to this mobile
                        if len(unique_excels) <= 1:
                             df_procesado = df_procesado.assign(movil=movil_manual)
                        else:
                             # Strict filter
                             df_procesado = df_procesado[df_procesado['movil'] == movil_manual]
                else:
                    # If processing succeeded but no mobile column (e.g. relaxed detection), default to manual
                    df_procesado = df_procesado.assign(movil=movil_manual)

            
            # Group Excel Data
            excel_grouped = df_procesado.groupby(['fecha', 'movil', 'sku'])['cantidad'].sum().reset_index()
            
            if excel_grouped.empty and movil_manual:
                 # If filtered result is empty
                 messagebox.showwarning("Aviso", f"El Excel no contiene registros para el móvil {movil_manual}.")
                 # Still show system data though? Let's verify system data
            
            # Identify target mobiles
            if movil_manual:
                moviles_target = [movil_manual]
            else:
                moviles_target = excel_grouped['movil'].unique()
            
            # Fetch System Data
            all_sys_data = []
            for m in moviles_target:
                asig = obtener_asignacion_movil(m)
                for nombre, sku, cant in asig:
                    all_sys_data.append({'movil': m, 'sku': sku, 'cantidad': cant})
            
            df_sys = pd.DataFrame(all_sys_data)
            if df_sys.empty: df_sys = pd.DataFrame(columns=['movil', 'sku', 'cantidad'])
            
            # Merge
            # Excel aggregation (Movil/SKU)
            excel_total = excel_grouped.groupby(['movil', 'sku'])['cantidad'].sum().reset_index()
            
            merged = pd.merge(excel_total, df_sys, on=['movil', 'sku'], how='outer', suffixes=('_excel', '_sistema')).fillna(0)
            
            # Dates
            min_d = excel_grouped['fecha'].min() if not excel_grouped.empty else "Hoy"
            merged['fecha'] = str(min_d)
            
            final_df = merged

        # --- FINAL DISPLAY ---
        if 'cantidad_sistema' not in final_df.columns: final_df['cantidad_sistema'] = 0
        if 'cantidad_excel' not in final_df.columns: final_df['cantidad_excel'] = 0
            
        final_df['cantidad_sistema'] = final_df['cantidad_sistema'].astype(int)
        final_df['cantidad_excel'] = final_df['cantidad_excel'].astype(int)
        
        from config import PRODUCTOS_INICIALES
        sku_to_name = {sku: nombre for nombre, sku, _ in PRODUCTOS_INICIALES}
        
        has_items_to_process = False
        
        for _, row in final_df.iterrows():
            fecha = row.get('fecha', 'Hoy')
            movil = row['movil']
            sku = row['sku']
            nombre = sku_to_name.get(sku, sku)
            
            c_sys = row['cantidad_sistema']
            c_exc = row['cantidad_excel']
            diff = c_sys - c_exc
            
            # Logic: Assigned - Consumed = Theoretical Balance (Saldo)
            # User Scenario: Assigned 30, Returns 15. Consumed MUST be 15.
            # If Excel says 15 Consumed: 30 - 15 = 15 Saldo. (User verifies 15 Physical). Match.
            # If Excel says 10 Consumed: 30 - 10 = 20 Saldo. (User verifies 15 Physical). 5 Missing (Faltante).
            
            saldo_teorico = c_sys - c_exc
            
            estado = "OK"
            tag = "match"
            
            if c_sys == 0 and c_exc > 0:
                estado = "Consumo sin Asig."
                tag = "missing_system" # Red flag
                saldo_teorico = -c_exc
            elif c_sys > 0 and c_exc == 0:
                estado = "Sin Consumo" # Might be valid if returned full
                tag = "missing_excel" 
            elif saldo_teorico < 0:
                estado = "Error: Saldo Neg."
                tag = "mismatch" # Critical error
            else:
                estado = f"Saldo: {saldo_teorico}"
                # If Excel Consumption is present, usually meaningful
                tag = "match"
                
            self.tree.insert('', 'end', values=(
                fecha, movil, nombre, c_sys, c_exc, saldo_teorico, estado, sku
            ), tags=(tag,))
            
            if c_exc > 0: has_items_to_process = True
            
        self.lbl_status.config(text=f"Registros: {len(final_df)}")
        
        # Enable Process Button only if there is Excel consumption to process
        if has_items_to_process and df is not None:
             if self.btn_process:
                 self.btn_process.config(state='normal')
        else:
             if self.btn_process:
                 self.btn_process.config(state='disabled')


    def procesar_consumo_confirmado(self):
        """Applies the consumption to the database."""
        items = self.tree.get_children()
        to_process = []
        
        for item in items:
            vals = self.tree.item(item)['values']
            # vals: Date, Movil, Product, Sys, Exc, Diff, State, SKU
            movil = vals[1]
            sku = vals[7] # Hidden SKU
            qty_excel = int(vals[4])
            
            if qty_excel > 0:
                to_process.append((movil, sku, qty_excel))
        
        if not to_process:
            messagebox.showinfo("Info", "No hay consumo reportado (Excel) para procesar.")
            return
            
        resp = messagebox.askyesno("Confirmar Procesamiento", 
                                   f"Se procesará el consumo de {len(to_process)} ítems.\n\n"
                                   "Esto descontará el stock de la asignación del móvil.\n"
                                   "¿Está seguro?")
        if not resp: return
        
        # Execute
        success_count = 0
        errors = []
        
        for movil, sku, qty in to_process:
            # We use registrar_movimiento_gui with 'CONSUMO_MOVIL'
            # Note: We don't have exact 'paquete' info here easily unless we fetch it or assume.
            # Consumo movil usually doesn't strictly require packet logic if we just deduct quantity, 
            # BUT database logic might check it. The refactor used generic assignment.
            # Let's try passing None for packet.
            
            ok, msg = registrar_movimiento_gui(
                sku=sku, 
                tipo_movimiento='CONSUMO_MOVIL', 
                cantidad_afectada=qty, 
                movil_afectado=movil,
                fecha_evento=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                paquete_asignado=None, 
                observaciones="Conciliación Excel Masiva"
            )
            
            if ok:
                success_count += 1
            else:
                errors.append(f"{sku}: {msg}")
                
        # Report
        summary = f"Procesados: {success_count}/{len(to_process)}"
        if errors:
            summary += "\n\nErrores:\n" + "\n".join(errors[:5])
            if len(errors) > 5: summary += "\n..."
            
        messagebox.showinfo("Resultado", summary)
        
        # Refresh
        self.recalcular_con_fechas()


    def detectar_y_procesar_formato(self, df, col_map_std):
        # ... logic identical to previous ...
        # (Included for completeness of overwrite)
        if 'sku' in col_map_std and 'cantidad' in col_map_std:
            data = df.rename(columns={
                col_map_std['fecha']: 'fecha',
                col_map_std['movil']: 'movil',
                col_map_std['sku']: 'sku',
                col_map_std['cantidad']: 'cantidad'
            })
            return self._limpiar_tipos(data)

        cols_fecha = ['fecha_cierre', 'fecha', 'date', 'closure date']
        cols_movil = ['nombre_movil', 'codigo_movil', 'movil', 'patente', 'resource']
        
        col_fecha_found = None
        col_movil_found = None
        df_cols_lower = [str(c).lower().strip() for c in df.columns]
        col_real_names = dict(zip(df_cols_lower, df.columns))
        
        for c in cols_fecha:
            if c in df_cols_lower: col_fecha_found = col_real_names[c]; break
        for c in cols_movil:
            if c in df_cols_lower: col_movil_found = col_real_names[c]; break
            
        if not col_fecha_found or not col_movil_found:
             if 'fecha' in col_map_std: col_fecha_found = df.columns[df.columns.str.lower() == col_map_std['fecha']].tolist()[0]
             if 'movil' in col_map_std: col_movil_found = df.columns[df.columns.str.lower() == col_map_std['movil']].tolist()[0]
             if not col_fecha_found or not col_movil_found: raise ValueError("Meta-data missing")

        # Detect Products
        from config import PRODUCTOS_INICIALES
        mapa_sistema_nombres = {n.lower().strip(): sku for n, sku, _ in PRODUCTOS_INICIALES}
        mapa_sku_columna = {}
        for col in df.columns:
            cl = str(col).lower().strip()
            if col == col_fecha_found or col == col_movil_found:
                continue
                
            # Clean column name once (Aggressive)
            # Remove dots, dashes, quotes, brackets, parents
            cl_clean = cl.lower().replace('.', ' ').replace('-', ' ').replace('"', '').replace("'", "").replace('[', '').replace(']', '').replace('(', '').replace(')', '').strip()
            
            # 1. Exact Match (already checked via dict lookups above roughly)
            # 2. Substring Match
            # 3. Token Match (New)
            # 4. Fuzzy Match (New - difflib)
            
            best_ratio = 0
            best_match_sku = None
            
            for sn, ss in mapa_sistema_nombres.items():
                # Clean System Name same way
                sn_clean = sn.replace('.', ' ').replace('-', ' ').replace('"', '').replace("'", "").replace('[', '').replace(']', '').replace('(', '').replace(')', '').strip()
                
                # A) Substring (High confidence)
                # Check cleaned versions too!
                if sn_clean in cl_clean or cl_clean in sn_clean:
                    # Relaxed: Allow 3+ chars (e.g. "ONT", "UTP", "STB")
                    if len(sn_clean)>2 and len(cl_clean)>2:
                         mapa_sku_columna[col] = ss
                         best_match_sku = None 
                         print(f"  [MATCH] '{col}' -> {ss} (Substring)")
                         break
                
                # B) Token Subset (Medium confidence)
                tokens_col = set(cl_clean.split())
                tokens_sys = set(sn_clean.split())
                
                # Relaxed: Allow single token match if it's significant (len>2)
                if len(tokens_col) >= 1:
                    # Filter out tiny tokens from the set to be safe?
                    # basic safety: assume cl_clean > 2 already checked conceptually or rely on issubset
                    if tokens_col.issubset(tokens_sys):
                        # Avoid matching generic words if possible? 
                        # For now, trust the user's column isn't just "DE" or "EL"
                        mapa_sku_columna[col] = ss
                        best_match_sku = None
                        print(f"  [MATCH] '{col}' -> {ss} (Token Subset)")
                        break
                
                # C) Fuzzy Match (Low confidence fallback)
                # Only check if we haven't found a match yet
                ratio = difflib.SequenceMatcher(None, cl_clean, sn_clean).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match_sku = ss
            
            # Apply fuzzy match if threshold met and no better match found
            if best_match_sku and col not in mapa_sku_columna:
                if best_ratio > 0.6: # 60% similarity
                    print(f"  [MATCH] '{col}' -> {best_match_sku} (Fuzzy {best_ratio:.2f})")
                    mapa_sku_columna[col] = best_match_sku
        
        # Debug Report of Unmapped
        mapped_cols = set(mapa_sku_columna.keys())
        all_cols = set(df.columns)
        unmapped = all_cols - mapped_cols - {col_fecha_found, col_movil_found}
        if unmapped:
            print(f"⚠️ [WARNING] Unmapped Columns: {unmapped}")
        
        if not mapa_sku_columna: 
            # Fallback: List columns to help user debug
            cols_debug = ", ".join(df.columns[:5])
            raise ValueError(f"No valid products found in columns. Saw: {cols_debug}...")
        
        cols_keep = [col_fecha_found, col_movil_found] + list(mapa_sku_columna.keys())
        cols_keep = list(set(cols_keep) & set(df.columns))
        
        df_melt = df[cols_keep].melt(id_vars=[col_fecha_found, col_movil_found], 
                                     value_vars=[c for c in mapa_sku_columna.keys() if c in df.columns],
                                     var_name='_col', value_name='cantidad')
        df_melt['sku'] = df_melt['_col'].map(mapa_sku_columna)
        df_melt = df_melt.rename(columns={col_fecha_found:'fecha', col_movil_found:'movil'})
        
        return self._limpiar_tipos(df_melt[['fecha', 'movil', 'sku', 'cantidad']])

    def _limpiar_tipos(self, data):
        data = data.copy()
        data['fecha'] = pd.to_datetime(data['fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
        def cq(x):
            if str(x).lower().strip() in ['no', 'nan', '', 'none']: return 0
            try: return int(float(x))
            except: return 0
        data['cantidad'] = data['cantidad'].apply(cq)
        data['sku'] = data['sku'].astype(str).str.strip()
        data['movil'] = data['movil'].astype(str).str.strip()
        return data.dropna(subset=['fecha'])

def abrir_ventana_conciliacion_excel(master_app, mode='excel'):
    win = ReconciliationWindow(master_app, mode=mode)
    return win
