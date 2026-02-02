import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import subprocess
from dotenv import load_dotenv

# Configuración de colores
COLORS = {
    'primary': '#2c3e50',    # Azul oscuro elegante
    'secondary': '#3498db',  # Azul claro
    'accent': '#e74c3c',     # Rojo
    'bg': '#ecf0f1',         # Gris claro
    'card': '#ffffff',       # Blanco
    'text': '#2c3e50'
}

class BranchLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("StockWare - Selección de Sucursal")
        self.root.geometry("500x400")
        self.root.configure(bg=COLORS['bg'])
        self.root.resizable(False, False)
        
        # Centrar ventana
        self.center_window()
        
        # Cargar variables de entorno base
        self.load_base_env()
        
        self.create_widgets()
        
    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
    def load_base_env(self):
        # Determinar ruta del .env
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
            
        dotenv_path = os.path.join(application_path, '.env')
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path)
            
    def create_widgets(self):
        # Frame principal
        main_frame = tk.Frame(self.root, bg=COLORS['bg'])
        main_frame.pack(expand=True, fill='both', padx=40, pady=40)
        
        # Título
        lbl_title = tk.Label(main_frame, text="Bienvenido a StockWare", 
                            font=("Segoe UI", 24, "bold"), 
                            bg=COLORS['bg'], fg=COLORS['primary'])
        lbl_title.pack(pady=(0, 10))
        
        lbl_subtitle = tk.Label(main_frame, text="Seleccione la sucursal para iniciar sesión", 
                               font=("Segoe UI", 12), 
                               bg=COLORS['bg'], fg="#7f8c8d")
        lbl_subtitle.pack(pady=(0, 30))
        
        # Botones de Sucursal
        btn_frame = tk.Frame(main_frame, bg=COLORS['bg'])
        btn_frame.pack(fill='x', pady=20)
        
        # Botón Chiriquí (Default)
        self.create_branch_btn(btn_frame, "David / Chiriquí", "🏢", 
                             self.launch_chiriqui, COLORS['secondary'])
                             
        # Separador
        tk.Frame(btn_frame, height=20, bg=COLORS['bg']).pack()
        
        # Botón Santiago
        self.create_branch_btn(btn_frame, "Santiago", "🚛", 
                             self.launch_santiago, COLORS['success'] if 'success' in COLORS else '#27ae60')

        # Footer
        lbl_footer = tk.Label(main_frame, text="v1.1 - Multi-Sucursal", 
                             font=("Segoe UI", 8), 
                             bg=COLORS['bg'], fg="#95a5a6")
        lbl_footer.pack(side='bottom', pady=20)

    def create_branch_btn(self, parent, text, icon, command, color):
        btn = tk.Button(parent, text=f"{icon}  {text}", 
                       font=("Segoe UI", 14),
                       bg=color, fg="white",
                       activebackground=color, activeforeground="white",
                       relief="flat", cursor="hand2",
                       command=command,
                       pady=10)
        btn.pack(fill='x', ipady=5)
        
        # Efecto Hover simple
        def on_enter(e): btn.config(bg=self.adjust_color_lightness(color, 0.9))
        def on_leave(e): btn.config(bg=color)
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        
    def adjust_color_lightness(self, color, factor):
        # Función simple para oscurecer color Hex
        # (Omitida implementación compleja, retornamos el mismo o un gris oscuro para simplificar si falla)
        return color # Placeholder
        
    def launch_chiriqui(self):
        self.launch_app("inventario_db") # Nombre original o el que está en .env
        
    def launch_santiago(self):
        self.launch_app("inventario_santiago")
        
    def launch_app(self, db_name):
        try:
            # Establecer variable de entorno para la DB
            # IMPORTANTE: Esto debe hacerse antes de importar config
            os.environ["MYSQL_DATABASE_OVERRIDE"] = db_name
            os.environ["CURRENT_BRANCH_NAME"] = "Santiago" if "santiago" in db_name.lower() else "David"
            
            self.root.destroy()
            
            # Importar e iniciar la app principal
            # Hacemos el import AQUÍ, no arriba, para que tome las variables de entorno
            import app_inventario
            app_inventario.main()
            
        except Exception as e:
            messagebox.showerror("Error de Inicio", f"No se pudo iniciar la aplicación:\n{e}")
            sys.exit(1)

if __name__ == "__main__":
    app = BranchLauncher()
    app.root.mainloop()
