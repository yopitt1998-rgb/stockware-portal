
from database import obtener_sku_por_codigo_barra

def test_lookup():
    print("--- TESTING BARCODE LOOKUP ---")
    
    # Test Case 1: Standard quoted barcode (from DB)
    code1 = "1'2'16"
    sku1 = obtener_sku_por_codigo_barra(code1)
    print(f"Lookup '{code1}' -> SKU: {sku1} (Expected: 1-2-16)")
    
    # Test Case 2: Dashed input (from Scanner)
    code2 = "1-2-16"
    sku2 = obtener_sku_por_codigo_barra(code2)
    print(f"Lookup '{code2}' -> SKU: {sku2} (Expected: 1-2-16)")
    
    # Test Case 3: Invalid code
    code3 = "INVALID-CODE"
    sku3 = obtener_sku_por_codigo_barra(code3)
    print(f"Lookup '{code3}' -> SKU: {sku3} (Expected: None)")

if __name__ == "__main__":
    test_lookup()
