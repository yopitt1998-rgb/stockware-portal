import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from .styles import Styles
from .utils import darken_color, mostrar_mensaje_emergente
from database import (
    obtener_todos_los_skus_para_movimiento,
    registrar_movimiento_gui,
    obtener_abastos_resumen,
    obtener_detalle_abasto,
    actualizar_movimiento_abasto
)

class AbastoWindow:
    def __init__(self, master_app, mode='registrar'):
        self.master_app = master_app
        self.master = master_app.master
        self.mode = mode # 'registrar' or 'gestionar'
        
        self.window = tk.Toplevel(self.master)
        self.window.title("📦 Gestión de Abastos")
        self.window.geometry("1000x800")
        try:
             self.window.state('zoomed')
        except:
             pass
        self.window.configure(bg='#f8f9fa')
        
        self.create_widgets()
        
        # Select initial tab based on mode
        if self.mode == 'gestionar':
            self.notebook.select(self.tab_history)
        
    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self.window, bg=Styles.PRIMARY_COLOR, height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📦 GESTIÓN DE ABASTOS E INVENTARIO INICIAL", 
                font=('Segoe UI', 18, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=20)
        
        # Notebook
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Tab 1: Registrar
        self.tab_register = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(self.tab_register, text="➕ Registrar Nuevo Abasto")
        self.setup_register_tab()
        
        # Tab 2: Historial
        self.tab_history = ttk.Frame(self.notebook, style='Modern.TFrame')
        self.notebook.add(self.tab_history, text="📜 Historial de Abastos")
        self.setup_history_tab()
        
    def setup_register_tab(self):
        # --- Formulario ---
        form_frame = tk.Frame(self.tab_register, bg='#f8f9fa', pady=10)
        form_frame.pack(fill='x')
        
        # Fecha
        tk.Label(form_frame, text="Fecha (YYYY-MM-DD):", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=(20, 5))
        self.fecha_entry = tk.Entry(form_frame, width=15, font=('Segoe UI', 10))
        self.fecha_entry.insert(0, date.today().isoformat())
        self.fecha_entry.pack(side='left', padx=5)
        
        # Referencia
        tk.Label(form_frame, text="Referencia / ID Abasto:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=(20, 5))
        self.ref_entry = tk.Entry(form_frame, width=20, font=('Segoe UI', 10))
        self.ref_entry.pack(side='left', padx=5)
        
        # Observaciones
        tk.Label(form_frame, text="Observaciones:", font=('Segoe UI', 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=(20, 5))
        self.obs_entry = tk.Entry(form_frame, width=30, font=('Segoe UI', 10))
        self.obs_entry.pack(side='left', padx=5)
        
        # Botón Guardar
        btn_save = tk.Button(form_frame, text="💾 Guardar Abasto", command=self.guardar_abasto,
                           bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 10, 'bold'), relief='flat', padx=15, pady=5)
        btn_save.pack(side='right', padx=20)
        
        # --- Lista de Productos ---
        list_frame = tk.Frame(self.tab_register, bg='#f8f9fa')
        list_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Canvas & Scrollbar
        canvas = tk.Canvas(list_frame, bg='white')
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg='white')
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel
        def _on_mousewheel(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except tk.TclError:
                pass
        
        # Bind only when mouse enters the widget to prevent global scrolling issues
        canvas.bind('<Enter>', lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all("<MouseWheel>"))
        
        self.populate_products_list()
        
    def populate_products_list(self):
        # Limpiar
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        # Headers
        headers = ["Producto", "SKU", "Stock Actual", "Cantidad a Ingresar"]
        for i, h in enumerate(headers):
            tk.Label(self.scrollable_frame, text=h, font=('Segoe UI', 10, 'bold'), bg='#e9ecef', padx=10, pady=5).grid(row=0, column=i, sticky='ew')
            
        # Data
        productos = obtener_todos_los_skus_para_movimiento() # [(nombre, sku, cant), ...]
        
        self.entry_vars = {}
        
        for idx, (nombre, sku, stock) in enumerate(productos, start=1):
            bg_color = 'white' if idx % 2 == 0 else '#f1f3f5'
            
            tk.Label(self.scrollable_frame, text=nombre, bg=bg_color, anchor='w', padx=10, pady=5).grid(row=idx, column=0, sticky='ew')
            tk.Label(self.scrollable_frame, text=sku, bg=bg_color, anchor='c', padx=10, pady=5).grid(row=idx, column=1, sticky='ew')
            tk.Label(self.scrollable_frame, text=str(stock), bg=bg_color, anchor='c', padx=10, pady=5).grid(row=idx, column=2, sticky='ew')
            
            entry = tk.Entry(self.scrollable_frame, width=10, justify='center')
            entry.grid(row=idx, column=3, padx=10, pady=2)
            self.entry_vars[sku] = entry
            
    def guardar_abasto(self):
        fecha = self.fecha_entry.get().strip()
        ref = self.ref_entry.get().strip()
        obs = self.obs_entry.get().strip()
        
        if not fecha:
            mostrar_mensaje_emergente(self.window, "Error", "La fecha es obligatoria", "error")
            return
        if not ref:
            mostrar_mensaje_emergente(self.window, "Error", "La referencia es obligatoria (ej: ABS-001)", "error")
            return
            
        items_to_save = []
        for sku, entry in self.entry_vars.items():
            val = entry.get().strip()
            if val:
                try:
                    qty = int(val)
                    if qty > 0:
                        items_to_save.append((sku, qty))
                except ValueError:
                    continue
                    
        if not items_to_save:
            mostrar_mensaje_emergente(self.window, "Aviso", "No ha ingresado cantidades para ningún producto", "warning")
            return
            
        confirm = messagebox.askyesno("Confirmar Abasto", 
                                    f"Se registrará el abasto '{ref}' con {len(items_to_save)} items.\n\n¿Desea continuar?")
        if not confirm:
            return
            
        success_count = 0
        errors = []
        
        for sku, qty in items_to_save:
            ok, msg = registrar_movimiento_gui(
                sku, 'ABASTO', qty, None, fecha, 
                documento_referencia=ref, observaciones=obs
            )
            if ok:
                success_count += 1
            else:
                errors.append(f"{sku}: {msg}")
                
        if errors:
            msg_res = f"Se registraron {success_count} items.\nErrores:\n" + "\n".join(errors)
            mostrar_mensaje_emergente(self.window, "Resultado Parcial", msg_res, "warning")
        else:
            mostrar_mensaje_emergente(self.window, "Éxito", "Abasto registrado correctamente.", "success")
            # Limpiar entradas
            self.ref_entry.delete(0, tk.END)
            self.obs_entry.delete(0, tk.END)
            for entry in self.entry_vars.values():
                entry.delete(0, tk.END)
                
            # Actualizar historial
            self.load_history()
            
            # Recargar stocks en lista (visual feedback)
            self.populate_products_list()
            
    def setup_history_tab(self):
        # Controls
        ctrl_frame = tk.Frame(self.tab_history, bg='#f8f9fa', pady=10)
        ctrl_frame.pack(fill='x')
        
        tk.Button(ctrl_frame, text="🔄 Actualizar Lista", command=self.load_history,
                bg=Styles.INFO_COLOR, fg='white', relief='flat', padx=10).pack(side='left', padx=20)
                
        # Treeview
        columns = ("Fecha", "Referencia", "Items", "Total Unidades", "Última Modificación")
        self.tree_history = ttk.Treeview(self.tab_history, columns=columns, show='headings')
        
        for col in columns:
            self.tree_history.heading(col, text=col)
            self.tree_history.column(col, anchor='center')
            
        self.tree_history.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Scrollbar
        sb = ttk.Scrollbar(self.tab_history, orient="vertical", command=self.tree_history.yview)
        self.tree_history.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        
        self.tree_history.bind("<Double-1>", self.on_history_double_click)
        
        self.load_history()
        
    def load_history(self):
        for item in self.tree_history.get_children():
            self.tree_history.delete(item)
            
        data = obtener_abastos_resumen() # [(fecha, ref, items, total, last_mod), ...]
        for row in data:
            self.tree_history.insert('', 'end', values=row)
            
    def on_history_double_click(self, event):
        item_id = self.tree_history.selection()
        if not item_id: return
        
        vals = self.tree_history.item(item_id[0])['values']
        fecha = vals[0]
        ref = vals[1]
        
        AbastoDetailWindow(self.window, fecha, ref, self.load_history)

class AbastoDetailWindow:
    def __init__(self, parent, fecha, referencia, callback_refresh):
        self.top = tk.Toplevel(parent)
        self.top.title(f"Detalle Abasto: {referencia}")
        self.top.geometry("800x600")
        self.top.grab_set()
        
        self.fecha = fecha
        self.referencia = referencia
        self.callback_refresh = callback_refresh
        
        self.create_ui()
        self.load_details()
        
    def create_ui(self):
        tk.Label(self.top, text=f"Detalle de Abasto: {self.referencia}", font=('Segoe UI', 14, 'bold')).pack(pady=10)
        tk.Label(self.top, text=f"Fecha: {self.fecha}").pack()
        
        # Treeview for items
        cols = ("ID", "Producto", "SKU", "Cantidad", "Ref", "Obs")
        self.tree = ttk.Treeview(self.top, columns=cols, show='headings')
        self.tree.heading("ID", text="ID"); self.tree.column("ID", width=50)
        self.tree.heading("Producto", text="Producto"); self.tree.column("Producto", width=200)
        self.tree.heading("SKU", text="SKU"); self.tree.column("SKU", width=100)
        self.tree.heading("Cantidad", text="Cantidad"); self.tree.column("Cantidad", width=80)
        self.tree.heading("Ref", text="Ref"); self.tree.column("Ref", width=100)
        
        self.tree.pack(fill='both', expand=True, padx=20, pady=10)
        self.tree.bind("<Double-1>", self.edit_item)
        
        tk.Label(self.top, text="Doble clic en un item para editar cantidad o referencia.", fg='gray').pack(pady=5)
        
    def load_details(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        
        detalles = obtener_detalle_abasto(self.fecha, self.referencia)
        # [(id, nombre, sku, cantidad, ref, obs), ...]
        
        for d in detalles:
            self.tree.insert('', 'end', values=d)
            
    def edit_item(self, event):
        item = self.tree.selection()
        if not item: return
        vals = self.tree.item(item[0])['values']
        
        id_mov = vals[0]
        sku = vals[2]
        old_qty = vals[3]
        old_ref = vals[4]
        
        # Edit Dialog
        edit_win = tk.Toplevel(self.top)
        edit_win.title("Editar Item")
        edit_win.geometry("300x250")
        edit_win.transient(self.top)
        edit_win.grab_set()
        
        tk.Label(edit_win, text=f"SKU: {sku}").pack(pady=5)
        
        tk.Label(edit_win, text="Nueva Cantidad:").pack()
        e_qty = tk.Entry(edit_win)
        e_qty.insert(0, str(old_qty))
        e_qty.pack()
        
        tk.Label(edit_win, text="Nueva Referencia:").pack()
        e_ref = tk.Entry(edit_win)
        e_ref.insert(0, str(old_ref))
        e_ref.pack()
        
        def save():
            try:
                new_q = int(e_qty.get())
                new_r = e_ref.get()
                
                # Check if ref changed, might need to update ALL items of this abasto?
                # User requirement: "review and edit all previously entered abastos".
                # Usually reference change applies to the group, but here we edit item level. 
                # If they want to rename the whole abasto, we'd need a bulk update.
                # For now, let's allow individual item update.
                
                ok, msg = actualizar_movimiento_abasto(id_mov, new_q, new_r)
                if ok:
                    messagebox.showinfo("Éxito", "Actualizado correctamente")
                    self.load_details()
                    self.callback_refresh()
                    edit_win.destroy()
                else:
                    messagebox.showerror("Error", msg)
            except ValueError:
                messagebox.showerror("Error", "Cantidad inválida")
                
        tk.Button(edit_win, text="Guardar Cambios", command=save, bg=Styles.SUCCESS_COLOR, fg='white').pack(pady=20)
