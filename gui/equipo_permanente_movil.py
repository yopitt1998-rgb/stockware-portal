import tkinter as tk
from tkinter import ttk, messagebox
from .styles import Styles
from .utils import mostrar_mensaje_emergente


class EquipoPermanenteMovilDialog(tk.Toplevel):
    """
    Diálogo para gestionar la asignación de equipo/material PERMANENTE a cada móvil.
    El material asignado:
      - Descuenta de bodega inmediatamente.
      - Se registra en consumos_pendientes (visible en Render).
      - No genera retorno (es definitivo).
      - Si se elimina, el stock regresa a bodega.
    """

    ACCENT  = '#00695C'   # teal oscuro
    ACCENT2 = '#004D40'   # teal más oscuro (header)
    BG      = '#f0faf8'
    ROW_ODD  = '#ffffff'
    ROW_EVEN = '#e8f5e9'

    def __init__(self, master):
        super().__init__(master)
        self.title("🔧 Equipo / Material Permanente por Móvil")
        self.geometry("1000x680")
        self.configure(bg=self.BG)
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()

        # Centrar ventana
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width()  // 2) - 500
        y = master.winfo_rooty() + (master.winfo_height() // 2) - 340
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

        self._cargar_datos_maestros()
        self._build_ui()
        self._cargar_tabla()

    # ── Datos maestros ────────────────────────────────────────────────────────

    def _cargar_datos_maestros(self):
        try:
            from database import obtener_nombres_moviles, obtener_todos_los_skus_para_movimiento
            self.moviles = obtener_nombres_moviles() or []
            prods_raw = obtener_todos_los_skus_para_movimiento() or []
            # prods_raw → lista de (nombre, sku, cantidad)
            self.productos_list = prods_raw
            self.prod_labels = [f"{p[1]} – {p[0]}" for p in prods_raw]
        except Exception as e:
            self.moviles = []
            self.productos_list = []
            self.prod_labels = []
            print(f"[EquipoPermanente] Error cargando maestros: {e}")

    # ── Construcción UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=self.ACCENT2, height=65)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr,
                 text="🔧  EQUIPO / MATERIAL PERMANENTE POR MÓVIL",
                 font=('Segoe UI', 15, 'bold'),
                 bg=self.ACCENT2, fg='white').pack(pady=16)

        # Nota informativa
        nota = tk.Frame(self, bg='#FFF8E1', pady=8, padx=20)
        nota.pack(fill='x')
        tk.Label(nota,
                 text="⚠️  Este material no genera retorno. Al asignarlo se descuenta de bodega y se registra "
                      "en el consumo del portal. Si lo elimina, el stock regresa a bodega.",
                 font=('Segoe UI', 9), bg='#FFF8E1', fg='#795548', justify='left').pack(anchor='w')

        # ── Formulario de asignación ─────────────────────────────────────────
        form_outer = tk.LabelFrame(self,
                                   text="  ➕ Nueva Asignación Permanente  ",
                                   font=('Segoe UI', 10, 'bold'),
                                   bg=self.BG, fg=self.ACCENT,
                                   padx=15, pady=12,
                                   relief='groove', bd=2)
        form_outer.pack(fill='x', padx=20, pady=(12, 6))

        form = tk.Frame(form_outer, bg=self.BG)
        form.pack(fill='x')

        # Fila 1: Móvil | Producto (con búsqueda)
        tk.Label(form, text="Móvil:", font=('Segoe UI', 10, 'bold'),
                 bg=self.BG).grid(row=0, column=0, sticky='w', padx=(0, 8))
        self.var_movil = tk.StringVar()
        self.combo_movil = ttk.Combobox(form, textvariable=self.var_movil,
                                        values=self.moviles, state='readonly', width=22)
        if self.moviles:
            self.combo_movil.current(0)
        self.combo_movil.grid(row=0, column=1, sticky='w', padx=(0, 20))

        tk.Label(form, text="Producto (SKU – Nombre):", font=('Segoe UI', 10, 'bold'),
                 bg=self.BG).grid(row=0, column=2, sticky='w', padx=(0, 8))
        self.var_prod = tk.StringVar()
        self.combo_prod = ttk.Combobox(form, textvariable=self.var_prod,
                                       values=self.prod_labels,
                                       width=40, state='normal')
        if self.prod_labels:
            self.combo_prod.current(0)
        self.combo_prod.grid(row=0, column=3, sticky='w', padx=(0, 20))
        self.combo_prod.bind('<KeyRelease>', self._filtrar_productos)

        # Fila 2: Cantidad | Paquete | Observaciones
        tk.Label(form, text="Cantidad:", font=('Segoe UI', 10, 'bold'),
                 bg=self.BG).grid(row=1, column=0, sticky='w', pady=(10, 0), padx=(0, 8))
        self.entry_cant = ttk.Entry(form, width=8, font=('Segoe UI', 10))
        self.entry_cant.insert(0, "1")
        self.entry_cant.grid(row=1, column=1, sticky='w', padx=(0, 20), pady=(10, 0))

        tk.Label(form, text="Visible en Paquete:", font=('Segoe UI', 10, 'bold'),
                 bg=self.BG).grid(row=1, column=2, sticky='w', pady=(10, 0), padx=(0, 8))
        self.var_paquete = tk.StringVar(value='AMBOS')
        combo_paq = ttk.Combobox(form, textvariable=self.var_paquete,
                                  values=['AMBOS', 'PAQUETE A', 'PAQUETE B', 'PAQUETE DOMINGO'],
                                  state='readonly', width=18)
        combo_paq.grid(row=1, column=3, sticky='w', padx=(0, 20), pady=(10, 0))

        tk.Label(form, text="Observaciones:", font=('Segoe UI', 10, 'bold'),
                 bg=self.BG).grid(row=2, column=0, sticky='w', pady=(10, 0), padx=(0, 8))
        self.entry_obs = ttk.Entry(form, width=65, font=('Segoe UI', 10))
        self.entry_obs.grid(row=2, column=1, columnspan=3, sticky='ew', pady=(10, 0))

        # Botón asignar
        tk.Button(form, text="➕ Asignar Permanentemente",
                  command=self._asignar,
                  bg=self.ACCENT, fg='white',
                  font=('Segoe UI', 10, 'bold'),
                  relief='flat', padx=20, pady=8, cursor='hand2').grid(
            row=3, column=0, columnspan=4, pady=(14, 0))

        # ── Tabla de asignaciones ────────────────────────────────────────────
        tbl_outer = tk.LabelFrame(self,
                                  text="  📋 Asignaciones Permanentes Registradas  ",
                                  font=('Segoe UI', 10, 'bold'),
                                  bg=self.BG, fg=self.ACCENT,
                                  padx=10, pady=8,
                                  relief='groove', bd=2)
        tbl_outer.pack(fill='both', expand=True, padx=20, pady=(4, 15))

        # Filtro por móvil en la tabla
        filter_frame = tk.Frame(tbl_outer, bg=self.BG)
        filter_frame.pack(fill='x', pady=(0, 6))
        tk.Label(filter_frame, text="Filtrar por Móvil:", font=('Segoe UI', 9, 'bold'),
                 bg=self.BG).pack(side='left')
        self.var_filtro_movil = tk.StringVar(value='TODOS')
        filtro_vals = ['TODOS'] + self.moviles
        combo_filtro = ttk.Combobox(filter_frame, textvariable=self.var_filtro_movil,
                                    values=filtro_vals, state='readonly', width=22)
        combo_filtro.pack(side='left', padx=8)
        combo_filtro.bind('<<ComboboxSelected>>', lambda e: self._cargar_tabla())

        tk.Button(filter_frame, text="🔄 Actualizar",
                  command=self._cargar_tabla,
                  bg='#546E7A', fg='white', font=('Segoe UI', 9, 'bold'),
                  relief='flat', padx=12, pady=3, cursor='hand2').pack(side='left', padx=4)

        # Treeview
        cols = ('ID', 'Móvil', 'SKU', 'Nombre Producto', 'Cantidad', 'Paquete',
                'Fecha Asignación', 'Observaciones')
        tbl_frame = tk.Frame(tbl_outer, bg=self.BG)
        tbl_frame.pack(fill='both', expand=True)

        self.tree = ttk.Treeview(tbl_frame, columns=cols, show='headings',
                                  style='Modern.Treeview')

        col_widths = [40, 120, 90, 220, 70, 90, 140, 200]
        for col, w in zip(cols, col_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w,
                             anchor='center' if w <= 100 else 'w')
        self.tree.column('ID', width=40, anchor='center')

        vsb = ttk.Scrollbar(tbl_frame, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(tbl_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tbl_frame.rowconfigure(0, weight=1)
        tbl_frame.columnconfigure(0, weight=1)

        # Tags de color alternado
        self.tree.tag_configure('odd',  background=self.ROW_ODD)
        self.tree.tag_configure('even', background=self.ROW_EVEN)

        # Menú contextual (clic derecho)
        ctx = tk.Menu(self, tearoff=0)
        ctx.add_command(
            label="🗑️  Eliminar asignación (revierte stock a bodega)",
            command=self._eliminar_seleccionado)
        self.tree.bind('<Button-3>', lambda e: self._show_ctx(e, ctx))

        # Botón eliminar también en la parte inferior
        tk.Button(tbl_outer,
                  text="🗑️  Eliminar Seleccionado  (Revierte Stock a Bodega)",
                  command=self._eliminar_seleccionado,
                  bg='#c0392b', fg='white',
                  font=('Segoe UI', 9, 'bold'),
                  relief='flat', padx=15, pady=5, cursor='hand2').pack(pady=(8, 0))

    # ── Filtro de productos por escritura ─────────────────────────────────────

    def _filtrar_productos(self, event=None):
        texto = self.var_prod.get().lower()
        filtrados = [lbl for lbl in self.prod_labels if texto in lbl.lower()]
        self.combo_prod['values'] = filtrados if filtrados else self.prod_labels
        if filtrados:
            try:
                self.combo_prod.event_generate('<Down>')
            except Exception:
                pass

    # ── Cargar tabla ─────────────────────────────────────────────────────────

    def _cargar_tabla(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            from database import obtener_equipos_permanentes
            filtro = self.var_filtro_movil.get()
            movil_filtro = None if filtro == 'TODOS' else filtro
            rows = obtener_equipos_permanentes(movil=movil_filtro)
        except Exception as e:
            mostrar_mensaje_emergente(self, "Error", f"No se pudo cargar la tabla:\n{e}", "error")
            return

        for i, row in enumerate(rows):
            # row: (id, movil, sku, nombre_producto, cantidad, paquete,
            #       fecha_asignacion, observaciones, sucursal)
            rid, movil, sku, nombre, cant, paquete, fecha, obs, suc = row
            fecha_fmt = str(fecha)[:16] if fecha else '-'
            tag = 'odd' if i % 2 == 0 else 'even'
            self.tree.insert('', tk.END,
                             values=(rid, movil, sku, nombre, cant,
                                     paquete or 'AMBOS', fecha_fmt, obs or ''),
                             tags=(tag,))

    # ── Asignar ──────────────────────────────────────────────────────────────

    def _asignar(self):
        movil = self.var_movil.get().strip()
        prod_label = self.var_prod.get().strip()
        cant_str = self.entry_cant.get().strip()
        paquete = self.var_paquete.get().strip()
        obs = self.entry_obs.get().strip() or None

        if not movil:
            mostrar_mensaje_emergente(self, "Validación", "Debe seleccionar un móvil.", "error")
            return
        if not prod_label:
            mostrar_mensaje_emergente(self, "Validación", "Debe seleccionar un producto.", "error")
            return

        # Extraer SKU del label "SKU – Nombre"
        sku = prod_label.split(' – ')[0].strip()
        if not sku:
            mostrar_mensaje_emergente(self, "Validación",
                                      "No se pudo identificar el SKU del producto seleccionado.", "error")
            return

        if not cant_str.isdigit() or int(cant_str) <= 0:
            mostrar_mensaje_emergente(self, "Validación",
                                      "La cantidad debe ser un número entero mayor a 0.", "error")
            return

        cantidad = int(cant_str)

        confirmar = messagebox.askyesno(
            "Confirmar Asignación Permanente",
            f"¿Asignar permanentemente al móvil '{movil}'?\n\n"
            f"  SKU:      {sku}\n"
            f"  Cantidad: {cantidad}\n"
            f"  Paquete:  {paquete}\n\n"
            f"⚠️ Esto descontará {cantidad} unidad(es) de bodega\n"
            f"y registrará el consumo. NO generará retorno.",
            parent=self
        )
        if not confirmar:
            return

        try:
            from database import asignar_equipo_permanente
            exito, msg = asignar_equipo_permanente(
                movil=movil, sku=sku, cantidad=cantidad,
                paquete=paquete, observaciones=obs
            )
            if exito:
                mostrar_mensaje_emergente(self, "✅ Éxito", msg, "success")
                self.entry_cant.delete(0, tk.END)
                self.entry_cant.insert(0, "1")
                self.entry_obs.delete(0, tk.END)
                self._cargar_tabla()
            else:
                mostrar_mensaje_emergente(self, "Error", msg, "error")
        except Exception as e:
            mostrar_mensaje_emergente(self, "Error inesperado", str(e), "error")

    # ── Eliminar seleccionado ─────────────────────────────────────────────────

    def _eliminar_seleccionado(self):
        sel = self.tree.selection()
        if not sel:
            mostrar_mensaje_emergente(self, "Selección",
                                      "Seleccione una fila de la tabla para eliminar.", "info")
            return

        vals = self.tree.item(sel[0])['values']
        rid, movil, sku, nombre, cant = vals[0], vals[1], vals[2], vals[3], vals[4]

        confirmar = messagebox.askyesno(
            "Confirmar Eliminación",
            f"¿Eliminar la asignación permanente?\n\n"
            f"  Móvil:    {movil}\n"
            f"  Producto: {nombre} ({sku})\n"
            f"  Cantidad: {cant}\n\n"
            f"✅ El stock ({cant} unidad(es)) será revertido a bodega.",
            icon='warning', parent=self
        )
        if not confirmar:
            return

        try:
            from database import eliminar_equipo_permanente
            exito, msg = eliminar_equipo_permanente(int(rid))
            if exito:
                mostrar_mensaje_emergente(self, "✅ Eliminado", msg, "success")
                self._cargar_tabla()
            else:
                mostrar_mensaje_emergente(self, "Error", msg, "error")
        except Exception as e:
            mostrar_mensaje_emergente(self, "Error inesperado", str(e), "error")

    # ── Menú contextual helper ────────────────────────────────────────────────

    def _show_ctx(self, event, menu):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            menu.post(event.x_root, event.y_root)
