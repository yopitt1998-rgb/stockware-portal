import tkinter as tk
from tkinter import ttk, messagebox
import winsound
import sys
import os
import threading
from datetime import date

# Añadir el path raíz para importaciones
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from database import get_db_connection, run_query, registrar_movimiento_gui
from gui.styles import Styles

class ReversoConsumoScannerWindow:
    def __init__(self, main_app):
        self.main_app = main_app
        # Compatibilidad: la app puede usar .root o .master como ventana principal
        root_win = getattr(main_app, 'root', None) or getattr(main_app, 'master', None)
        self.window = tk.Toplevel(root_win)
        self.window.title("⏪ Reverso de Consumo")
        self.window.geometry("850x600")
        self.window.configure(bg=Styles.BG_COLOR)
        
        # Make it modal
        self.window.transient(root_win)
        self.window.grab_set()
        
        self.scanned_items = []
        
        self._build_ui()
        self.scanner_input.focus_set()

    def _build_ui(self):
        # Header
        header_frame = tk.Frame(self.window, bg=Styles.PRIMARY_COLOR, pady=15)
        header_frame.pack(fill='x')
        tk.Label(header_frame, text="⏪ Reverso de Consumo (De Consumido a Bodega)", font=('Segoe UI', 16, 'bold'), fg='white', bg=Styles.PRIMARY_COLOR).pack()
        tk.Label(header_frame, text="Escanea los equipos reportados como consumidos para regresarlos al stock", font=('Segoe UI', 10), fg='#E0E0E0', bg=Styles.PRIMARY_COLOR).pack()
        
        # Scanner area
        scan_frame = tk.Frame(self.window, bg=Styles.BG_COLOR, pady=20)
        scan_frame.pack(fill='x', padx=20)
        
        tk.Label(scan_frame, text="Escanea la MAC o Serial:", font=('Segoe UI', 12, 'bold'), bg=Styles.BG_COLOR).pack(side='left', padx=(0, 10))
        
        self.scanner_var = tk.StringVar()
        self.scanner_input = tk.Entry(scan_frame, textvariable=self.scanner_var, font=('Segoe UI', 14), width=25)
        self.scanner_input.pack(side='left', padx=10)
        self.scanner_input.bind('<Return>', self.process_scan)

        self.btn_procesar = tk.Button(scan_frame, text="⚙️ Procesar Retorno", command=self.ejecutar_reverso_batch,
                                   bg=Styles.SUCCESS_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                                   relief='flat', padx=15, pady=5, cursor='hand2', state='disabled')
        self.btn_procesar.pack(side='left', padx=10)
        
        # Status Label
        self.status_label = tk.Label(self.window, text="Esperando escaneo...", font=('Segoe UI', 12), fg=Styles.TEXT_COLOR, bg=Styles.BG_COLOR)
        self.status_label.pack(pady=10)

        # Treeview
        columns = ("#", "Serial/MAC", "SKU", "Estado Anterior", "Resultado")
        self.tree = ttk.Treeview(self.window, columns=columns, show='headings', height=15)
        self.tree.heading("#", text="#")
        self.tree.heading("Serial/MAC", text="Serial/MAC")
        self.tree.heading("SKU", text="SKU")
        self.tree.heading("Estado Anterior", text="Estado Anterior")
        self.tree.heading("Resultado", text="Resultado")
        
        self.tree.column("#", width=50, anchor='center')
        self.tree.column("Serial/MAC", width=200)
        self.tree.column("SKU", width=150, anchor='center')
        self.tree.column("Estado Anterior", width=150, anchor='center')
        self.tree.column("Resultado", width=250, anchor='center')
        
        self.tree.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Tag configuration for colors
        self.tree.tag_configure('success', background='#D4EDDA', foreground='#155724')
        self.tree.tag_configure('warning', background='#FFF3CD', foreground='#856404')
        self.tree.tag_configure('error', background='#F8D7DA', foreground='#721C24')

        # Bindings for deletion
        self.tree.bind('<Double-1>', self.remove_item)
        
        # Help label
        tk.Label(self.window, text="💡 Doble-clic para eliminar un equipo de la lista antes de procesar", 
                 font=('Segoe UI', 9), fg='#666', bg=Styles.BG_COLOR).pack(pady=5)

    def play_sound(self, success=True):
        try:
            if success:
                winsound.MessageBeep(winsound.MB_OK)
            else:
                winsound.MessageBeep(winsound.MB_ICONHAND)
        except:
            pass
            
    def process_scan(self, event=None):
        serial = self.scanner_var.get().strip()
        self.scanner_input.delete(0, tk.END)
        
        if not serial:
            return
            
        if serial in self.scanned_items:
            self.status_label.config(text=f"⚠️ El equipo {serial} ya fue escaneado en esta sesión.", fg='#d32f2f')
            self.play_sound(False)
            return
            
        self.status_label.config(text=f"Buscando {serial}...", fg=Styles.INFO_COLOR)
        threading.Thread(target=self._lookup_serial_async, args=(serial,), daemon=True).start()

    def _lookup_serial_async(self, serial):
        conn = None
        try:
            conn = get_db_connection()
            from config import DB_TYPE
            cursor = conn.cursor(buffered=True) if DB_TYPE == 'MYSQL' else conn.cursor()
            from config import CURRENT_CONTEXT
            sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
            
            cursor.execute("SELECT sku, ubicacion, estado FROM series_registradas WHERE (serial_number = %s OR mac_number = %s) AND sucursal = %s", (serial, serial, sucursal))
            row = cursor.fetchone()
            
            if not row:
                self.window.after(0, self._update_ui_result, serial, "DESCONOCIDO", "DESCONOCIDO", "❌ No encontrado", 'error')
                return
                
            sku, ubicacion, estado = row
            if ubicacion == 'BODEGA':
                self.window.after(0, self._update_ui_result, serial, sku, ubicacion, "⚠️ Ya está en Bodega", 'warning')
                return
            
            # Add to tree as READY
            self.window.after(0, self._add_ready_item, serial, sku, ubicacion)
            
        except Exception as e:
            self.window.after(0, self.status_label.config, {"text": f"❌ Error: {e}", "fg": "red"})
        finally:
            if conn: conn.close()

    def _add_ready_item(self, serial, sku, anterior):
        num = len(self.tree.get_children()) + 1
        self.tree.insert('', 0, values=(num, serial, sku, anterior, "⏳ LISTO PARA PROCESAR"), tags=('warning',))
        self.scanned_items.append(serial)
        self.btn_procesar.config(state='normal')
        self.status_label.config(text=f"✅ Equipo {serial} listo. Haz clic en 'Procesar Retorno'", fg=Styles.SUCCESS_COLOR)
        self.play_sound(True)

    def remove_item(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return
            
        values = self.tree.item(selected_item)['values']
        serial = values[1]
        resultado = values[4]
        
        # Solo permitir borrar los que no han sido procesados o fallaron
        if "✅" in str(resultado):
            return

        if messagebox.askyesno("Confirmar", f"¿Eliminar el equipo {serial} de la lista?"):
            self.tree.delete(selected_item)
            if serial in self.scanned_items:
                self.scanned_items.remove(serial)
            
            if not self.tree.get_children():
                self.btn_procesar.config(state='disabled')
            
            self.status_label.config(text=f"🗑️ Equipo {serial} eliminado de la lista", fg='#666')

    def ejecutar_reverso_batch(self):
        # Procesar todos los que esten en estado "LISTO" o "Pendiente"
        items_to_process = []
        for child in self.tree.get_children():
            values = self.tree.item(child)['values']
            status = str(values[4])
            if "LISTO PARA PROCESAR" in status or "Pendiente" in status:
                items_to_process.append((child, values[1], values[2], values[3]))
        
        if not items_to_process:
            messagebox.showinfo("Información", "No hay ítems Pendientes o Listos para procesar en la lista.", parent=self.window)
            return
        
        self.btn_procesar.config(state='disabled')
        threading.Thread(target=self._process_batch_async, args=(items_to_process,), daemon=True).start()

    def _process_batch_async(self, items):
        conn = None
        try:
            conn = get_db_connection()
            from config import DB_TYPE
            cursor = conn.cursor(buffered=True) if DB_TYPE == 'MYSQL' else conn.cursor()
            from config import CURRENT_CONTEXT
            sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
            from datetime import date
            
            # OPTIMIZACIÓN: Una sola conexión para todo el batch
            for item_id, serial, sku, ubicacion in items:
                try:
                    # 1. Revertir en series_registradas
                    run_query(cursor, "UPDATE series_registradas SET ubicacion = 'BODEGA', estado = 'DISPONIBLE', movil = NULL, paquete = 'NINGUNO' WHERE (serial_number = %s OR mac_number = %s) AND sucursal = %s", (serial, serial, sucursal))
                    
                    # 2. Sincronizar stocks contables
                    # Si estaba en un estado final (Consumido/Faltante/Descarte), sumamos a Bodega
                    if ubicacion in ('CONSUMIDO', 'DESCARTE', 'FALTANTE'):
                        run_query(cursor, "UPDATE productos SET cantidad = cantidad + 1 WHERE sku = %s AND ubicacion = 'BODEGA' AND sucursal = %s", (sku, sucursal))
                    
                    # SI ESTABA EN UNA MÓVIL (ASIGNADO): Restar de la móvil y sumar a Bodega
                    elif str(ubicacion).startswith('Movil') or str(ubicacion).startswith('Móvil'):
                         # Restar de asignacion_moviles (usamos la lógica de ANY package)
                         run_query(cursor, """
                             UPDATE asignacion_moviles SET cantidad = cantidad - 1 
                             WHERE sku_producto = ? AND movil = ? AND sucursal = ? AND cantidad > 0
                             ORDER BY (CASE WHEN paquete = 'NINGUNO' THEN 1 ELSE 0 END) ASC
                             LIMIT 1
                         """, (sku, ubicacion, sucursal))
                         
                         # Sumar a Bodega
                         run_query(cursor, "UPDATE productos SET cantidad = cantidad + 1 WHERE sku = %s AND ubicacion = 'BODEGA' AND sucursal = %s", (sku, sucursal))
                    
                    # 3. LIMPIEZA DE AUDITORÍA (NUEVO)
                    
                    # A. Limpiar en consumos_pendientes (Si existe un reporte de este serial)
                    # Usamos LIKE para encontrar el serial en la lista de seriales_usados
                    try:
                        run_query(cursor, "DELETE FROM consumos_pendientes WHERE (seriales_usados LIKE %s OR seriales_usados = %s) AND sucursal = %s", (f"%{serial}%", serial, sucursal))
                    except Exception as e:
                        logger.warning(f"⚠️ Error limpiando consumos_pendientes para {serial}: {e}")

                    # B. Limpiar en faltantes_registrados
                    try:
                        # Buscar si el serial está en el detalle de faltantes
                        run_query(cursor, "SELECT faltante_id FROM seriales_faltantes_detalle WHERE serial = %s", (serial,))
                        f_row = cursor.fetchone()
                        if f_row:
                            id_faltante = f_row[0]
                            # Eliminar detalle
                            run_query(cursor, "DELETE FROM seriales_faltantes_detalle WHERE serial = %s", (serial,))
                            # Decrementar cabecera
                            run_query(cursor, "UPDATE faltantes_registrados SET cantidad = cantidad - 1 WHERE id = %s", (id_faltante,))
                            # Eliminar cabecera si llegó a 0
                            run_query(cursor, "DELETE FROM faltantes_registrados WHERE id = %s AND cantidad <= 0", (id_faltante,))
                    except Exception as e:
                        logger.warning(f"⚠️ Error limpiando faltantes para {serial}: {e}")

                    # 4. Registrar el movimiento
                    registrar_movimiento_gui(
                        sku, "ENTRADA", 1, None, date.today().isoformat(), "NINGUNO", 
                        observaciones=f"Reverso a Bodega desde {ubicacion} - Serial: {serial}", 
                        seriales=[serial], sucursal_context=sucursal,
                        existing_conn=conn
                    )
                    
                    self.window.after(0, self._finalize_item_ui, item_id, "✅ Reversado a Bodega", 'success')
                except Exception as e:
                    self.window.after(0, self._finalize_item_ui, item_id, f"❌ Error: {e}", 'error')
            
            conn.commit()
            self.window.after(0, self.status_label.config, {"text": "✅ Procesamiento completado", "fg": Styles.SUCCESS_COLOR})

        except Exception as e:
            if conn: conn.rollback()
            self.window.after(0, self.status_label.config, {"text": f"❌ Error crítico: {e}", "fg": "red"})
        finally:
            if conn: conn.close()

    def _finalize_item_ui(self, item_id, resultado, tag):
        values = list(self.tree.item(item_id)['values'])
        values[4] = resultado
        self.tree.item(item_id, values=values, tags=(tag,))
        self.play_sound(tag == 'success')

    def _process_scan_async(self, serial):
        conn = None
        try:
            conn = get_db_connection()
            from config import DB_TYPE
            if DB_TYPE == 'MYSQL':
                cursor = conn.cursor(buffered=True)
            else:
                cursor = conn.cursor()
            
            # Determinar sucursal
            from config import CURRENT_CONTEXT
            sucursal = CURRENT_CONTEXT.get('BRANCH', 'CHIRIQUI')
            
            # 1. Obtener SKU y ubicación REAL del equipo
            cursor.execute("SELECT sku, ubicacion, estado FROM series_registradas WHERE (serial_number = %s OR mac_number = %s) AND sucursal = %s", (serial, serial, sucursal))
            row = cursor.fetchone()
            
            if not row:
                self.window.after(0, self._update_ui_result, serial, "DESCONOCIDO", "DESCONOCIDO", "❌ No encontrado", 'error')
                return
                
            sku, ubicacion, estado = row
            
            if ubicacion == 'BODEGA':
                self.window.after(0, self._update_ui_result, serial, sku, ubicacion, "⚠️ Ya está en Bodega", 'warning')
                return
            
            # 2. Revertir en series_registradas
            run_query(cursor, "UPDATE series_registradas SET ubicacion = 'BODEGA', estado = 'DISPONIBLE', movil = NULL, paquete = 'NINGUNO' WHERE (serial_number = %s OR mac_number = %s) AND sucursal = %s", (serial, serial, sucursal))
            
            # 3. Si estaba fuera de bodega, sumar al stock contable
            if ubicacion in ('CONSUMIDO', 'DESCARTE', 'FALTANTE'):
                run_query(cursor, "UPDATE productos SET cantidad = cantidad + 1 WHERE sku = %s AND ubicacion = 'BODEGA' AND sucursal = %s", (sku, sucursal))
            
            # 4. LIMPIEZA DE AUDITORÍA (NUEVO)
            
            # A. Consumos Pendientes
            try:
                run_query(cursor, "DELETE FROM consumos_pendientes WHERE (seriales_usados LIKE %s OR seriales_usados = %s) AND sucursal = %s", (f"%{serial}%", serial, sucursal))
            except Exception as e:
                logger.warning(f"⚠️ Error limpiando consumos_pendientes para {serial}: {e}")

            # B. Faltantes
            try:
                run_query(cursor, "SELECT faltante_id FROM seriales_faltantes_detalle WHERE serial = %s", (serial,))
                f_row = cursor.fetchone()
                if f_row:
                    id_f = f_row[0]
                    run_query(cursor, "DELETE FROM seriales_faltantes_detalle WHERE serial = %s", (serial,))
                    run_query(cursor, "UPDATE faltantes_registrados SET cantidad = cantidad - 1 WHERE id = %s", (id_f,))
                    run_query(cursor, "DELETE FROM faltantes_registrados WHERE id = %s AND cantidad <= 0", (id_f,))
            except Exception as e:
                logger.warning(f"⚠️ Error limpiando faltantes para {serial}: {e}")

            # 5. Registrar el movimiento
            registrar_movimiento_gui(
                sku, 
                "ENTRADA", 
                1, 
                None, 
                date.today().isoformat(), 
                "NINGUNO", 
                observaciones=f"Reverso a Bodega desde {ubicacion} - Serial: {serial}", 
                seriales=[serial],
                sucursal_context=sucursal,
                existing_conn=conn
            )
            
            conn.commit()
            self.window.after(0, self._update_ui_result, serial, sku, ubicacion, "✅ Reversado a Bodega", 'success')
            self.scanned_items.append(serial)
            
        except Exception as e:
            if conn: conn.rollback()
            self.window.after(0, self._update_ui_result, serial, "ERROR", "ERROR", f"❌ Error interno: {e}", 'error')
        finally:
            if conn: conn.close()

    def _update_ui_result(self, serial, sku, anterior, resultado, tag):
        self.play_sound(tag == 'success')
        # Insert string at top
        num = len(self.tree.get_children()) + 1
        self.tree.insert('', 0, values=(num, serial, sku, anterior, resultado), tags=(tag,))
        
        if tag == 'success':
            self.status_label.config(text=f"✅ Equipo {serial} retornado exitosamente a Bodega", fg='#2e7d32')
        elif tag == 'warning':
            self.status_label.config(text=f"⚠️ Equipo {serial} ya se encontraba en Bodega", fg='#ef6c00')
        else:
            self.status_label.config(text=f"❌ Error al procesar equipo {serial}", fg='#d32f2f')
