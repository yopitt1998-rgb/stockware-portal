"""
Sistema de Tooltips para StockWare
Proporciona tooltips informativos al pasar el mouse sobre widgets
"""
import tkinter as tk

class ToolTip:
    """
    Crea un tooltip para un widget dado.
    """
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        
    def on_enter(self, event=None):
        """Programa mostrar el tooltip después del delay"""
        self.schedule()
        
    def on_leave(self, event=None):
        """Cancela y oculta el tooltip"""
        self.unschedule()
        self.hide()
        
    def schedule(self):
        """Programa mostrar el tooltip"""
        self.unschedule()
        self.id = self.widget.after(self.delay, self.show)
        
    def unschedule(self):
        """Cancela mostrar el tooltip"""
        id_temp = self.id
        self.id = None
        if id_temp:
            self.widget.after_cancel(id_temp)
            
    def show(self):
        """Muestra el tooltip"""
        if self.tooltip_window:
            return
            
        # Obtener posición del widget
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        # Crear ventana del tooltip
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        # Crear frame con borde
        frame = tk.Frame(self.tooltip_window, 
                        background="#2c3e50",
                        borderwidth=1,
                        relief="solid")
        frame.pack()
        
        # Crear label con el texto
        label = tk.Label(frame,
                        text=self.text,
                        justify=tk.LEFT,
                        background="#2c3e50",
                        foreground="white",
                        relief="flat",
                        font=("Segoe UI", 9),
                        padx=8,
                        pady=4)
        label.pack()
        
    def hide(self):
        """Oculta el tooltip"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


def create_tooltip(widget, text, delay=500):
    """
    Función helper para crear tooltips fácilmente.
    
    Args:
        widget: El widget al que agregar el tooltip
        text: El texto a mostrar
        delay: Milisegundos antes de mostrar (default: 500)
    
    Returns:
        ToolTip: Instancia del tooltip creado
    """
    return ToolTip(widget, text, delay)


# Diccionario de textos de tooltips comunes
TOOLTIPS = {
    # Dashboard
    "refresh_dashboard": "Actualizar las métricas del dashboard (F5)",
    
    # Inventario
    "nuevo_abasto": "Registrar entrada de material a bodega (Ctrl+N)",
    "salida_movil": "Asignar material a un móvil (Ctrl+S)",
    "retorno_movil": "Devolver material de un móvil a bodega (Ctrl+R)",
    "conciliacion_excel": "Importar y conciliar consumos desde Excel",
    "conciliacion_manual": "Revisar y ajustar consumos manualmente",
    "historial": "Ver historial completo de movimientos",
    "gestionar_abastos": "Ver y editar abastos registrados",
    
    # Auditoría
    "filtrar_audit": "Cargar consumos pendientes de auditoría",
    "importar_excel_audit": "Importar Excel de producción para comparar",
    "validar_audit": "Validar consumos seleccionados y descontar del inventario",
    "limpiar_audit": "Eliminar todos los consumos pendientes",
    
    # Reportes
    "exportar_excel": "Exportar datos a archivo Excel (Ctrl+E)",
    "generar_reporte": "Generar reporte con filtros aplicados",
    
    # Configuración
    "guardar_config": "Guardar cambios de configuración",
    "crear_respaldo": "Crear copia de seguridad de la base de datos",
    "limpiar_bd": "⚠️ PELIGRO: Eliminar todos los movimientos y datos",
    
    # Móviles
    "crear_movil": "Agregar un nuevo móvil al sistema",
    "editar_movil": "Modificar datos del móvil seleccionado",
    "eliminar_movil": "Desactivar móvil (no se puede eliminar si tiene stock)",
    
    # Recordatorios
    "crear_recordatorio": "Crear nuevo recordatorio",
    "completar_recordatorio": "Marcar recordatorio como completado",
    "eliminar_recordatorio": "Eliminar recordatorio",
}
