"""
Dashboard de Analítica Avanzada para StockWare
Proporciona métricas avanzadas, tendencias y predicciones
"""
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta, date
from collections import defaultdict
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import numpy as np
import threading
import time


from database import (
    obtener_stock_actual_y_moviles,
    obtener_movimientos_por_rango,
    obtener_nombres_moviles,
    get_db_connection,
    run_query
)
from .styles import Styles
from .tooltips import create_tooltip

class AnalyticsTab:
    """Pestaña de analítica avanzada con métricas y visualizaciones"""
    
    def __init__(self, notebook, main_app):
        self.notebook = notebook
        self.main_app = main_app
        self.create_widgets()
        
    def create_widgets(self):
        """Crear interfaz de analítica"""
        analytics_frame = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(analytics_frame, text="📈 Analítica")
        
        # Título
        header = tk.Frame(analytics_frame, bg='#f8f9fa')
        header.pack(fill='x', padx=20, pady=(20, 10))
        
        tk.Label(header, text="📊 ANALÍTICA AVANZADA",
                font=('Segoe UI', 18, 'bold'), bg='#f8f9fa', fg=Styles.PRIMARY_COLOR).pack(side='left')
        
        # Botón de actualizar
        refresh_btn = tk.Button(header, text="🔄 Actualizar",
                               command=self.actualizar_analytics,
                               bg=Styles.PRIMARY_COLOR, fg='white',
                               font=('Segoe UI', 10, 'bold'),
                               relief='flat', padx=15, pady=8, cursor='hand2')
        refresh_btn.pack(side='right')
        create_tooltip(refresh_btn, "Actualizar todas las métricas y gráficos")
        
        # Selector de período
        self.create_period_selector(analytics_frame)
        
        # KPIs principales
        self.create_kpi_cards(analytics_frame)
        
        # Gráficos
        self.create_charts_section(analytics_frame)
        
        # Tablas de análisis
        self.create_analysis_tables(analytics_frame)
        
        # Cargar datos iniciales
        # Cargar datos iniciales - ASYNC
        self.notebook.after(500, self.actualizar_analytics) # Small delay to let UI show up first

        
    def create_period_selector(self, parent):
        """Crear selector de período de análisis"""
        period_frame = tk.Frame(parent, bg='#f8f9fa')
        period_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(period_frame, text="Período de análisis:",
                font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=(0, 10))
        
        self.period_var = tk.StringVar(value="30")
        periods = [
            ("Última semana", "7"),
            ("Último mes", "30"),
            ("Últimos 3 meses", "90"),
            ("Último año", "365")
        ]
        
        for text, days in periods:
            rb = tk.Radiobutton(period_frame, text=text, variable=self.period_var,
                               value=days, bg='#f8f9fa', font=('Segoe UI', 9),
                               command=self.actualizar_analytics)
            rb.pack(side='left', padx=5)
            
    def create_kpi_cards(self, parent):
        """Crear tarjetas de KPIs principales"""
        kpi_frame = tk.Frame(parent, bg='#f8f9fa')
        kpi_frame.pack(fill='x', padx=20, pady=10)
        
        self.kpi_labels = {}
        
        kpis = [
            {"key": "rotacion", "title": "Rotación de Inventario", "icon": "🔄", "color": "#3498db"},
            {"key": "dias_stock", "title": "Días de Stock", "icon": "📅", "color": "#27ae60"},
            {"key": "eficiencia", "title": "Eficiencia Abasto", "icon": "⚡", "color": "#f39c12"},
            {"key": "top_producto", "title": "Producto Top", "icon": "🏆", "color": "#9b59b6"},
        ]
        
        for i, kpi in enumerate(kpis):
            card = self.create_kpi_card(kpi_frame, kpi, i)
            kpi_frame.columnconfigure(i, weight=1)
            
    def create_kpi_card(self, parent, kpi, index):
        """Crear tarjeta individual de KPI"""
        card = tk.Frame(parent, bg='white', relief='raised', borderwidth=0,
                       highlightbackground='#ddd', highlightthickness=1)
        card.grid(row=0, column=index, padx=10, pady=10, sticky='nsew')
        
        # Icono
        tk.Label(card, text=kpi["icon"], font=('Segoe UI', 24),
                bg='white', fg=kpi["color"]).pack(pady=(15, 5))
        
        # Valor
        value_label = tk.Label(card, text="...", font=('Segoe UI', 20, 'bold'),
                              bg='white', fg=Styles.DARK_TEXT)
        value_label.pack(pady=5)
        self.kpi_labels[kpi["key"]] = value_label
        
        # Título
        tk.Label(card, text=kpi["title"], font=('Segoe UI', 9),
                bg='white', fg='#7f8c8d').pack(pady=(0, 15))
        
        return card
        
    def create_charts_section(self, parent):
        """Crear sección de gráficos"""
        charts_container = tk.Frame(parent, bg='#f8f9fa')
        charts_container.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Fila 1: Tendencia de stock y Consumo por móvil
        row1 = tk.Frame(charts_container, bg='#f8f9fa')
        row1.pack(fill='both', expand=True, pady=(0, 10))
        
        self.create_trend_chart(row1)
        self.create_mobile_consumption_chart(row1)
        
        # Fila 2: Abasto vs Consumo y Top productos
        row2 = tk.Frame(charts_container, bg='#f8f9fa')
        row2.pack(fill='both', expand=True)
        
        self.create_supply_vs_consumption_chart(row2)
        self.create_top_products_chart(row2)
        
    def create_trend_chart(self, parent):
        """Gráfico de tendencia de stock"""
        frame = tk.Frame(parent, bg='white', relief='raised', borderwidth=0,
                        highlightthickness=1, highlightbackground='#ddd')
        frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        tk.Label(frame, text="📈 Tendencia de Stock Total",
                font=('Segoe UI', 11, 'bold'), bg='white', fg='#2c3e50').pack(pady=10)
        
        self.fig_trend = Figure(figsize=(6, 3), dpi=100)
        self.ax_trend = self.fig_trend.add_subplot(111)
        self.canvas_trend = FigureCanvasTkAgg(self.fig_trend, master=frame)
        self.canvas_trend.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        
    def create_mobile_consumption_chart(self, parent):
        """Gráfico de consumo por móvil"""
        frame = tk.Frame(parent, bg='white', relief='raised', borderwidth=0,
                        highlightthickness=1, highlightbackground='#ddd')
        frame.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        tk.Label(frame, text="🚚 Consumo por Móvil",
                font=('Segoe UI', 11, 'bold'), bg='white', fg='#2c3e50').pack(pady=10)
        
        self.fig_mobile = Figure(figsize=(6, 3), dpi=100)
        self.ax_mobile = self.fig_mobile.add_subplot(111)
        self.canvas_mobile = FigureCanvasTkAgg(self.fig_mobile, master=frame)
        self.canvas_mobile.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        
    def create_supply_vs_consumption_chart(self, parent):
        """Gráfico de abasto vs consumo"""
        frame = tk.Frame(parent, bg='white', relief='raised', borderwidth=0,
                        highlightthickness=1, highlightbackground='#ddd')
        frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        tk.Label(frame, text="⚖️ Abasto vs Consumo Mensual",
                font=('Segoe UI', 11, 'bold'), bg='white', fg='#2c3e50').pack(pady=10)
        
        self.fig_supply = Figure(figsize=(6, 3), dpi=100)
        self.ax_supply = self.fig_supply.add_subplot(111)
        self.canvas_supply = FigureCanvasTkAgg(self.fig_supply, master=frame)
        self.canvas_supply.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        
    def create_top_products_chart(self, parent):
        """Gráfico de productos más consumidos"""
        frame = tk.Frame(parent, bg='white', relief='raised', borderwidth=0,
                        highlightthickness=1, highlightbackground='#ddd')
        frame.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        tk.Label(frame, text="🏆 Top 10 Productos Consumidos",
                font=('Segoe UI', 11, 'bold'), bg='white', fg='#2c3e50').pack(pady=10)
        
        self.fig_top = Figure(figsize=(6, 3), dpi=100)
        self.ax_top = self.fig_top.add_subplot(111)
        self.canvas_top = FigureCanvasTkAgg(self.fig_top, master=frame)
        self.canvas_top.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)
        
    def create_analysis_tables(self, parent):
        """Crear tablas de análisis"""
        tables_frame = tk.Frame(parent, bg='#f8f9fa')
        tables_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Tabla de productos con bajo stock
        self.create_low_stock_table(tables_frame)
        
    def create_low_stock_table(self, parent):
        """Tabla de productos con bajo stock"""
        frame = tk.Frame(parent, bg='white', relief='raised', borderwidth=0,
                        highlightthickness=1, highlightbackground='#ddd')
        frame.pack(fill='both', expand=True)
        
        tk.Label(frame, text="⚠️ Productos con Bajo Stock (Requieren Atención)",
                font=('Segoe UI', 11, 'bold'), bg='white', fg='#e74c3c').pack(pady=10, padx=10, anchor='w')
        
        columns = ("Producto", "Stock Actual", "Mínimo", "Consumo Promedio", "Días Restantes")
        self.low_stock_table = ttk.Treeview(frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            self.low_stock_table.heading(col, text=col)
            self.low_stock_table.column(col, width=150, anchor='center')
            
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.low_stock_table.yview)
        self.low_stock_table.configure(yscrollcommand=scrollbar.set)
        
        self.low_stock_table.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y', pady=10)
        
    def actualizar_analytics(self):
        """Actualizar todas las métricas y gráficos en segundo plano"""
        try:
            days = int(self.period_var.get())
        except:
            days = 30
            
        # Iniciar thread
        threading.Thread(target=self._fetch_analytics_data, args=(days,), daemon=True).start()

    def _fetch_analytics_data(self, days):
        """Obtiene todos los datos pesados en segundo plano"""
        try:
            fecha_fin = date.today()
            fecha_inicio = fecha_fin - timedelta(days=days)
            
            # 1. Obtener datos de stock (Pesado)
            stock_data = obtener_stock_actual_y_moviles()
            
            # 2. Obtener datos para gráficos específicos (Simulados o consultas reales)
            # Mobile consumption
            mobile_data = self._get_mobile_consumption_data(fecha_inicio, fecha_fin)
            
            # Top products
            top_products_data = self._get_top_products_data(fecha_inicio, fecha_fin)
            
            # Programar actualización en UI
            self.main_app.master.after(0, lambda: self._apply_analytics_data(
                stock_data, mobile_data, top_products_data, fecha_inicio, fecha_fin
            ))
            
        except Exception as e:
            print(f"Error fetching analytics data: {e}")

    def _get_mobile_consumption_data(self, fecha_inicio, fecha_fin):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            query = """
                SELECT movil_afectado, SUM(cantidad_afectada) as total
                FROM movimientos
                WHERE tipo_movimiento IN ('SALIDA', 'CONSUMO_MOVIL')
                AND fecha_evento BETWEEN ? AND ?
                AND movil_afectado IS NOT NULL
                GROUP BY movil_afectado
                ORDER BY total DESC
                LIMIT 10
            """
            run_query(cursor, query, (fecha_inicio.isoformat(), fecha_fin.isoformat()))
            datos = cursor.fetchall()
            conn.close()
            return datos
        except: 
            return []

    def _get_top_products_data(self, fecha_inicio, fecha_fin):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            query = """
                SELECT p.nombre, SUM(m.cantidad_afectada) as total
                FROM movimientos m
                JOIN productos p ON m.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
                WHERE m.tipo_movimiento IN ('SALIDA', 'CONSUMO_MOVIL', 'DESCARTE')
                AND m.fecha_evento BETWEEN ? AND ?
                GROUP BY m.sku_producto, p.nombre
                ORDER BY total DESC
                LIMIT 10
            """
            run_query(cursor, query, (fecha_inicio.isoformat(), fecha_fin.isoformat()))
            datos = cursor.fetchall()
            conn.close()
            return datos
        except:
            return []

    def _apply_analytics_data(self, stock_data, mobile_data, top_products_data, fecha_inicio, fecha_fin):
        """Aplica los datos a la UI (debe correr en el hilo principal)"""
        try:
            if not self.notebook.winfo_exists(): return

            # Calcular KPIs
            self.calcular_kpis_from_data(stock_data)
            
            # Actualizar gráficos
            self.actualizar_trend_chart_ui(stock_data, fecha_inicio, fecha_fin)
            self.actualizar_mobile_chart_ui(mobile_data)
            self.actualizar_supply_chart_ui()
            self.actualizar_top_products_chart_ui(top_products_data)
            
            # Actualizar tabla
            self.actualizar_low_stock_table_ui(stock_data)
            
        except Exception as e:
            print(f"Error applying analytics data: {e}")

    def calcular_kpis_from_data(self, stock_data):
        """Calcular KPIs con datos ya obtenidos"""
        try:
            if not stock_data: return
                
            # 1. Rotación
            total_consumo = sum(d[5] for d in stock_data)
            total_stock = sum(d[4] for d in stock_data)
            rotacion = round(total_consumo / total_stock, 2) if total_stock > 0 else 0
            if "rotacion" in self.kpi_labels: self.kpi_labels["rotacion"].config(text=f"{rotacion}x")
            
            # 2. Días stock
            dias_stock = round(total_stock / (total_consumo / 30), 1) if total_consumo > 0 else 999
            if "dias_stock" in self.kpi_labels: self.kpi_labels["dias_stock"].config(text=f"{dias_stock} días")
            
            # 3. Eficiencia
            total_abasto = sum(d[6] for d in stock_data)
            eficiencia = round((total_abasto / total_consumo * 100), 1) if total_consumo > 0 else 0
            if "eficiencia" in self.kpi_labels: self.kpi_labels["eficiencia"].config(text=f"{eficiencia}%")
            
            # 4. Top Producto
            if stock_data:
                top_producto = max(stock_data, key=lambda x: x[5])
                nombre_corto = top_producto[0][:15] + "..." if len(top_producto[0]) > 15 else top_producto[0]
                if "top_producto" in self.kpi_labels: 
                    self.kpi_labels["top_producto"].config(text=nombre_corto, font=('Segoe UI', 14, 'bold'))
        except Exception as e:
            print(f"Error calculating KPIs: {e}")

    def actualizar_trend_chart_ui(self, stock_data, fecha_inicio, fecha_fin):
        try:
            self.ax_trend.clear()
            if stock_data:
                total_stock = sum(d[4] for d in stock_data)
                dias = (fecha_fin - fecha_inicio).days
                fechas = [fecha_inicio + timedelta(days=i) for i in range(dias + 1)]
                variation_range = total_stock // 10
                if variation_range > 0:
                    stocks = [total_stock + np.random.randint(-variation_range, variation_range) for _ in fechas]
                else:
                    stocks = [total_stock for _ in fechas]
                
                self.ax_trend.plot(fechas, stocks, color='#3498db', linewidth=2, marker='o', markersize=3)
                self.ax_trend.fill_between(fechas, stocks, alpha=0.3, color='#3498db')
                self.ax_trend.set_ylabel('Stock Total')
                self.ax_trend.grid(True, alpha=0.3)
                self.ax_trend.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
                self.ax_trend.tick_params(axis='x', rotation=45, labelsize=8)
            self.fig_trend.tight_layout()
            self.canvas_trend.draw()
        except Exception as e:
            print(f"Error trend chart: {e}")

    def actualizar_mobile_chart_ui(self, datos):
        try:
            self.ax_mobile.clear()
            if datos:
                moviles = [d[0][:10] + "..." if len(d[0]) > 10 else d[0] for d in datos]
                consumos = [d[1] for d in datos]
                colors = plt.cm.Set3(range(len(moviles)))
                bars = self.ax_mobile.barh(moviles, consumos, color=colors)
                self.ax_mobile.set_xlabel('Cantidad Consumida')
                self.ax_mobile.grid(True, alpha=0.3, axis='x')
                for i, bar in enumerate(bars):
                    width = bar.get_width()
                    self.ax_mobile.text(width, bar.get_y() + bar.get_height()/2, f'{int(width)}', ha='left', va='center', fontsize=8)
            self.fig_mobile.tight_layout()
            self.canvas_mobile.draw()
        except Exception as e:
            print(f"Error mobile chart: {e}")

    def actualizar_supply_chart_ui(self):
        try:
            self.ax_supply.clear()
            meses = ['Mes 1', 'Mes 2', 'Mes 3']
            abastos = [1200, 1500, 1300]
            consumos = [1100, 1400, 1350]
            x = np.arange(len(meses))
            width = 0.35
            self.ax_supply.bar(x - width/2, abastos, width, label='Abasto', color='#27ae60')
            self.ax_supply.bar(x + width/2, consumos, width, label='Consumo', color='#e74c3c')
            self.ax_supply.set_xticks(x)
            self.ax_supply.set_xticklabels(meses)
            self.ax_supply.set_ylabel('Cantidad')
            self.ax_supply.legend()
            self.ax_supply.grid(True, alpha=0.3, axis='y')
            self.fig_supply.tight_layout()
            self.canvas_supply.draw()
        except: pass

    def actualizar_top_products_chart_ui(self, datos):
        try:
            self.ax_top.clear()
            if datos:
                productos = [d[0][:20] + "..." if len(d[0]) > 20 else d[0] for d in datos]
                cantidades = [d[1] for d in datos]
                colors = plt.cm.viridis(np.linspace(0, 1, len(productos)))
                self.ax_top.barh(productos, cantidades, color=colors)
                self.ax_top.set_xlabel('Cantidad Consumida')
                self.ax_top.grid(True, alpha=0.3, axis='x')
            self.fig_top.tight_layout()
            self.canvas_top.draw()
        except: pass

    def actualizar_low_stock_table_ui(self, stock_data):
        try:
            for item in self.low_stock_table.get_children():
                self.low_stock_table.delete(item)
            if not stock_data: return
            
            for producto in stock_data:
                nombre, sku, bodega, moviles, total, consumo, abasto = producto
                consumo_diario = consumo / 30 if consumo > 0 else 0
                dias_restantes = round(total / consumo_diario, 1) if consumo_diario > 0 else 999
                
                if dias_restantes < 30 and dias_restantes > 0:
                    self.low_stock_table.insert('', 'end', values=(
                        nombre, total, "N/A", round(consumo_diario, 2), f"{dias_restantes} días"
                    ), tags=('warning' if dias_restantes < 15 else 'normal',))
            
            self.low_stock_table.tag_configure('warning', background='#ffebee')
            self.low_stock_table.tag_configure('normal', background='#fff3e0')
        except: pass

            
    def calcular_kpis(self, fecha_inicio, fecha_fin):
        """Calcular KPIs principales"""
        try:
            # Obtener datos
            stock_data = obtener_stock_actual_y_moviles()
            
            if not stock_data:
                return
                
            # 1. Rotación de inventario (Consumo / Stock Promedio)
            total_consumo = sum(d[5] for d in stock_data)  # índice 5 es consumo
            total_stock = sum(d[4] for d in stock_data)    # índice 4 es total
            rotacion = round(total_consumo / total_stock, 2) if total_stock > 0 else 0
            self.kpi_labels["rotacion"].config(text=f"{rotacion}x")
            
            # 2. Días de stock disponible
            dias_stock = round(total_stock / (total_consumo / 30), 1) if total_consumo > 0 else 999
            self.kpi_labels["dias_stock"].config(text=f"{dias_stock} días")
            
            # 3. Eficiencia de abasto (Abasto / Consumo * 100)
            total_abasto = sum(d[6] for d in stock_data)  # índice 6 es abasto
            eficiencia = round((total_abasto / total_consumo * 100), 1) if total_consumo > 0 else 0
            self.kpi_labels["eficiencia"].config(text=f"{eficiencia}%")
            
            # 4. Producto top (más consumido)
            if stock_data:
                top_producto = max(stock_data, key=lambda x: x[5])
                nombre_corto = top_producto[0][:15] + "..." if len(top_producto[0]) > 15 else top_producto[0]
                self.kpi_labels["top_producto"].config(text=nombre_corto, font=('Segoe UI', 14, 'bold'))
                
        except Exception as e:
            print(f"Error al calcular KPIs: {e}")
            
    def actualizar_trend_chart(self, fecha_inicio, fecha_fin):
        """Actualizar gráfico de tendencia"""
        try:
            self.ax_trend.clear()
            
            # Simulación de datos de tendencia (en producción, obtener de BD)
            # Por ahora mostrar stock actual como línea plana
            stock_data = obtener_stock_actual_y_moviles()
            if stock_data:
                total_stock = sum(d[4] for d in stock_data)
                
                # Crear datos de ejemplo para la tendencia
                dias = (fecha_fin - fecha_inicio).days
                fechas = [fecha_inicio + timedelta(days=i) for i in range(dias + 1)]
                # Simular variación de ±10%
                variation_range = total_stock // 10
                if variation_range > 0:
                    stocks = [total_stock + np.random.randint(-variation_range, variation_range) for _ in fechas]
                else:
                    stocks = [total_stock for _ in fechas]
                
                self.ax_trend.plot(fechas, stocks, color='#3498db', linewidth=2, marker='o', markersize=3)
                self.ax_trend.fill_between(fechas, stocks, alpha=0.3, color='#3498db')
                self.ax_trend.set_ylabel('Stock Total')
                self.ax_trend.grid(True, alpha=0.3)
                self.ax_trend.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
                self.ax_trend.tick_params(axis='x', rotation=45, labelsize=8)
                
            self.fig_trend.tight_layout()
            self.canvas_trend.draw()
            
        except Exception as e:
            print(f"Error en gráfico de tendencia: {e}")
            
    def actualizar_mobile_chart(self, fecha_inicio, fecha_fin):
        """Actualizar gráfico de consumo por móvil"""
        try:
            self.ax_mobile.clear()
            
            # Obtener consumo por móvil desde BD
            conn = get_db_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT movil_afectado, SUM(cantidad_afectada) as total
                FROM movimientos
                WHERE tipo_movimiento IN ('SALIDA', 'CONSUMO_MOVIL')
                AND fecha_evento BETWEEN ? AND ?
                AND movil_afectado IS NOT NULL
                GROUP BY movil_afectado
                ORDER BY total DESC
                LIMIT 10
            """
            
            run_query(cursor, query, (fecha_inicio.isoformat(), fecha_fin.isoformat()))
            datos = cursor.fetchall()
            conn.close()
            
            if datos:
                moviles = [d[0][:10] + "..." if len(d[0]) > 10 else d[0] for d in datos]
                consumos = [d[1] for d in datos]
                
                colors = plt.cm.Set3(range(len(moviles)))
                bars = self.ax_mobile.barh(moviles, consumos, color=colors)
                self.ax_mobile.set_xlabel('Cantidad Consumida')
                self.ax_mobile.grid(True, alpha=0.3, axis='x')
                
                # Valores en las barras
                for i, bar in enumerate(bars):
                    width = bar.get_width()
                    self.ax_mobile.text(width, bar.get_y() + bar.get_height()/2,
                                       f'{int(width)}', ha='left', va='center', fontsize=8)
                    
            self.fig_mobile.tight_layout()
            self.canvas_mobile.draw()
            
        except Exception as e:
            print(f"Error en gráfico de móviles: {e}")
            
    def actualizar_supply_chart(self, fecha_inicio, fecha_fin):
        """Actualizar gráfico de abasto vs consumo"""
        try:
            self.ax_supply.clear()
            
            # Datos de ejemplo (en producción, agrupar por mes desde BD)
            meses = ['Mes 1', 'Mes 2', 'Mes 3']
            abastos = [1200, 1500, 1300]
            consumos = [1100, 1400, 1350]
            
            x = np.arange(len(meses))
            width = 0.35
            
            self.ax_supply.bar(x - width/2, abastos, width, label='Abasto', color='#27ae60')
            self.ax_supply.bar(x + width/2, consumos, width, label='Consumo', color='#e74c3c')
            
            self.ax_supply.set_xticks(x)
            self.ax_supply.set_xticklabels(meses)
            self.ax_supply.set_ylabel('Cantidad')
            self.ax_supply.legend()
            self.ax_supply.grid(True, alpha=0.3, axis='y')
            
            self.fig_supply.tight_layout()
            self.canvas_supply.draw()
            
        except Exception as e:
            print(f"Error en gráfico de abasto vs consumo: {e}")
            
    def actualizar_top_products_chart(self, fecha_inicio, fecha_fin):
        """Actualizar gráfico de top productos"""
        try:
            self.ax_top.clear()
            
            # Obtener top productos consumidos
            conn = get_db_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT p.nombre, SUM(m.cantidad_afectada) as total
                FROM movimientos m
                JOIN productos p ON m.sku_producto = p.sku AND p.ubicacion = 'BODEGA'
                WHERE m.tipo_movimiento IN ('SALIDA', 'CONSUMO_MOVIL', 'DESCARTE')
                AND m.fecha_evento BETWEEN ? AND ?
                GROUP BY m.sku_producto, p.nombre
                ORDER BY total DESC
                LIMIT 10
            """
            
            run_query(cursor, query, (fecha_inicio.isoformat(), fecha_fin.isoformat()))
            datos = cursor.fetchall()
            conn.close()
            
            if datos:
                productos = [d[0][:20] + "..." if len(d[0]) > 20 else d[0] for d in datos]
                cantidades = [d[1] for d in datos]
                
                colors = plt.cm.viridis(np.linspace(0, 1, len(productos)))
                self.ax_top.barh(productos, cantidades, color=colors)
                self.ax_top.set_xlabel('Cantidad Consumida')
                self.ax_top.grid(True, alpha=0.3, axis='x')
                
            self.fig_top.tight_layout()
            self.canvas_top.draw()
            
        except Exception as e:
            print(f"Error en gráfico de top productos: {e}")
            
    def actualizar_low_stock_table(self):
        """Actualizar tabla de productos con bajo stock"""
        try:
            # Limpiar tabla
            for item in self.low_stock_table.get_children():
                self.low_stock_table.delete(item)
                
            # Obtener productos con bajo stock
            stock_data = obtener_stock_actual_y_moviles()
            
            for producto in stock_data:
                nombre, sku, bodega, moviles, total, consumo, abasto = producto
                
                # Calcular consumo promedio diario (consumo total / 30 días)
                consumo_diario = consumo / 30 if consumo > 0 else 0
                
                # Calcular días restantes
                dias_restantes = round(total / consumo_diario, 1) if consumo_diario > 0 else 999
                
                # Mostrar solo si está bajo stock (menos de 30 días)
                if dias_restantes < 30 and dias_restantes > 0:
                    self.low_stock_table.insert('', 'end', values=(
                        nombre,
                        total,
                        "N/A",  # Mínimo (podría obtenerse de productos.minimo_stock)
                        round(consumo_diario, 2),
                        f"{dias_restantes} días"
                    ), tags=('warning' if dias_restantes < 15 else 'normal',))
                    
            # Configurar colores
            self.low_stock_table.tag_configure('warning', background='#ffebee')
            self.low_stock_table.tag_configure('normal', background='#fff3e0')
            
        except Exception as e:
            print(f"Error al actualizar tabla de bajo stock: {e}")
