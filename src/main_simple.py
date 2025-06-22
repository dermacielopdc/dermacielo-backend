from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    
    # Enable CORS for all routes
    CORS(app, origins="*")
    
    @app.route('/')
    def health_check():
        return {'status': 'healthy', 'message': 'Dermacielo API is running'}
    
    @app.route('/api/health')
    def api_health():
        return {'status': 'ok', 'message': 'Dermacielo API is running'}
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)

