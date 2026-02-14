import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from .styles import Styles
from .utils import mostrar_mensaje_emergente
from database import get_db_connection, run_query

class ProductsTab(tk.Frame):
    def __init__(self, master, main_app):
        super().__init__(master)
        self.main_app = main_app
        self.configure(bg='#f8f9fa')
        
        self.create_widgets()
        self.cargar_productos()
        
    def create_widgets(self):
        # --- HEADER ---
        header_frame = tk.Frame(self, bg=Styles.PRIMARY_COLOR, height=60)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📦 GESTIÓN DE PRODUCTOS Y CÓDIGOS DE BARRA", 
                font=('Segoe UI', 14, 'bold'), bg=Styles.PRIMARY_COLOR, fg='white').pack(side='left', padx=20)

        # --- CONTROLES SUPERIORES ---
        controls_frame = tk.Frame(self, bg='#f8f9fa', pady=10)
        controls_frame.pack(fill='x', padx=20)
        
        tk.Label(controls_frame, text="🔍 Buscar:", bg='#f8f9fa', font=('Segoe UI', 10, 'bold')).pack(side='left')
        self.entry_search = tk.Entry(controls_frame, width=30)
        self.entry_search.pack(side='left', padx=5)
        self.entry_search.bind('<KeyRelease>', self.filtrar_productos)
        
        button_frame = tk.Frame(controls_frame, bg='#f8f9fa')
        button_frame.pack(side='right', padx=15)

        tk.Button(button_frame, text="✏️ Asignar Código de Barra", command=self.abrir_dialogo_edicion,
                 bg=Styles.ACCENT_COLOR, fg='white', relief='flat', font=('Segoe UI', 10, 'bold'), padx=15).pack(side='left', padx=5)
        
        # --- TREEVIEW ---
        tree_frame = tk.Frame(self, bg='#f8f9fa')
        tree_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('ID', 'SKU', 'Nombre', 'Stock Bodega', 'Código de Barra', 'Ubicación')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        self.tree.heading('ID', text='ID')
        self.tree.heading('SKU', text='SKU')
        self.tree.heading('Nombre', text='Nombre Producto')
        self.tree.heading('Stock Bodega', text='Stock Bodega')
        self.tree.heading('Código de Barra', text='Código de Barra (Escanear)')
        self.tree.heading('Ubicación', text='Ubicación')
        
        self.tree.column('ID', width=40, anchor='center')
        self.tree.column('SKU', width=100, anchor='center')
        self.tree.column('Nombre', width=250)
        self.tree.column('Stock Bodega', width=80, anchor='center')
        self.tree.column('Código de Barra', width=200, anchor='center') # Destacado
        self.tree.column('Ubicación', width=80, anchor='center')
        
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Bindeos
        self.tree.bind('<Double-1>', self.on_double_click)
        
    def cargar_productos(self):
        # Limpiar
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Obtener productos (solo BODEGA para simplificar vista, o todos agrupados)
            # Mostraremos productos únicos por SKU preferiblemente, mostrando stock total o bodega
            query = "SELECT id, sku, nombre, cantidad, codigo_barra_maestro, ubicacion FROM productos WHERE ubicacion = 'BODEGA' ORDER BY nombre"
            run_query(cursor, query)
            self.productos_cache = cursor.fetchall()
            
            self.filtrar_productos()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando productos: {e}")
        finally:
            conn.close()

    def filtrar_productos(self, event=None):
        filtro = self.entry_search.get().lower()
        
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        for p in self.productos_cache:
            # p: id, sku, nombre, cantidad, codigo_barra, ubicacion
            nombre = str(p[2]).lower()
            sku = str(p[1]).lower()
            barcode = str(p[4]).lower() if p[4] else ""
            
            if filtro in nombre or filtro in sku or filtro in barcode:
                # Formatear None -> ""
                valores = list(p)
                if valores[4] is None: valores[4] = "" # Codigo barra vacio string
                
                self.tree.insert('', 'end', values=valores)

    def on_double_click(self, event):
        self.abrir_dialogo_edicion()

    def abrir_dialogo_edicion(self):
        item = self.tree.selection()
        if not item:
            mostrar_mensaje_emergente(self, "Selección Requerida", "Por favor, seleccione un producto de la lista primero.", "warning")
            return
        
        valores = self.tree.item(item[0], 'values')
        # valores: ID, SKU, Nombre, Stock, Barcode, Ubicacion
        
        sku = valores[1]
        nombre = valores[2]
        barcode_actual = valores[4]
        
        # Crear Diálogo POPUP
        dialog = tk.Toplevel(self)
        dialog.title("✏️ Asignar Código de Barra")
        dialog.geometry("500x300")
        dialog.configure(bg='white')
        dialog.transient(self)
        dialog.grab_set()
        
        # Centrar
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 500) // 2
        y = (dialog.winfo_screenheight() - 300) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # UI Diálogo
        tk.Label(dialog, text="Asignar Código de Barra", font=('Segoe UI', 14, 'bold'), bg='white', fg=Styles.PRIMARY_COLOR).pack(pady=15)
        
        info_frame = tk.Frame(dialog, bg='#f8f9fa', padx=10, pady=10)
        info_frame.pack(fill='x', padx=20)
        
        tk.Label(info_frame, text=f"Producto: {nombre}", font=('Segoe UI', 11, 'bold'), bg='#f8f9fa').pack(anchor='w')
        tk.Label(info_frame, text=f"SKU: {sku}", font=('Segoe UI', 10), bg='#f8f9fa', fg='#666').pack(anchor='w')
        
        tk.Label(dialog, text="👇 Escanee o escriba el código aquí:", font=('Segoe UI', 10), bg='white').pack(pady=(20, 5))
        
        entry_barcode = tk.Entry(dialog, font=('Segoe UI', 14), justify='center', width=30, bg='#e3f2fd')
        entry_barcode.pack(pady=5)
        entry_barcode.insert(0, barcode_actual)
        entry_barcode.select_range(0, tk.END)
        entry_barcode.focus_set()
        
        def guardar(event=None):
            nuevo_codigo = entry_barcode.get().strip()
            
            # NORMALIZAR código escaneado (convertir caracteres problemáticos del scanner)
            if nuevo_codigo:
                nuevo_codigo = nuevo_codigo.replace('´', '-')
                nuevo_codigo = nuevo_codigo.replace('`', '-')
                nuevo_codigo = nuevo_codigo.replace('′', '-')
                nuevo_codigo = nuevo_codigo.upper()
            
            # Guardar en BD usando actualizar_codigo_barra_maestro
            from database import actualizar_codigo_barra_maestro
            
            exito, mensaje = actualizar_codigo_barra_maestro(sku, nuevo_codigo)
            
            if exito:
                mostrar_mensaje_emergente(self, "Actualizado", mensaje, "success")
                dialog.destroy()
                self.cargar_productos()
            else:
                messagebox.showerror("Error", mensaje, parent=dialog)
        
        tk.Button(dialog, text="💾 GUARDAR CODIGO", command=guardar,
                 bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'), 
                 relief='flat', padx=20, pady=10).pack(pady=20)
        
        entry_barcode.bind('<Return>', guardar)
