"""
Test what the Render portal is actually returning
"""
import requests

print("=" * 70)
print("TESTING RENDER PORTAL")
print("=" * 70)

try:
    # Get the main page
    response = requests.get("https://stockware-portal.onrender.com/")
    
    # Look for the status banner in the HTML
    html = response.text
    
    # Extract key information
    if "BASE DE DATOS VACÍA" in html:
        print("❌ Status: BASE DE DATOS VACÍA")
        print("   The portal still shows empty database")
    elif "ESTADO: OK" in html or 'db_status == \'OK\'' in html:
        print("✅ Status: OK")
        print("   The portal should be working!")
    
    # Check for moviles in the select options
    if '<option value="Movil 200">Movil 200</option>' in html:
        print("✅ Moviles dropdown has options")
        # Count how many moviles
        movil_count = html.count('<option value="Movil')
        print(f"   Found {movil_count} moviles in dropdown")
    else:
        print("⚠️ No moviles found in dropdown HTML")
    
    # Check for productos
    if 'material-item' in html:
        material_count = html.count('class="material-item"')
        print(f"✅ Found {material_count} material items in the list")
    else:
        print("⚠️ No material items found")
    
    # Look for the status banner values
    import re
    
    # Try to find the count values
    count_m_match = re.search(r'count_m["\s:=]+(\d+)', html)
    count_p_match = re.search(r'count_p["\s:=]+(\d+)', html)
    
    if count_m_match and count_p_match:
        count_m = count_m_match.group(1)
        count_p = count_p_match.group(1)
        print(f"\n📊 Banner shows: {count_m} Móviles, {count_p} Productos")
    
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    
    if "Movil 200" in html and material_count > 0:
        print("🎉 SUCCESS! The portal is working correctly")
        print("   Moviles and productos are showing in the form")
    else:
        print("⚠️ The portal may still have issues")
        print("   Try refreshing the page in your browser")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("=" * 70)
