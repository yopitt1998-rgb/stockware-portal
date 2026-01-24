import tkinter as tk
from tkinter import ttk, messagebox
from database import autenticar_usuario
from .styles import Styles

class LoginWindow:
    def __init__(self, root, on_success_callback):
        self.root = root
        self.on_success = on_success_callback
        
        self.root.title("StockWare - Iniciar Sesión")
        self.root.geometry("400x500")
        self.root.configure(bg='white')
        self.root.resizable(False, False)
        
        # Center window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        self.create_widgets()

    def create_widgets(self):
        # Header / Logo
        header_frame = tk.Frame(self.root, bg=Styles.PRIMARY_COLOR, height=150)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="StockWare", font=('Segoe UI', 24, 'bold'), 
                bg=Styles.PRIMARY_COLOR, fg='white').pack(pady=(40, 5))
        tk.Label(header_frame, text="Gestión de Inventario", font=('Segoe UI', 10), 
                bg=Styles.PRIMARY_COLOR, fg='#bdc3c7').pack()
        
        # Login Form
        form_frame = tk.Frame(self.root, bg='white', padx=40, pady=30)
        form_frame.pack(fill='both', expand=True)
        
        tk.Label(form_frame, text="USUARIO", font=('Segoe UI', 9, 'bold'), 
                bg='white', fg='#7f8c8d').pack(anchor='w', pady=(10, 5))
        self.user_entry = ttk.Entry(form_frame, font=('Segoe UI', 11))
        self.user_entry.pack(fill='x', pady=(0, 20))
        self.user_entry.insert(0, "admin") # Convenience for MVP
        
        tk.Label(form_frame, text="CONTRASEÑA", font=('Segoe UI', 9, 'bold'), 
                bg='white', fg='#7f8c8d').pack(anchor='w', pady=(0, 5))
        self.pass_entry = ttk.Entry(form_frame, font=('Segoe UI', 11), show="*")
        self.pass_entry.pack(fill='x', pady=(0, 30))
        self.pass_entry.insert(0, "admin123") # Convenience for MVP
        
        # Action Button
        self.btn_login = tk.Button(form_frame, text="INGRESAR", command=self.handle_login,
                                bg=Styles.SECONDARY_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                                relief='flat', bd=0, pady=12, cursor='hand2')
        self.btn_login.pack(fill='x')
        
        # Footer
        tk.Label(form_frame, text="v2.0 - 2024", font=('Segoe UI', 8), 
                bg='white', fg='#bdc3c7').pack(pady=(40, 0))
                
        # Bind Enter key
        self.root.bind('<Return>', lambda e: self.handle_login())

    def handle_login(self):
        username = self.user_entry.get().strip()
        password = self.pass_entry.get().strip()
        
        if not username or not password:
            messagebox.showwarning("Atención", "Por favor ingrese usuario y contraseña.")
            return
            
        usuario = autenticar_usuario(username, password)
        if usuario:
            self.on_success(usuario)
        else:
            messagebox.showerror("Error", "Usuario o contraseña incorrectos.")
            self.pass_entry.delete(0, tk.END)
