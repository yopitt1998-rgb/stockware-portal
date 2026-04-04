from datetime import date
from database import obtener_recordatorios_pendientes

class NotificationService:
    """Service to handle business logic for notifications and reminders."""
    
    @staticmethod
    def get_todays_reminders_message():
        """Retrieve and format a message for today's pending reminders."""
        fecha_hoy = date.today().isoformat()
        recordatorios = obtener_recordatorios_pendientes(fecha_hoy)
        
        if not recordatorios:
            return None
        
        # Filter and count by type
        retornos = [r for r in recordatorios if r[3] == 'RETORNO']
        conciliaciones = [r for r in recordatorios if r[3] == 'CONCILIACION']
        
        if not retornos and not conciliaciones:
            return None
            
        mensaje = "🔔 RECORDATORIOS PENDIENTES PARA HOY:\n\n"
        
        if retornos:
            mensaje += f"🔄 RETORNOS PENDIENTES: {len(retornos)}\n"
            for r in retornos:
                mensaje += f"   • {r[1]} - Paquete {r[2]}\n"
            mensaje += "\n"
        
        if conciliaciones:
            mensaje += f"⚖️ CONCILIACIONES PENDIENTES: {len(conciliaciones)}\n"
            for r in conciliaciones:
                mensaje += f"   • {r[1]} - Paquete {r[2]}\n"
                
        return mensaje
