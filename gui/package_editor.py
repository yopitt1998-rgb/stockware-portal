import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from config import PAQUETES_MATERIALES, save_custom_packages
import copy
from gui.styles import Styles

class PackageEditorDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("📦 Configurar Contenido y Progreso de Paquetes")
        self.geometry("750x620")
        self.configure(bg='#f8f9fa')
        self.transient(master)
        self.grab_set()
        
        # Load products for names mapping
        try:
            from database import obtener_todos_los_skus_para_movimiento
            prods = obtener_todos_los_skus_para_movimiento()
            self.prod_map = {p[1]: p[0] for p in prods}
            self.all_products_list = prods
        except Exception as e:
            print(f"Error cargando productos maestros: {e}")
            self.prod_map = {}
            self.all_products_list = []
            
        # Working copy
        self.pack_data = copy.deepcopy(PAQUETES_MATERIALES)
        
        self.create_widgets()
        
        if "PAQUETE A" in self.pack_data:
            self.combo_pack.set("PAQUETE A")
            self.load_package("PAQUETE A")
        elif self.pack_data:
            first = list(self.pack_data.keys())[0]
            self.combo_pack.set(first)
            self.load_package(first)

    def create_widgets(self):
        header = tk.Frame(self, bg=Styles.PRIMARY_COLOR, pady=15)
        header.pack(fill='x')
        tk.Label(header, text="⚙️ Configuración de Contenido y Progreso de Paquetes", 
                 font=('Segoe UI', 14, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack()
                 
        top_frame = tk.Frame(self, bg='#f8f9fa', pady=10, padx=20)
        top_frame.pack(fill='x')
        
        tk.Label(top_frame, text="Seleccione un Paquete:", bg='#f8f9fa', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(0,10))
        
        self.combo_pack = ttk.Combobox(top_frame, values=list(self.pack_data.keys()), state='readonly', width=30)
        self.combo_pack.pack(side='left')
        self.combo_pack.bind("<<ComboboxSelected>>", lambda e: self.load_package(self.combo_pack.get()))
        
        # main list
        list_frame = tk.Frame(self, bg='#f8f9fa', padx=20, pady=10)
        list_frame.pack(fill='both', expand=True)
        
        columns = ('SKU', 'Nombre', 'Cantidad Objetivo')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        self.tree.heading('SKU', text='SKU')
        self.tree.heading('Nombre', text='Nombre Producto')
        self.tree.heading('Cantidad Objetivo', text='Cantidad Objetivo (100%)', anchor='center')
        
        self.tree.column('SKU', width=120)
        self.tree.column('Nombre', width=300)
        self.tree.column('Cantidad Objetivo', width=150, anchor='center')
        self.tree.pack(fill='both', expand=True, side='left')
        
        scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        scroll.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scroll.set)
        
        self.tree.bind("<Double-1>", self.editar_item)
        
        # Action list buttons
        action_list_frame = tk.Frame(self, bg='#f8f9fa', padx=20, pady=5)
        action_list_frame.pack(fill='x')
        
        tk.Button(action_list_frame, text="➕ Agregar Producto", command=self.agregar_producto,
                  bg='#3498db', fg='white', font=('Segoe UI', 9, 'bold'),
                  relief='flat', padx=12, pady=6, cursor='hand2').pack(side='left', padx=5)
                  
        tk.Button(action_list_frame, text="❌ Quitar Producto", command=self.quitar_producto,
                  bg='#e74c3c', fg='white', font=('Segoe UI', 9, 'bold'),
                  relief='flat', padx=12, pady=6, cursor='hand2').pack(side='left', padx=5)

        tk.Button(action_list_frame, text="✏️ Editar Cantidad", command=lambda: self.editar_item(None),
                  bg='#f39c12', fg='white', font=('Segoe UI', 9, 'bold'),
                  relief='flat', padx=12, pady=6, cursor='hand2').pack(side='left', padx=5)
        
        # text hint
        tk.Label(self, text="💡 Estos cambios modifican el progreso en Salida y determinan qué productos mostrar al auditar Retornos.",
                 bg='#e8f0fe', fg='#1967d2', font=('Segoe UI', 9), pady=5).pack(fill='x', padx=20, pady=(10, 5))
                 
        # btn frame
        btn_frame = tk.Frame(self, bg='#f8f9fa', pady=15)
        btn_frame.pack(fill='x')
        
        tk.Button(btn_frame, text="✅ Guardar Cambios", command=self.guardar,
                  bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                  padx=20, pady=8, relief='flat').pack(side='right', padx=20)
                  
        tk.Button(btn_frame, text="❌ Cancelar", command=self.destroy,
                  bg=Styles.ACCENT_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                  padx=20, pady=8, relief='flat').pack(side='right')

    def load_package(self, pkg_name):
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        items = self.pack_data.get(pkg_name, [])
        for sku, cant in items:
            nombre = self.prod_map.get(sku, "Desconocido / Compartido / No en DB")
            self.tree.insert('', 'end', values=(sku, nombre, cant))

    def agregar_producto(self):
        pkg_name = self.combo_pack.get()
        if not pkg_name:
            messagebox.showwarning("Advertencia", "Por favor seleccione un paquete primero.")
            return
            
        # Modal dialogue to add a product
        add_win = tk.Toplevel(self)
        add_win.title("➕ Agregar Producto al Paquete")
        add_win.geometry("480x260")
        add_win.resizable(False, False)
        add_win.configure(bg='#f8f9fa')
        add_win.transient(self)
        add_win.grab_set()
        
        # Center relative to parent
        x = self.winfo_rootx() + (self.winfo_width() // 2) - 240
        y = self.winfo_rooty() + (self.winfo_height() // 2) - 130
        add_win.geometry(f"+{x}+{y}")
        
        tk.Label(add_win, text="Seleccione el Producto:", bg='#f8f9fa', font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=30, pady=(20, 5))
        
        # Load fresh list if not present
        if not hasattr(self, 'all_products_list') or not self.all_products_list:
            try:
                from database import obtener_todos_los_skus_para_movimiento
                self.all_products_list = obtener_todos_los_skus_para_movimiento()
                self.prod_map = {p[1]: p[0] for p in self.all_products_list}
            except Exception as e:
                print(f"Error cargando productos maestros: {e}")
                self.all_products_list = []
                
        options = [f"{p[1]} - {p[0]}" for p in self.all_products_list]
        if not options:
            options = ["No hay productos registrados en la BD"]
            
        prod_var = tk.StringVar()
        combo_prod = ttk.Combobox(add_win, textvariable=prod_var, values=options, state='readonly', width=50)
        combo_prod.pack(padx=30, pady=5)
        if options and options[0] != "No hay productos registrados en la BD":
            combo_prod.set(options[0])
            
        tk.Label(add_win, text="Cantidad Objetivo (100%):", bg='#f8f9fa', font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=30, pady=(15, 5))
        
        cant_entry = ttk.Entry(add_win, width=15, font=('Segoe UI', 10))
        cant_entry.pack(anchor='w', padx=30, pady=5)
        cant_entry.insert(0, "1")
        
        def confirmar():
            prod_sel = prod_var.get()
            if not prod_sel or prod_sel == "No hay productos registrados en la BD":
                messagebox.showerror("Error", "Debe seleccionar un producto válido.")
                return
                
            sku = prod_sel.split(" - ")[0].strip()
            cant_str = cant_entry.get().strip()
            
            if not cant_str.isdigit() or int(cant_str) < 0:
                messagebox.showerror("Error", "La cantidad debe ser un número entero mayor o igual a 0.")
                return
                
            qty = int(cant_str)
            
            # Verify if already in package
            current_items = self.pack_data.get(pkg_name, [])
            exists = False
            new_list = []
            
            for s, c in current_items:
                if s == sku:
                    exists = True
                    if messagebox.askyesno("Producto Existente", f"El producto {sku} ya existe en el paquete.\n¿Desea sobrescribir su cantidad con {qty}?"):
                        new_list.append((s, qty))
                    else:
                        new_list.append((s, c))
                else:
                    new_list.append((s, c))
                    
            if not exists:
                new_list.append((sku, qty))
                
            self.pack_data[pkg_name] = new_list
            self.load_package(pkg_name)
            add_win.destroy()
            
        btn_confirmar = tk.Button(add_win, text="🚀 Agregar al Paquete", command=confirmar,
                                  bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 10, 'bold'),
                                  relief='flat', padx=20, pady=6, cursor='hand2')
        btn_confirmar.pack(pady=20)

    def quitar_producto(self):
        pkg_name = self.combo_pack.get()
        if not pkg_name:
            messagebox.showwarning("Advertencia", "Por favor seleccione un paquete primero.")
            return
            
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selección", "Por favor, seleccione un producto de la lista para quitarlo.")
            return
            
        item_id = selected[0]
        vals = self.tree.item(item_id, 'values')
        sku, nombre, cant = vals
        
        if messagebox.askyesno("Confirmar", f"¿Está seguro que desea quitar el producto '{nombre}' ({sku}) del paquete '{pkg_name}'?"):
            current_items = self.pack_data.get(pkg_name, [])
            new_list = [(s, c) for s, c in current_items if s != sku]
            self.pack_data[pkg_name] = new_list
            self.load_package(pkg_name)

    def editar_item(self, event=None):
        if event:
            item_id = self.tree.identify_row(event.y)
        else:
            selected = self.tree.selection()
            item_id = selected[0] if selected else None
            
        if not item_id:
            if not event:
                messagebox.showwarning("Selección", "Por favor, seleccione un producto de la lista para editar su cantidad.")
            return
            
        vals = self.tree.item(item_id, 'values')
        sku, nombre, cant_actual = vals
        
        nueva_cant = simpledialog.askinteger("Editar Cantidad", 
                                             f"SKU: {sku}\nNombre: {nombre}\nNueva cantidad objetivo:",
                                             initialvalue=int(cant_actual), parent=self, minvalue=0)
        if nueva_cant is not None and nueva_cant >= 0:
            self.tree.item(item_id, values=(sku, nombre, nueva_cant))
            
            # Update memory dict
            pkg_name = self.combo_pack.get()
            # find and replace
            new_list = []
            for s, c in self.pack_data[pkg_name]:
                if s == sku:
                    new_list.append((s, nueva_cant))
                else:
                    new_list.append((s, c))
            self.pack_data[pkg_name] = new_list

    def guardar(self):
        if messagebox.askyesno("Confirmar", "¿Desea aplicar y guardar la configuración de progreso de estos paquetes?"):
            PAQUETES_MATERIALES.clear()
            PAQUETES_MATERIALES.update(self.pack_data)
            save_custom_packages()
            messagebox.showinfo("Éxito", "Configuración de paquetes actualizada correctamente.")
            self.destroy()
