import threading
import tkinter as tk
from tkinter import ttk
from utils.logger import get_logger

logger = get_logger(__name__)

def mostrar_cargando_async(ventana, funcion_carga, callback_exito, master_app=None):
    """
    Ejecuta una función de carga en un hilo secundario y muestra un loading en la ventana dada.
    
    Args:
        ventana: tk.Toplevel o ventana donde mostrar el loading.
        funcion_carga: Función que retorna los datos (se ejecuta en thread).
        callback_exito: Función que recibe los datos (se ejecuta en main thread).
        master_app: Opcional, referencia a la app principal para logs.
    """
    frame_carga = tk.Frame(ventana, bg=ventana.cget('bg'))
    frame_carga.pack(fill='both', expand=True)
    
    content_frame = tk.Frame(frame_carga, bg=ventana.cget('bg'))
    content_frame.pack(expand=True)
    
    tk.Label(content_frame, text="🔄", font=('Segoe UI', 30), 
            bg=ventana.cget('bg'), fg='#7f8c8d').pack(pady=10)
    tk.Label(content_frame, text="Cargando datos...", font=('Segoe UI', 12), 
            bg=ventana.cget('bg'), fg='#7f8c8d').pack()
    
    def run_thread():
        try:
            import time; time.sleep(0.1) 
            datos = funcion_carga()
            if ventana.winfo_exists():
                ventana.after(0, lambda: _finalizar_carga(ventana, frame_carga, callback_exito, datos))
        except Exception as e:
            logger.error(f"Error async: {e}")
            import traceback; traceback.print_exc()
            if ventana.winfo_exists():
                ventana.after(0, lambda: _manejar_error_carga(ventana, e))

    threading.Thread(target=run_thread, daemon=True).start()

def _finalizar_carga(ventana, frame_carga, callback_exito, datos):
    if not ventana.winfo_exists(): return
    frame_carga.destroy()
    callback_exito(datos)

def _manejar_error_carga(ventana, error):
    mostrar_mensaje_emergente(ventana, "Error", f"Error cargando datos: {error}", "error")
    ventana.destroy()


def darken_color(color, factor=0.8):
    """Oscurece un color hexadecimal"""
    if color.startswith('#'):
        color = color[1:]
    try:
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        darker = tuple(max(0, int(c * factor)) for c in rgb)
        return f"#{darker[0]:02x}{darker[1]:02x}{darker[2]:02x}"
    except ValueError:
        return color

def mostrar_mensaje_emergente(master, titulo, mensaje, tipo="info"):
    """Muestra un mensaje emergente moderno - No roba el foco y se cierra automáticamente"""
    try:
        ventana_mensaje = tk.Toplevel(master)
    except Exception:
        # Fallback if master is not valid or destroyed
        return

    ventana_mensaje.title(titulo)
    ventana_mensaje.geometry("400x200")
    ventana_mensaje.resizable(False, False)
    ventana_mensaje.transient(master)
    ventana_mensaje.configure(bg='#f8f9fa')
    
    # Centrar la ventana
    ventana_mensaje.update_idletasks()
    try:
        x = (ventana_mensaje.winfo_screenwidth() // 2) - (400 // 2)
        y = (ventana_mensaje.winfo_screenheight() // 2) - (200 // 2)
        ventana_mensaje.geometry(f"400x200+{x}+{y}")
    except Exception:
        pass
    
    # Configurar color según el tipo
    if tipo == "error":
        color_fondo = "#FFEBEE"
        color_texto = "#D32F2F"
        icono = "❌"
    elif tipo == "warning":
        color_fondo = "#FFF3E0"
        color_texto = "#E65100"
        icono = "⚠️"
    elif tipo == "success":
        color_fondo = "#E8F5E8"
        color_texto = "#388E3C"
        icono = "✅"
    else:  # info
        color_fondo = "#E3F2FD"
        color_texto = "#1976D2"
        icono = "ℹ️"
    
    frame_principal = tk.Frame(ventana_mensaje, bg=color_fondo, padx=20, pady=20)
    frame_principal.pack(fill='both', expand=True)
    
    # Icono y mensaje
    frame_contenido = tk.Frame(frame_principal, bg=color_fondo)
    frame_contenido.pack(fill='both', expand=True)
    
    tk.Label(frame_contenido, text=icono, font=('Segoe UI', 24), bg=color_fondo).pack(side=tk.LEFT, padx=(0, 15))
    
    frame_texto = tk.Frame(frame_contenido, bg=color_fondo)
    frame_texto.pack(side=tk.LEFT, fill='both', expand=True)
    
    tk.Label(frame_texto, text=titulo, font=('Segoe UI', 12, 'bold'), 
            bg=color_fondo, fg=color_texto, justify=tk.LEFT).pack(anchor='w')
    tk.Label(frame_texto, text=mensaje, font=('Segoe UI', 10), 
            bg=color_fondo, fg=color_texto, justify=tk.LEFT, wraplength=280).pack(anchor='w', pady=(5, 0))
            
    # Botón de cerrar
    tk.Button(frame_principal, text="Cerrar", command=ventana_mensaje.destroy,
             bg='white', fg=color_texto, font=('Segoe UI', 9, 'bold'),
             relief='flat', bd=0, padx=15, pady=5).pack(anchor='e', pady=(15, 0))

    # Auto-cierre
    ventana_mensaje.after(3000, ventana_mensaje.destroy)

