import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from src.config.supabase_client import init_supabase
from src.routes.auth import auth_bp
from src.routes.patients import patients_bp
from src.routes.appointments import appointments_bp
from src.routes.services import services_bp
from src.routes.payments import payments_bp
from src.routes.users import users_bp
from src.routes.import_data import import_bp

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dermacielo-secret-key-2025')

# Habilitar CORS para todas las rutas
CORS(app, origins="*")

# Inicializar Supabase
init_supabase()

# Registrar blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(patients_bp, url_prefix='/api/patients')
app.register_blueprint(appointments_bp, url_prefix='/api/appointments')
app.register_blueprint(services_bp, url_prefix='/api/services')
app.register_blueprint(payments_bp, url_prefix='/api/payments')
app.register_blueprint(users_bp, url_prefix='/api/users')
app.register_blueprint(import_bp, url_prefix='/api/import')

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

@app.route('/api/health')
def health_check():
    return {'status': 'ok', 'message': 'Dermacielo API is running'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

