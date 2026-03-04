import requests
import json

def get_api_data():
    try:
        # Start the server in a temporary way or just call the function directly if possible
        # Since I have the code, I can just mock the database call or use the existing logic.
        # But wait, I can just call the route function if I import it?
        # Actually, let's just run a small script that mimics get_inventario_movil logic.
        
        from web_server import get_inventario_movil
        from flask import Flask
        app = Flask(__name__)
        with app.app_context():
            response = get_inventario_movil("Movil 202")
            print(json.dumps(response.get_json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_api_data()
