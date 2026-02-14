import sys
import py_compile

try:
    py_compile.compile(r'c:\Users\johni\Documents\GestorInventario_MySQL\gui\abasto.py', doraise=True)
    print("Compilation SUCCESS")
except py_compile.PyCompileError as e:
    print(f"Compilation FAILED: {e}")
except Exception as e:
    print(f"Other Error: {e}")
