import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
from ..styles import Styles
from database import obtener_nombres_moviles, obtener_historial_faltantes, obtener_configuracion

class FaltantesDashboardWindow:
    def __init__(self, master_app):
        self.master_app = master_app
        self.master = master_app.master
        
        self.ventana = tk.Toplevel(self.master)
        self.ventana.title("🚩 Historial de Faltantes y Discrepancias")
        self.ventana.geometry("1100x700")
        try:
            self.ventana.state('zoomed')
        except:
            pass
        self.ventana.configure(bg='#f8f9fa')
        
        self.construir_ui()

    def construir_ui(self):
        # Header
        header = tk.Frame(self.ventana, bg=Styles.ACCENT_COLOR, height=70)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        tk.Label(header, text="🚩 HISTORIAL DE FALTANTES POR MÓVIL", 
                 font=('Segoe UI', 16, 'bold'), bg=Styles.ACCENT_COLOR, fg='white').pack(pady=15)
        
        # Filtros
        filter_frame = tk.Frame(self.ventana, bg='white', pady=15, padx=20)
        filter_frame.pack(fill='x')
        
        tk.Label(filter_frame, text="Móvil:", font=('Segoe UI', 10, 'bold'), bg='white').pack(side='left', padx=(0, 5))
        self.movil_combo = ttk.Combobox(filter_frame, values=["TODOS"] + obtener_nombres_moviles(), state="readonly", width=15)
        self.movil_combo.set("TODOS")
        self.movil_combo.pack(side='left', padx=(0, 20))
        
        tk.Label(filter_frame, text="Desde:", font=('Segoe UI', 10, 'bold'), bg='white').pack(side='left', padx=(0, 5))
        self.fecha_inicio = tk.Entry(filter_frame, width=12)
        self.fecha_inicio.insert(0, (date.today() - timedelta(days=30)).isoformat())
        self.fecha_inicio.pack(side='left', padx=(0, 15))
        
        tk.Label(filter_frame, text="Hasta:", font=('Segoe UI', 10, 'bold'), bg='white').pack(side='left', padx=(0, 5))
        self.fecha_fin = tk.Entry(filter_frame, width=12)
        self.fecha_fin.insert(0, date.today().isoformat())
        self.fecha_fin.pack(side='left', padx=(0, 15))
        
        btn_buscar = tk.Button(filter_frame, text="🔍 Consultar", command=self.cargar_datos,
                               bg=Styles.PRIMARY_COLOR, fg='white', font=('Segoe UI', 10, 'bold'), 
                               padx=20, relief='flat', cursor='hand2')
        btn_buscar.pack(side='left', padx=10)
        
        # Tabla
        table_frame = tk.Frame(self.ventana, bg='white', padx=20, pady=10)
        table_frame.pack(fill='both', expand=True)
        
        columns = ('ID', 'Fecha', 'Móvil', 'Paquete', 'SKU', 'Producto', 'Cant.', 'Series/Detalle', 'Observaciones')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings')
        
        self.tree.heading('ID', text='ID'); self.tree.column('ID', width=50, anchor='center')
        self.tree.heading('Fecha', text='Fecha'); self.tree.column('Fecha', width=130, anchor='center')
        self.tree.heading('Móvil', text='Móvil'); self.tree.column('Móvil', width=100)
        self.tree.heading('Paquete', text='Paquete'); self.tree.column('Paquete', width=100)
        self.tree.heading('SKU', text='SKU'); self.tree.column('SKU', width=100)
        self.tree.heading('Producto', text='Producto'); self.tree.column('Producto', width=200)
        self.tree.heading('Cant.', text='Cant.'); self.tree.column('Cant.', width=60, anchor='center')
        self.tree.heading('Series/Detalle', text='Series/Detalle'); self.tree.column('Series/Detalle', width=200)
        self.tree.heading('Observaciones', text='Observaciones'); self.tree.column('Observaciones', width=150)
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Summary bar
        self.summary_label = tk.Label(self.ventana, text="Total Faltantes: 0", font=('Segoe UI', 11, 'bold'), 
                                     bg='#eee', pady=5)
        self.summary_label.pack(fill='x')
        
        self.cargar_datos()

    def cargar_datos(self):
        movil = self.movil_combo.get()
        if movil == "TODOS": movil = None
        
        f_ini = self.fecha_inicio.get()
        f_fin = self.fecha_fin.get()
        
        # Validar fechas básicas
        try:
            if f_ini: date.fromisoformat(f_ini)
            if f_fin: date.fromisoformat(f_fin)
        except:
            messagebox.showerror("Error", "Formato de fecha inválido (YYYY-MM-DD)")
            return

        # Limpiar
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        faltantes = obtener_historial_faltantes(movil=movil, fecha_inicio=f_ini, fecha_fin=f_fin)
        
        total_qty = 0
        for f in faltantes:
            # f: (id, movil, sku, nombre, cantidad, fecha_audit, observaciones, seriales, paquete)
            total_qty += f[4]
            self.tree.insert('', 'end', values=(
                f[0], 
                f[5].strftime('%Y-%m-%d %H:%M') if hasattr(f[5], 'strftime') else f[5],
                f[1], f[8] or "NINGUNO", f[2], f[3] or "N/A", f[4], f[7] or "N/A", f[6] or ""
            ))
            
        self.summary_label.config(text=f"Total de Unidades Faltantes en el período: {total_qty}")
