"""
WSGI entry point for Waitress production server
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    import waitress
    print("Serving Food Man on http://0.0.0.0:5000 with Waitress...")
    waitress.serve(app, host="0.0.0.0", port=5000, threads=6)
