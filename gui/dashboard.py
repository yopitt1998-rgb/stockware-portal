import tkinter as tk
import threading

from tkinter import ttk
from .styles import Styles
from .tooltips import create_tooltip, TOOLTIPS
from .utils import ScrollableFrame
from database import obtener_estadisticas_reales, obtener_inventario, obtener_stock_actual_y_moviles, obtener_ultimos_movimientos
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib
matplotlib.use('TkAgg')

class DashboardTab:
    def __init__(self, notebook, main_app):
        self.notebook = notebook
        self.main_app = main_app
        self.metric_labels = {}
        self.scroll_container = None
        self.dashboard_table = None
        self.ax_bar = None
        self.fig_bar = None
        self.canvas_bar = None
        self.ax_pie = None
        self.fig_pie = None
        self.canvas_pie = None
        
        self.create_widgets()
        
    def create_widgets(self):
        """Crear pestaña de Dashboard"""
        dashboard_frame = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(dashboard_frame, text="📊 Dashboard")
        
        # Envolver todo en un ScrollableFrame para pantallas pequeñas
        self.scroll_container = ScrollableFrame(dashboard_frame)
        self.scroll_container.pack(fill='both', expand=True)
        
        main_content = self.scroll_container.scrollable_frame

        # Grid para métricas
        metrics_frame = ttk.Frame(main_content, style='Modern.TFrame')
        metrics_frame.pack(fill='x', padx=20, pady=20)
        
        # Métricas iniciales (se actualizarán luego)
        metrics_data = [
            {"title": "Productos en Bodega", "key": "productos_bodega", "icon": "📦", "color": Styles.SECONDARY_COLOR},
            {"title": "Móviles Activos", "key": "moviles_activos", "icon": "🚚", "color": Styles.SUCCESS_COLOR},
            {"title": "Stock Total", "key": "stock_total", "icon": "📈", "color": Styles.WARNING_COLOR},
            {"title": "Bajo Stock", "key": "bajo_stock", "icon": "⚠️", "color": Styles.ACCENT_COLOR}
        ]
        
        for i, metric in enumerate(metrics_data):
            self.create_metric_card(metrics_frame, metric, i)
            
        # Acciones Rápidas
        self.create_quick_actions(main_content)
        
        # Tabla de movimientos recientes
        self.create_recent_table(main_content)

        # Gráficos
        self.create_charts(main_content)

        # Actualizar valores iniciales
        self.actualizar_metricas()
        
        # Iniciar ciclo de auto-actualización (cada 60 segundos)
        self.iniciar_auto_refresh()

    def iniciar_auto_refresh(self):
        """Actualiza las métricas automáticamente cada 60 segundos"""
        def refresh_loop():
            # Check if the notebook still exists before updating
            if self.notebook.winfo_exists():
                self.actualizar_metricas()
                # OPTIMIZADO: Reducido de 30 a 60 segundos para disminuir carga en la base de datos
                self.main_app.master.after(60000, refresh_loop)  # 60 segundos
            # else: the window is closed, stop scheduling
        
        refresh_loop()
        
    def on_card_click(self, key):
        """Maneja el evento de click en las tarjetas del dashboard"""
        if key == "productos_bodega" or key == "stock_total":
            self.main_app.switch_to_tab("Inventario")
        elif key == "moviles_activos":
            self.main_app.perform_inventory_action('abrir_ventana_gestion_moviles')
        elif key == "bajo_stock":
            self.main_app.perform_inventory_action('mostrar_stock_critico')

    def create_metric_card(self, parent, metric, index):
        """Crear tarjeta de métrica individual moderna e interactiva"""
        card = tk.Frame(parent, bg='white', relief='raised', borderwidth=0, 
                       highlightbackground='#ddd', highlightthickness=1, cursor='hand2')
        card.grid(row=0, column=index, padx=10, pady=10, sticky='nsew')
        parent.columnconfigure(index, weight=1)
        
        # Icono y contenido
        icon_frame = tk.Frame(card, bg='white', cursor='hand2')
        icon_frame.pack(fill='x', pady=(15, 5))
        
        icon_label = tk.Label(icon_frame, text=metric["icon"], font=('Segoe UI', 28), 
                             bg='white', fg=metric["color"], cursor='hand2')
        icon_label.pack()
        
        # Label para el valor (guardar referencia para actualizar)
        value_label = tk.Label(card, text="...", font=('Segoe UI', 24, 'bold'),
                              bg='white', fg=Styles.DARK_TEXT, cursor='hand2')
        value_label.pack(pady=5)
        self.metric_labels[metric["key"]] = value_label
        
        title_label = tk.Label(card, text=metric["title"], font=('Segoe UI', 10),
                              bg='white', fg='#7f8c8d', cursor='hand2')
        title_label.pack(pady=(0, 15))
        
        # Interacciones Hover y Click
        def on_enter(e):
            card.configure(bg='#f0f4f8')
            icon_frame.configure(bg='#f0f4f8')
            icon_label.configure(bg='#f0f4f8')
            value_label.configure(bg='#f0f4f8')
            title_label.configure(bg='#f0f4f8')
            
        def on_leave(e):
            card.configure(bg='white')
            icon_frame.configure(bg='white')
            icon_label.configure(bg='white')
            value_label.configure(bg='white')
            title_label.configure(bg='white')
            
        def on_click(e, key=metric["key"]):
            self.on_card_click(key)

        for widget in (card, icon_frame, icon_label, value_label, title_label):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)
            
        return card

    def create_quick_actions(self, parent):
        quick_actions_frame = ttk.Frame(parent, style='Modern.TFrame')
        quick_actions_frame.pack(fill='x', padx=20, pady=10)

        header_frame = tk.Frame(quick_actions_frame, bg='#f8fafc')
        header_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(header_frame, text="ACCIONES RÁPIDAS:", style='Subtitle.TLabel').pack(side='left')
        
        btn_refresh = tk.Button(header_frame, text="🔄 Sincronizar", 
                              command=self.main_app.refresh_app_cache,
                              font=('Segoe UI', 8, 'bold'), bg='#e2e8f0', fg='#475569',
                              relief='flat', padx=8, pady=2, cursor='hand2')
        btn_refresh.pack(side='right')
        
        # DETECTAR MODO SANTIAGO
        import os
        is_santiago = os.environ.get('SANTIAGO_DIRECT_MODE') == '1'

        if is_santiago:
            quick_actions = [
                ("🔫 Abasto Scanner", lambda: self.main_app.perform_inventory_action('abrir_ventana_abasto_scanner'), '#00C853'),
                ("⚠️ Reportar Daño", lambda: self.main_app.switch_to_tab("Material Dañado"), '#c0392b'),
                ("🔫 Auditoría Física", lambda: self.main_app.switch_to_tab("Auditoría Física"), '#607D8B'),
                ("🚚 Gestión Móviles", lambda: self.main_app.perform_inventory_action('abrir_ventana_gestion_moviles'), '#3498db')
            ]
        else:
            quick_actions = [
                ("🔫 Abasto Scanner", lambda: self.main_app.perform_inventory_action('abrir_ventana_abasto_scanner'), '#00C853'),
                ("🔫 Salida Scanner", lambda: self.main_app.perform_inventory_action('abrir_ventana_salida_movil_scanner'), '#FF6F00'),
                ("🔄 Retorno de Móvil", lambda: self.main_app.perform_inventory_action('abrir_ventana_retorno_movil'), Styles.SUCCESS_COLOR),
                ("📜 Registro Global", lambda: self.main_app.switch_to_tab("Registro Global"), '#6f42c1')
            ]
        
        actions_frame = ttk.Frame(quick_actions_frame, style='Modern.TFrame')
        actions_frame.pack(fill='x')
        
        for i, (text, command, color) in enumerate(quick_actions):
            btn = tk.Button(actions_frame, text=text, command=command,
                          bg=color, fg='white', font=('Segoe UI', 10, 'bold'),
                          relief='flat', bd=0, padx=20, pady=12, cursor='hand2')
            btn.pack(side='left', padx=5, fill='x', expand=True)
            
            # Agregar tooltips
            tooltip_keys = ["nuevo_abasto", "salida_movil", "retorno_movil", "historial_instalaciones"]
            if i < len(tooltip_keys):
                create_tooltip(btn, TOOLTIPS.get(tooltip_keys[i], ""))
            
            # Efectos hover
            def on_enter(e, b=btn): b.configure(bg=self.darken_color(b.cget('bg')))
            def on_leave(e, b=btn, c=color): b.configure(bg=c)
            
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

    def create_recent_table(self, parent):
        table_frame = ttk.Frame(parent, style='Modern.TFrame')
        table_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        ttk.Label(table_frame, text="ÚLTIMOS MOVIMIENTOS", style='Subtitle.TLabel').pack(anchor='w', pady=(0, 10))
        
        columns = ("ID", "Fecha", "Tipo", "Producto", "Cantidad", "Detalle")
        self.dashboard_table = ttk.Treeview(table_frame, columns=columns, show='headings', height=12, style='Modern.Treeview')
        
        self.dashboard_table.heading("ID", text="ID")
        self.dashboard_table.heading("Fecha", text="FECHA")
        self.dashboard_table.heading("Tipo", text="TIPO")
        self.dashboard_table.heading("Producto", text="PRODUCTO")
        self.dashboard_table.heading("Cantidad", text="CANT.")
        self.dashboard_table.heading("Detalle", text="DETALLE")
        
        self.dashboard_table.column("ID", width=50, anchor='center')
        self.dashboard_table.column("Fecha", width=100, anchor='center')
        self.dashboard_table.column("Tipo", width=120, anchor='center')
        self.dashboard_table.column("Producto", width=250)
        self.dashboard_table.column("Cantidad", width=80, anchor='center')
        self.dashboard_table.column("Detalle", width=150, anchor='center')
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.dashboard_table.yview)
        self.dashboard_table.configure(yscrollcommand=scrollbar.set)
        
        self.dashboard_table.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        def on_mousewheel(event):
            self.dashboard_table.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.dashboard_table.bind("<MouseWheel>", on_mousewheel)
        
        # self.cargar_datos_recent() # REMOVED: Loaded asynchronously via actualizar_metricas

    def actualizar_metricas(self):
        """Actualiza las métricas y la tabla en un hilo separado para no bloquear la UI"""
        self.main_app.set_status("🔄 Actualizando dashboard...")
        
        def run_update():
            try:
                # 1. Obtener métricas pesadas
                estadisticas = obtener_estadisticas_reales()
                
                # 2. Obtener movimientos recientes
                movimientos = obtener_ultimos_movimientos(15)
                
                # 3. Obtener datos para gráficos
                datos_charts = obtener_stock_actual_y_moviles()
                
                # Programar actualización de la UI en el hilo principal
                def _success():
                    self._aplicar_actualizacion_ui(estadisticas, movimientos, datos_charts)
                    self.main_app.set_status("✅ Dashboard actualizado", timeout=2000)
                
                self.main_app.master.after(0, _success)
            except Exception as e:
                self.main_app.set_status(f"⚠️ Error actualizando dashboard: {e}", timeout=5000)
                print(f"⚠️ Error al actualizar dashboard: {e}")
                
                # Mostrar error visual en los labels
                def _mostrar_error_conexion():
                    if not self.notebook.winfo_exists():
                        return
                    for key, lbl in self.metric_labels.items():
                        try: lbl.config(text="⚠️")
                        except: pass
                    if self.dashboard_table and self.dashboard_table.winfo_exists():
                        for child in self.dashboard_table.get_children():
                            self.dashboard_table.delete(child)
                        self.dashboard_table.insert('', tk.END, values=(
                            "❌", "Error de Red", "Sin conexión a MySQL",
                            "Verifica tu internet y reintenta", "", ""
                        ))
                self.main_app.master.after(0, _mostrar_error_conexion)

        threading.Thread(target=run_update, daemon=True).start()

    def _aplicar_actualizacion_ui(self, estadisticas, movimientos, datos_charts):
        """Aplica los datos obtenidos a los widgets de la interfaz"""
        if not self.notebook.winfo_exists():
            return

        # Actualizar tarjetas
        if "productos_bodega" in self.metric_labels:
            self.metric_labels["productos_bodega"].config(text=str(estadisticas.get("productos_bodega", 0)))
        if "moviles_activos" in self.metric_labels:
            self.metric_labels["moviles_activos"].config(text=str(estadisticas.get("moviles_activos", 0)))
        if "stock_total" in self.metric_labels:
            self.metric_labels["stock_total"].config(text=f"{estadisticas.get('stock_total', 0):,}")
        if "prestamos_activos" in self.metric_labels:
            self.metric_labels["prestamos_activos"].config(text=str(estadisticas.get("prestamos_activos", 0)))
        if "bajo_stock" in self.metric_labels:
            self.metric_labels["bajo_stock"].config(text=str(estadisticas.get("bajo_stock", 0)))

        # Actualizar tabla
        for item in self.dashboard_table.get_children():
            self.dashboard_table.delete(item)
            
        if not movimientos:
            self.dashboard_table.insert('', tk.END, values=("", "", "No hay movimientos recientes", "", "", ""))
        else:
            for row in movimientos:
                self.dashboard_table.insert('', tk.END, values=row)

        # Actualizar gráficos
        self._actualizar_charts_ui(datos_charts)

    def _actualizar_charts_ui(self, datos):
        """Aplica los datos a los gráficos (debe llamarse desde el hilo principal)"""
        if not datos:
            return

        # --- Gráfico de Barras ---
        datos_ordenados = sorted(datos, key=lambda x: x[4], reverse=True)[:5]
        nombres = [d[0][:15] + '...' if len(d[0]) > 15 else d[0] for d in datos_ordenados]
        totales = [d[4] for d in datos_ordenados]
        
        self.ax_bar.clear()
        colors_bar = ['#3498db', '#2ecc71', '#9b59b6', '#f1c40f', '#e67e22']
        bars = self.ax_bar.bar(nombres, totales, color=colors_bar[:len(nombres)])
        
        self.ax_bar.set_ylabel('Cantidad Total')
        self.ax_bar.tick_params(axis='x', rotation=45, labelsize=8)
        self.ax_bar.spines['top'].set_visible(False)
        self.ax_bar.spines['right'].set_visible(False)
        
        for bar in bars:
            height = bar.get_height()
            self.ax_bar.text(bar.get_x() + bar.get_width()/2., height, f'{int(height)}', ha='center', va='bottom')
            
        self.fig_bar.tight_layout()
        self.canvas_bar.draw()
        
        # --- Gráfico de Torta ---
        total_bodega = sum(d[2] for d in datos)
        total_moviles = sum(d[3] for d in datos)
        
        self.ax_pie.clear()
        if total_bodega + total_moviles > 0:
            labels = ['Bodega', 'Móviles']
            sizes = [total_bodega, total_moviles]
            colors_pie = ['#3498db', '#27ae60']
            self.ax_pie.pie(sizes, explode=(0.05, 0), labels=labels, colors=colors_pie,
                           autopct='%1.1f%%', shadow=True, startangle=90, textprops={'fontsize': 9})
            self.ax_pie.axis('equal')
        else:
            self.ax_pie.text(0.5, 0.5, "Sin Datos", ha='center', va='center')
            
        self.canvas_pie.draw()

    def create_charts(self, parent):
        """Crea el área de gráficos"""
        charts_frame = ttk.Frame(parent, style='Modern.TFrame')
        charts_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Frame izquierdo (Barras) y derecho (Torta)
        self.fig_bar = plt.Figure(figsize=(5, 4), dpi=100)
        self.ax_bar = self.fig_bar.add_subplot(111)
        
        self.fig_pie = plt.Figure(figsize=(4, 4), dpi=100)
        self.ax_pie = self.fig_pie.add_subplot(111)
        
        # Canvas
        bar_frame = tk.Frame(charts_frame, bg='white', relief='raised', borderwidth=0, highlightthickness=1, highlightbackground='#ddd')
        bar_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        tk.Label(bar_frame, text="Top 5 Productos (Mayor Stock)", font=('Segoe UI', 12, 'bold'), bg='white', fg='#2c3e50').pack(pady=10)
        
        self.canvas_bar = FigureCanvasTkAgg(self.fig_bar, master=bar_frame)
        self.canvas_bar.get_tk_widget().pack(fill='both', expand=True)
        
        pie_frame = tk.Frame(charts_frame, bg='white', relief='raised', borderwidth=0, highlightthickness=1, highlightbackground='#ddd')
        pie_frame.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        tk.Label(pie_frame, text="Distribución de Stock", font=('Segoe UI', 12, 'bold'), bg='white', fg='#2c3e50').pack(pady=10)
        
        self.canvas_pie = FigureCanvasTkAgg(self.fig_pie, master=pie_frame)
        self.canvas_pie.get_tk_widget().pack(fill='both', expand=True)

    def actualizar_charts(self):
        """Actualiza los datos de los gráficos"""
        datos = obtener_stock_actual_y_moviles()
        if not datos:
            return

        # --- Gráfico de Barras (Top 5 Stock Total) ---
        # datos: (nombre, sku, bodega, moviles, total, consumo, abasto)
        # Ordenar por total descendente
        datos_ordenados = sorted(datos, key=lambda x: x[4], reverse=True)[:5]
        
        nombres = [d[0][:15] + '...' if len(d[0]) > 15 else d[0] for d in datos_ordenados]
        totales = [d[4] for d in datos_ordenados]
        
        self.ax_bar.clear()
        colors_bar = ['#3498db', '#2ecc71', '#9b59b6', '#f1c40f', '#e67e22']
        bars = self.ax_bar.bar(nombres, totales, color=colors_bar[:len(nombres)])
        
        # Etiquetas
        self.ax_bar.set_ylabel('Cantidad Total')
        self.ax_bar.tick_params(axis='x', rotation=45, labelsize=8)
        self.ax_bar.spines['top'].set_visible(False)
        self.ax_bar.spines['right'].set_visible(False)
        
        # Valores sobre barras
        for bar in bars:
            height = bar.get_height()
            self.ax_bar.text(bar.get_x() + bar.get_width()/2., height,
                            f'{int(height)}',
                            ha='center', va='bottom')
            
        self.fig_bar.tight_layout()
        self.canvas_bar.draw()
        
        # --- Gráfico de Torta (Bodega vs Moviles) ---
        total_bodega = sum(d[2] for d in datos)
        total_moviles = sum(d[3] for d in datos)
        
        self.ax_pie.clear()
        if total_bodega + total_moviles > 0:
            labels = ['Bodega', 'Móviles']
            sizes = [total_bodega, total_moviles]
            colors_pie = ['#3498db', '#27ae60']
            explode = (0.05, 0)
            
            self.ax_pie.pie(sizes, explode=explode, labels=labels, colors=colors_pie,
                           autopct='%1.1f%%', shadow=True, startangle=90, textprops={'fontsize': 9})
            self.ax_pie.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        else:
            self.ax_pie.text(0.5, 0.5, "Sin Datos", ha='center', va='center')
            
        self.canvas_pie.draw()

    def cargar_datos_recent(self):
        for item in self.dashboard_table.get_children():
            self.dashboard_table.delete(item)
            
        datos = obtener_ultimos_movimientos(15)
        if not datos:
            self.dashboard_table.insert('', tk.END, values=("", "", "No hay movimientos recientes", "", "", ""))
            return

        for row in datos:
            # row = (id, fecha, tipo, producto, cantidad, detalle)
            self.dashboard_table.insert('', tk.END, values=row)

    def darken_color(self, hex_color, factor=0.8):
        """Oscurece un color HEX para efecto hover (copiado de utilidades)"""
        # Si no queremos duplicar esto, podríamos ponerlo en Styles o utils
        # Por ahora lo replico simple
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
            
            return f'#{r:02x}{g:02x}{b:02x}'
        except:
            return hex_color
