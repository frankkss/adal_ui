import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    debug = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    
    app.run(host=host, port=port, debug=debug)