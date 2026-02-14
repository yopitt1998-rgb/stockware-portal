
import os

file_path = r"c:\Users\johni\Documents\GestorInventario_MySQL\gui\audit.py"
extension_path = r"c:\Users\johni\Documents\GestorInventario_MySQL\gui\audit_extension.py"

try:
    # Read original file
    with open(file_path, 'rb') as f:
        content = f.read()
    
    # Remove null bytes
    clean_content = content.replace(b'\x00', b'')
    
    # Decode to string (assuming utf-8, fallback to latin-1)
    try:
        text_content = clean_content.decode('utf-8')
    except UnicodeDecodeError:
        text_content = clean_content.decode('latin-1')
        
    # Read extension
    with open(extension_path, 'r', encoding='utf-8') as f:
        ext_text = f.read()
        
    # Check if extension is already present (partial check)
    if "def mostrar_detalle_series" in text_content:
        print("Method already present (partially?). Truncating it to re-append.")
        # Find the start of the method and truncate
        idx = text_content.rfind("def mostrar_detalle_series")
        if idx != -1:
            text_content = text_content[:idx]
            
    # Ensure newline before append
    if not text_content.endswith('\n'):
        text_content += '\n'
        
    # Append extension
    final_content = text_content + "\n" + ext_text
    
    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
        
    print("Successfully fixed and appended.")
    
except Exception as e:
    print(f"Error: {e}")
