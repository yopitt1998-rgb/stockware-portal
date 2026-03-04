import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import date

from database import (
    obtener_todos_los_skus_para_movimiento,
    registrar_danado_directo,
    obtener_info_serial,
    logger
)
from config import COLORS, PRODUCTOS_CON_CODIGO_BARRA

class SantiagoDanadosTab:
    def __init__(self, master, app_instance):
        self.master = master
        self.app = app_instance
        self.setup_ui()
        self.cargar_datos_iniciales()

    def setup_ui(self):
        # Main container
        self.main_frame = tk.Frame(self.master, bg='#f8f9fa', padx=20, pady=20)
        self.main_frame.pack(fill='both', expand=True)

        # Header
        header = tk.Frame(self.main_frame, bg='white', relief='flat', pady=15, padx=20)
        header.pack(fill='x', pady=(0, 20))
        
        tk.Label(header, text="⚠️ Reporte de Material / Equipo Dañado", 
                 font=('Segoe UI', 18, 'bold'), bg='white', fg='#c0392b').pack(anchor='w')
        tk.Label(header, text="Use esta pestaña para dar de baja material que llegó dañado o falló en bodega.", 
                 font=('Segoe UI', 9), bg='white', fg='gray').pack(anchor='w')

        # Reporter Info
        form_frame = tk.Frame(self.main_frame, bg='white', padx=20, pady=20)
        form_frame.pack(fill='x')
        
        tk.Label(form_frame, text="Reportado por:", font=('Segoe UI', 10, 'bold'), bg='white').pack(side='left', padx=10)
        self.reporter_entry = ttk.Entry(form_frame, font=('Segoe UI', 10), width=30)
        self.reporter_entry.pack(side='left', padx=10)
        self.reporter_entry.insert(0, "Bodega Santiago")

        tk.Label(form_frame, text="Observación:", font=('Segoe UI', 10, 'bold'), bg='white').pack(side='left', padx=(40, 10))
        self.obs_entry = ttk.Entry(form_frame, font=('Segoe UI', 10), width=50)
        self.obs_entry.pack(side='left', padx=10)
        self.obs_entry.insert(0, "Material Dañado / Defectuoso")

        # Search & Quick Scan
        search_panel = tk.Frame(self.main_frame, bg='white', padx=20, pady=20)
        search_panel.pack(fill='x', pady=(0, 20))
        
        tk.Label(search_panel, text="🔫 ESCANEAR MAC / SERIAL (Baja Directa):", bg='white', font=('Segoe UI', 11, 'bold'), fg='#c0392b').pack(side='left')
        self.direct_scan_var = tk.StringVar()
        self.direct_scan_entry = ttk.Entry(search_panel, textvariable=self.direct_scan_var, font=('Segoe UI', 14), width=30)
        self.direct_scan_entry.pack(side='left', padx=15)
        self.direct_scan_entry.focus_set()
        self.direct_scan_entry.bind('<Return>', lambda e: self.procesar_escaneo_directo())

        tk.Label(search_panel, text="O busque por nombre:", bg='white', font=('Segoe UI', 9), fg='gray').pack(side='left', padx=(50, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filtrar_productos)
        self.search_entry = ttk.Entry(search_panel, textvariable=self.search_var, font=('Segoe UI', 10))
        self.search_entry.pack(side='left', fill='x', expand=True)

    def procesar_escaneo_directo(self):
        sn = self.direct_scan_var.get().strip().upper()
        self.direct_scan_var.set("")
        if not sn: return

        reporter = self.reporter_entry.get().strip()
        if not reporter:
            messagebox.showwarning("Faltan Datos", "Indique quién reporta el daño.")
            return

        try:
            sku_db, loc = obtener_info_serial(sn)
            if not sku_db:
                messagebox.showerror("No Encontrado", f"El serial/MAC {sn} no está registrado en el sistema.")
                return
            
            if loc != 'BODEGA':
                messagebox.showerror("Error", f"El equipo {sn} debe estar en BODEGA para reportar daño. Actualmente: {loc}")
                return

            # Confirmación rápida
            nombre_prod = "Equipo"
            if hasattr(self, 'all_products'):
                for p in self.all_products:
                    if p[1] == sku_db:
                        nombre_prod = p[0]
                        break

            if messagebox.askyesno("Confirmar Daño", f"¿Reportar como DAÑADO?\n\nEquipo: {nombre_prod}\nMAC: {sn}"):
                exito, msg = registrar_danado_directo(sku_db, 1, reporter, self.obs_entry.get(), [sn])
                if exito:
                    messagebox.showinfo("Éxito", "Dañado registrado correctamente.")
                    self.cargar_datos_iniciales()
                else:
                    messagebox.showerror("Error", msg)

        except Exception as e:
            logger.error(f"Error en escaneo directo Dañados: {e}")
            messagebox.showerror("Error", f"Fallo al procesar escaneo: {e}")

    def cargar_datos_iniciales(self):
        # UI for Treeview (Manual Selection)
        tree_frame = tk.Frame(self.main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        columns = ('Nombre', 'SKU', 'Stock en Bodega', 'Tipo')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='browse', style='Modern.Treeview')
        
        for col in columns: 
            self.tree.heading(col, text=col)
        
        self.tree.column('Nombre', width=400)
        self.tree.column('SKU', width=120)
        self.tree.column('Stock en Bodega', width=120, anchor='center')
        
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        self.tree.bind('<Double-1>', lambda e: self.abrir_ventana_danado())
        
        try:
            self.all_products = obtener_todos_los_skus_para_movimiento()
            self.filtrar_productos()
        except Exception as e:
            logger.error(f"Error cargando stock Dañados: {e}")

    def filtrar_productos(self, *args):
        search_term = self.search_var.get().lower()
        for item in self.tree.get_children(): self.tree.delete(item)
        
        for p in self.all_products:
            nombre, sku, cant = p
            es_equipo = sku in PRODUCTOS_CON_CODIGO_BARRA
            tipo = "EQUIPO" if es_equipo else "MATERIAL"
            
            if search_term in nombre.lower() or search_term in sku.lower():
                self.tree.insert('', 'end', values=(nombre, sku, cant, tipo))

    def abrir_ventana_danado(self):
        selected = self.tree.selection()
        if not selected: return
        
        nombre, sku, stock, tipo = self.tree.item(selected)['values']
        reporter = self.reporter_entry.get().strip()
        
        if not reporter:
            messagebox.showwarning("Faltan Datos", "Indique quién reporta el daño.")
            return

        self.ventana_accion_danado(sku, nombre, stock, reporter)

    def ventana_accion_danado(self, sku, nombre, stock, reporter):
        vent = tk.Toplevel(self.app.master)
        vent.title("Reportar Daño")
        vent.geometry("500x350")
        vent.configure(bg='white')
        vent.grab_set()

        # Centrar
        x = vent.master.winfo_x() + (vent.master.winfo_width()//2) - (500//2)
        y = vent.master.winfo_y() + (vent.master.winfo_height()//2) - (350//2)
        vent.geometry(f"+{x}+{y}")

        main = tk.Frame(vent, bg='white', padx=30, pady=30)
        main.pack(fill='both', expand=True)

        tk.Label(main, text="Confirmar Reporte de Daño", font=('Segoe UI', 10), bg='white').pack()
        tk.Label(main, text=nombre, font=('Segoe UI', 12, 'bold'), bg='white', fg='#c0392b', wraplength=400).pack(pady=10)
        
        es_equipo = sku in PRODUCTOS_CON_CODIGO_BARRA

        if es_equipo:
            tk.Label(main, text="Escanee Serial/MAC del equipo dañado:", bg='white').pack(pady=(10, 5))
            entry = ttk.Entry(main, font=('Segoe UI', 12))
            entry.pack(fill='x', pady=5)
            entry.focus_set()
            
            def procesar():
                sn = entry.get().strip().upper()
                if not sn: return
                sku_db, loc = obtener_info_serial(sn)
                if sku_db != sku:
                    messagebox.showerror("Error", "El serial no corresponde al producto.")
                    return
                if loc != 'BODEGA':
                    messagebox.showerror("Error", f"El equipo debe estar en BODEGA. Actualmente: {loc}")
                    return
                
                exito, msg = registrar_danado_directo(sku, 1, reporter, self.obs_entry.get(), [sn])
                if exito:
                    vent.destroy()
                    messagebox.showinfo("Éxito", "Dañado registrado.")
                    self.cargar_datos_iniciales()
                else:
                    messagebox.showerror("Error", msg)

            tk.Button(main, text="⚠️ REGISTRAR DAÑO", command=procesar, bg='#c0392b', fg='white', 
                      font=('Segoe UI', 11, 'bold'), relief='flat', pady=10).pack(fill='x', pady=20)
            vent.bind('<Return>', lambda e: procesar())
        else:
            tk.Label(main, text="Cantidad dañada:", bg='white').pack(pady=(10, 5))
            cnt = ttk.Entry(main, font=('Segoe UI', 12), justify='center')
            cnt.insert(0, "1")
            cnt.pack(pady=5)
            cnt.focus_set()

            def procesar():
                try:
                    q = int(cnt.get())
                    if q <= 0 or q > stock: raise ValueError()
                except:
                    messagebox.showerror("Error", "Cantidad inválida.")
                    return
                
                exito, msg = registrar_danado_directo(sku, q, reporter, self.obs_entry.get())
                if exito:
                    vent.destroy()
                    messagebox.showinfo("Éxito", "Dañado registrado.")
                    self.cargar_datos_iniciales()
                else:
                    messagebox.showerror("Error", msg)

            tk.Button(main, text="⚠️ REGISTRAR DAÑO", command=procesar, bg='#c0392b', fg='white', 
                      font=('Segoe UI', 11, 'bold'), relief='flat', pady=10).pack(fill='x', pady=20)
            vent.bind('<Return>', lambda e: procesar())
