from flask import Blueprint, request, jsonify
from src.config.supabase_client import get_supabase_client
from src.utils.auth import hash_password, verify_password, generate_token

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    """Iniciar sesión de usuario"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email y contraseña son requeridos'}), 400
        
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Buscar usuario por email
        result = supabase.table('users').select('*').eq('email', email).eq('is_active', True).execute()
        
        if not result.data:
            return jsonify({'error': 'Credenciales inválidas'}), 401
        
        user = result.data[0]
        
        # Verificar contraseña
        if not verify_password(password, user['password_hash']):
            return jsonify({'error': 'Credenciales inválidas'}), 401
        
        # Obtener información del rol
        role_result = supabase.table('roles').select('*').eq('id', user['role_id']).execute()
        role_name = role_result.data[0]['name'] if role_result.data else 'usuario'
        
        # Generar token
        token = generate_token(user['id'], user['email'], role_name)
        
        return jsonify({
            'token': token,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'full_name': user['full_name'],
                'role': role_name,
                'sucursal': user['sucursal']
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/register', methods=['POST'])
def register():
    """Registrar nuevo usuario (solo para administradores)"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        full_name = data.get('full_name')
        role_name = data.get('role', 'cajero')
        sucursal = data.get('sucursal')
        
        if not all([email, password, full_name]):
            return jsonify({'error': 'Email, contraseña y nombre completo son requeridos'}), 400
        
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Verificar si el email ya existe
        existing_user = supabase.table('users').select('id').eq('email', email).execute()
        if existing_user.data:
            return jsonify({'error': 'El email ya está registrado'}), 400
        
        # Obtener ID del rol
        role_result = supabase.table('roles').select('id').eq('name', role_name).execute()
        if not role_result.data:
            return jsonify({'error': 'Rol inválido'}), 400
        
        role_id = role_result.data[0]['id']
        
        # Hash de la contraseña
        password_hash = hash_password(password)
        
        # Crear usuario
        user_data = {
            'email': email,
            'password_hash': password_hash,
            'full_name': full_name,
            'role_id': role_id,
            'sucursal': sucursal,
            'is_active': True
        }
        
        result = supabase.table('users').insert(user_data).execute()
        
        if result.data:
            user = result.data[0]
            return jsonify({
                'message': 'Usuario creado exitosamente',
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'full_name': user['full_name'],
                    'role': role_name,
                    'sucursal': user['sucursal']
                }
            }), 201
        else:
            return jsonify({'error': 'Error al crear usuario'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/roles', methods=['GET'])
def get_roles():
    """Obtener lista de roles disponibles"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        result = supabase.table('roles').select('*').execute()
        
        return jsonify({
            'roles': result.data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

