from flask import Blueprint, request, jsonify
from src.config.supabase_client import get_supabase_client
from src.utils.auth import require_auth, require_role, hash_password

users_bp = Blueprint('users', __name__)

@users_bp.route('', methods=['GET'])
@require_auth
@require_role(['administrador'])
def get_users():
    """Obtener lista de usuarios"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        result = supabase.table('users').select('''
            id, email, full_name, sucursal, is_active, created_at,
            roles(name, description)
        ''').execute()
        
        return jsonify({
            'users': result.data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@users_bp.route('/<user_id>', methods=['PUT'])
@require_auth
@require_role(['administrador'])
def update_user(user_id):
    """Actualizar un usuario"""
    try:
        data = request.get_json()
        
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Verificar que el usuario existe
        existing_user = supabase.table('users').select('id').eq('id', user_id).execute()
        if not existing_user.data:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Actualizar usuario
        update_data = {}
        allowed_fields = ['full_name', 'sucursal', 'is_active']
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        # Actualizar rol si se proporciona
        if 'role' in data:
            role_result = supabase.table('roles').select('id').eq('name', data['role']).execute()
            if role_result.data:
                update_data['role_id'] = role_result.data[0]['id']
        
        # Actualizar contraseña si se proporciona
        if 'password' in data and data['password']:
            update_data['password_hash'] = hash_password(data['password'])
        
        if update_data:
            result = supabase.table('users').update(update_data).eq('id', user_id).execute()
            
            if result.data:
                return jsonify({
                    'message': 'Usuario actualizado exitosamente',
                    'user': result.data[0]
                })
            else:
                return jsonify({'error': 'Error al actualizar usuario'}), 500
        else:
            return jsonify({'error': 'No hay datos para actualizar'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@users_bp.route('/operadoras', methods=['GET'])
@require_auth
def get_operadoras():
    """Obtener lista de operadoras (cosmetólogas)"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Obtener ID del rol cosmetóloga
        role_result = supabase.table('roles').select('id').eq('name', 'cosmetologa').execute()
        if not role_result.data:
            return jsonify({'operadoras': []})
        
        role_id = role_result.data[0]['id']
        
        result = supabase.table('users').select('id, full_name, sucursal').eq('role_id', role_id).eq('is_active', True).execute()
        
        return jsonify({
            'operadoras': result.data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@users_bp.route('/profile', methods=['GET'])
@require_auth
def get_profile():
    """Obtener perfil del usuario actual"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        user_id = request.user['user_id']
        
        result = supabase.table('users').select('''
            id, email, full_name, sucursal, created_at,
            roles(name, description, permissions)
        ''').eq('id', user_id).execute()
        
        if not result.data:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        return jsonify({
            'user': result.data[0]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@users_bp.route('/profile', methods=['PUT'])
@require_auth
def update_profile():
    """Actualizar perfil del usuario actual"""
    try:
        data = request.get_json()
        
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        user_id = request.user['user_id']
        
        # Actualizar perfil
        update_data = {}
        allowed_fields = ['full_name']
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        # Actualizar contraseña si se proporciona
        if 'password' in data and data['password']:
            update_data['password_hash'] = hash_password(data['password'])
        
        if update_data:
            result = supabase.table('users').update(update_data).eq('id', user_id).execute()
            
            if result.data:
                return jsonify({
                    'message': 'Perfil actualizado exitosamente',
                    'user': result.data[0]
                })
            else:
                return jsonify({'error': 'Error al actualizar perfil'}), 500
        else:
            return jsonify({'error': 'No hay datos para actualizar'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

