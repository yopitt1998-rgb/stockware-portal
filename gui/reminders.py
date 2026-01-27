import tkinter as tk
import threading

from tkinter import ttk
from datetime import date, timedelta
from database import (
    obtener_recordatorios_todos, 
    eliminar_recordatorios_completados, 
    marcar_recordatorio_completado,

)
from gui.utils import mostrar_mensaje_emergente
from config import COLORS

class RemindersTab(tk.Frame):
    def __init__(self, master=None, inventory_tab=None):
        super().__init__(master)
        self.master = master
        self.inventory_tab = inventory_tab # Reference to inventory tab for actions
        self.colors = COLORS
        self.current_reminder_date = date.today()
        
        self.create_widgets()

    def create_widgets(self):
        # Frame principal
        self.configure(bg='#f8f9fa')
        
        # Header
        header_frame = tk.Frame(self, bg=self.colors['primary'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="🔔 RECORDATORIOS AUTOMÁTICOS", 
                font=('Segoe UI', 16, 'bold'), bg=self.colors['primary'], fg='white').pack(pady=20)
        
        # Frame de navegación de fechas
        date_frame = tk.Frame(self, bg='#E3F2FD', padx=20, pady=15)
        date_frame.pack(fill='x')
        
        tk.Button(date_frame, text="◀️ Anterior", command=self.previous_day,
                 bg=self.colors['secondary'], fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=15, pady=8).pack(side='left')
        
        self.date_label = tk.Label(date_frame, text="", font=('Segoe UI', 14, 'bold'), 
                                  bg='#E3F2FD', fg='#2c3e50')
        self.date_label.pack(side='left', padx=20)
        
        tk.Button(date_frame, text="Hoy", command=self.go_to_today,
                 bg=self.colors['success'], fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=15, pady=8).pack(side='left', padx=5)
        
        tk.Button(date_frame, text="Siguiente ▶️", command=self.next_day,
                 bg=self.colors['secondary'], fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=15, pady=8).pack(side='left')
        
        # Frame de información del día
        info_frame = tk.Frame(self, bg='#F3E5F5', padx=20, pady=15)
        info_frame.pack(fill='x')
        
        self.day_info_label = tk.Label(info_frame, text="", font=('Segoe UI', 12), 
                                      bg='#F3E5F5', fg='#2c3e50', justify='left')
        self.day_info_label.pack(anchor='w')
        
        # Frame de botones de acción
        action_frame = tk.Frame(self, bg='#FFF3E0', padx=20, pady=10)
        action_frame.pack(fill='x')
        
        # Botón de actualizar
        tk.Button(action_frame, text="🔄 Actualizar", 
                 command=self.load_reminders,
                 bg=self.colors['success'], fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=15, pady=8, cursor='hand2').pack(side='left', padx=5)
        
        # Botón de limpiar completados
        tk.Button(action_frame, text="🧹 Limpiar Completados", 
                 command=self.limpiar_recordatorios_completados,
                 bg=self.colors['warning'], fg='white', font=('Segoe UI', 10, 'bold'),
                 relief='flat', bd=0, padx=15, pady=8, cursor='hand2').pack(side='left', padx=5)
        
        # Frame de checklist
        checklist_frame = tk.Frame(self, bg='#f8f9fa', padx=20, pady=20)
        checklist_frame.pack(fill='both', expand=True)
        
        # Canvas y scrollbar para checklist
        self.reminders_canvas = tk.Canvas(checklist_frame, bg='#f8f9fa')
        scrollbar = ttk.Scrollbar(checklist_frame, orient="vertical", command=self.reminders_canvas.yview)
        self.checklist_inner_frame = tk.Frame(self.reminders_canvas, bg='#f8f9fa')
        
        self.reminders_canvas.create_window((0, 0), window=self.checklist_inner_frame, anchor="nw")
        self.reminders_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.reminders_canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        def on_mousewheel(event):
            self.reminders_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        self.reminders_canvas.bind("<MouseWheel>", on_mousewheel)
        self.checklist_inner_frame.bind("<MouseWheel>", on_mousewheel)
        
        self.checklist_inner_frame.bind("<Configure>", lambda e: self.reminders_canvas.configure(scrollregion=self.reminders_canvas.bbox("all")))
        
        # Cargar recordatorios iniciales
        self.load_reminders()

    def limpiar_recordatorios_completados(self):
        """Limpia los recordatorios completados"""
        if eliminar_recordatorios_completados():
            mostrar_mensaje_emergente(self.master, "Éxito", "Recordatorios completados eliminados.", "success")
            self.load_reminders()
        else:
            mostrar_mensaje_emergente(self.master, "Error", "No se pudieron eliminar los recordatorios completados.", "error")

    def load_reminders(self):
        """Carga recordatorios para la fecha actual en un hilo separado"""
        self.date_label.config(text=self.current_reminder_date.strftime("%A, %d de %B de %Y"))
        fecha_iso = self.current_reminder_date.isoformat()
        
        def run_load():
            try:
                recordatorios = obtener_recordatorios_todos(fecha_iso)
                self.master.after(0, lambda: self._aplicar_recordatorios_ui(recordatorios))
            except Exception as e:
                print(f"⚠️ Error al cargar recordatorios: {e}")

        threading.Thread(target=run_load, daemon=True).start()

    def _aplicar_recordatorios_ui(self, recordatorios):
        """Aplica los recordatorios a la UI (hilo principal)"""
        if not self.winfo_exists():
            return

        for widget in self.checklist_inner_frame.winfo_children():
            widget.destroy()
        
        if not recordatorios:
            tk.Label(self.checklist_inner_frame, text="✅ No hay recordatorios para esta fecha", 
                    font=('Segoe UI', 12), bg='#f8f9fa', fg=self.colors['success']).pack(pady=50)
            self.day_info_label.config(text="✅ No hay recordatorios para hoy")
            return
        
        recordatorios_por_movil = {}
        for id_recordatorio, movil, paquete, tipo_recordatorio, fecha, completado in recordatorios:
            if movil not in recordatorios_por_movil:
                recordatorios_por_movil[movil] = []
            recordatorios_por_movil[movil].append((id_recordatorio, paquete, tipo_recordatorio, completado))
        
        row = 0
        for movil, recordatorios_list in recordatorios_por_movil.items():
            movil_frame = tk.Frame(self.checklist_inner_frame, bg='white', relief='raised', 
                                 borderwidth=1, padx=15, pady=10)
            movil_frame.grid(row=row, column=0, sticky='ew', padx=10, pady=5)
            movil_frame.columnconfigure(1, weight=1)
            
            tk.Label(movil_frame, text=f"🚚 {movil}", font=('Segoe UI', 12, 'bold'),
                    bg='white', fg=self.colors['primary']).grid(row=0, column=0, sticky='w', columnspan=2)
            
            for i, (id_recordatorio, paquete, tipo_recordatorio, completado) in enumerate(recordatorios_list, 1):
                task_text = f"{'✅' if completado else '🔄' if tipo_recordatorio == 'RETORNO' else '⚖️'} {tipo_recordatorio}: Paquete {paquete}"
                
                task_frame = tk.Frame(movil_frame, bg='white')
                task_frame.grid(row=i, column=0, columnspan=2, sticky='ew', pady=2)
                
                var = tk.BooleanVar(value=bool(completado))
                cb = tk.Checkbutton(task_frame, text=task_text, variable=var,
                                  font=('Segoe UI', 10), bg='white', fg='#666' if completado else '#2c3e50',
                                  command=lambda id_r=id_recordatorio, v=var, m=movil, p=paquete, t=tipo_recordatorio: 
                                  self.marcar_recordatorio_completado(id_r, v, m, p, t))
                cb.pack(side='left')
                
                if not completado:
                    # Determine target function based on type
                    # Using inventory_tab reference to call the methods
                    action_method = self.inventory_tab.abrir_ventana_retorno_movil if (self.inventory_tab and tipo_recordatorio == 'RETORNO') else \
                                   (self.inventory_tab.abrir_ventana_consiliacion if self.inventory_tab and tipo_recordatorio == 'CONCILIACION' else None)
                    
                    if not action_method and self.inventory_tab is None:
                        # Fallback if inventory_tab is not provided, maybe log warning
                        pass
                    
                    btn_text = "Abrir Retorno" if tipo_recordatorio == 'RETORNO' else "Abrir Conciliación"
                    
                    if action_method:
                        btn = tk.Button(task_frame, text=btn_text, 
                                      command=lambda m=movil, p=paquete, method=action_method: self.open_reminder_action(m, p, method),
                                      bg=self.colors['info'], fg='white', font=('Segoe UI', 8, 'bold'),
                                      relief='flat', bd=0, padx=8, pady=3)
                        btn.pack(side='right', padx=(10, 0))
            
            row += 1
        
        total_recordatorios = len(recordatorios)
        recordatorios_pendientes = sum(1 for r in recordatorios if not r[5])
        retornos = sum(1 for r in recordatorios if r[3] == 'RETORNO')
        conciliaciones = sum(1 for r in recordatorios if r[3] == 'CONCILIACION')
        
        info_text = f"📅 {self.current_reminder_date.strftime('%d/%m/%Y')}\n"
        info_text += f"📋 Total recordatorios: {total_recordatorios}\n"
        info_text += f"⏳ Pendientes: {recordatorios_pendientes}\n"
        info_text += f"✅ Completados: {total_recordatorios - recordatorios_pendientes}\n"
        info_text += f"🔄 Retornos: {retornos}\n"
        info_text += f"⚖️ Conciliaciones: {conciliaciones}"
        self.day_info_label.config(text=info_text)
        
        self.reminders_canvas.configure(scrollregion=self.reminders_canvas.bbox("all"))

    def marcar_recordatorio_completado(self, id_recordatorio, var, movil, paquete, tipo_recordatorio):
        """Marca un recordatorio como completado o descompletado"""
        if var.get():
            if marcar_recordatorio_completado(id_recordatorio):
                mostrar_mensaje_emergente(self.master, "Éxito", f"Recordatorio de {tipo_recordatorio} para {movil} - Paquete {paquete} marcado como completado.", "success")
                self.load_reminders()
            else:
                var.set(False)
                mostrar_mensaje_emergente(self.master, "Error", "No se pudo marcar el recordatorio como completado.", "error")
        else:
            var.set(True)
            mostrar_mensaje_emergente(self.master, "Información", "Los recordatorios completados no se pueden desmarcar.", "info")

    def previous_day(self):
        self.current_reminder_date -= timedelta(days=1)
        self.load_reminders()

    def next_day(self):
        self.current_reminder_date += timedelta(days=1)
        self.load_reminders()

    def go_to_today(self):
        self.current_reminder_date = date.today()
        self.load_reminders()

    def open_reminder_action(self, movil, paquete, method):
        """Abrir acción de recordatorio con parámetros predefinidos"""
        # Call the method (opens the window)
        if method:
            # We need to open the window with parameters. 
            # The original implementation called self.abrir_ventana_retorno_movil() then found the window and set values.
            # Here we can do the same but we need to rely on the window title convention.
            method()
            
            # Find the window (We assume it's a Toplevel in self.master)
            # This logic assumes the title conventions are maintained in InventoryTab
            target_title_retorno = "🔄 Retorno de Móvil"
            target_title_conciliacion = "⚖️ Consiliación"
            
            target_title = None
            if "retorno" in str(method).lower(): # Heuristic match
                 target_title = target_title_retorno
            elif "consiliacion" in str(method).lower():
                 target_title = target_title_conciliacion
            
            # Since method is a bound method, we can check __name__
            if method.__name__ == 'abrir_ventana_retorno_movil':
                target_title = target_title_retorno
            elif method.__name__ == 'abrir_ventana_consiliacion':
                target_title = target_title_conciliacion
                
            if target_title:
                self.set_window_params(target_title, movil, paquete)

    def set_window_params(self, window_title, movil, paquete):
        """Helper to find the window and set params"""
        # Wait a bit for window to open? Tkinter synchronous normally.
         # Buscar la ventana recién abierta y establecer los valores
        for window in self.master.winfo_children():
            if isinstance(window, tk.Toplevel) and window_title in window.title():
                # Buscar los comboboxes en la ventana
                for widget in window.winfo_children():
                    if isinstance(widget, tk.Frame) or isinstance(widget, ttk.Frame): # Support both
                        # Recursively search might be better but let's stick to original depth logic or slight improve
                        self.fill_combos_in_container(widget, movil, paquete)
                break
                
    def fill_combos_in_container(self, container, movil, paquete):
        for child in container.winfo_children():
            if isinstance(child, ttk.Combobox):
                # How to identify which combo? Text label previous?
                # Original code checked `str(widget)` which is unreliable if name depends on auto id.
                # Better to check variable names or position? Hard.
                # But original code checked if "Móvil Origen:" in str(widget). Wait, str(widget) gives .!toplevel.!frame...
                # It does NOT give the label text. The original code:
                # if "Móvil Origen:" in str(widget):
                # This seems wrong in original code unless widget was a specific named frame or Label packed in it?
                # Actually, original code:
                # if isinstance(widget, tk.Frame):
                #    for child in widget.winfo_children():
                #       if isinstance(child, ttk.Combobox):
                #           if "Móvil Origen:" in str(widget): 
                # This suggests 'widget' (the Frame) string representation contained "Móvil Origen:"? Unlikely.
                # Maybe I misread 1200-1300 block.
                # Let's look at 1282: if "Móvil Origen:" in str(widget):
                # If the frame has a label with that text, it doesn't appear in str(widget).
                # Unless they check children of widget for label?
                # Ah, maybe they meant to check label next to it?
                pass
            elif isinstance(child, tk.Frame) or isinstance(child, ttk.Frame):
                self.fill_combos_in_container(child, movil, paquete)

        # Re-implementing correctly:
        # We need to find the labels inside the container and see if they match, then find the combobox.
        # Or just try to set any combobox with values that match?
        # Let's traverse children, if we see a Label with "Móvil", the next Combobox is likely the one.
        
        children = container.winfo_children()
        for i, child in enumerate(children):
            if isinstance(child, tk.Label) or isinstance(child, ttk.Label):
                text = child.cget("text")
                if "Móvil" in text:
                    # Look for next combobox
                    for j in range(i+1, len(children)):
                        if isinstance(children[j], ttk.Combobox):
                            children[j].set(movil)
                            children[j].event_generate("<<ComboboxSelected>>")
                            break
                elif "Paquete" in text:
                    for j in range(i+1, len(children)):
                        if isinstance(children[j], ttk.Combobox):
                            children[j].set(paquete)
                            children[j].event_generate("<<ComboboxSelected>>")
                            break
