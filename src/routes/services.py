from flask import Blueprint, request, jsonify
from src.config.supabase_client import get_supabase_client
from src.utils.auth import require_auth, require_role

services_bp = Blueprint('services', __name__)

@services_bp.route('', methods=['GET'])
@require_auth
def get_services():
    """Obtener lista de servicios"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        result = supabase.table('services').select('*').eq('is_active', True).order('nombre').execute()
        
        return jsonify({
            'services': result.data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@services_bp.route('', methods=['POST'])
@require_auth
@require_role(['administrador'])
def create_service():
    """Crear nuevo servicio"""
    try:
        data = request.get_json()
        
        required_fields = ['nombre', 'zona', 'precio_base']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} es requerido'}), 400
        
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Crear servicio
        service_data = {
            'nombre': data['nombre'],
            'descripcion': data.get('descripcion'),
            'zona': data['zona'],
            'precio_base': data['precio_base'],
            'duracion_minutos': data.get('duracion_minutos', 30),
            'sesiones_recomendadas': data.get('sesiones_recomendadas', 10),
            'tecnologia': data.get('tecnologia', 'Sopranoice'),
            'is_active': True
        }
        
        result = supabase.table('services').insert(service_data).execute()
        
        if result.data:
            return jsonify({
                'message': 'Servicio creado exitosamente',
                'service': result.data[0]
            }), 201
        else:
            return jsonify({'error': 'Error al crear servicio'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@services_bp.route('/<service_id>', methods=['PUT'])
@require_auth
@require_role(['administrador'])
def update_service(service_id):
    """Actualizar un servicio"""
    try:
        data = request.get_json()
        
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Verificar que el servicio existe
        existing_service = supabase.table('services').select('id').eq('id', service_id).execute()
        if not existing_service.data:
            return jsonify({'error': 'Servicio no encontrado'}), 404
        
        # Actualizar servicio
        update_data = {}
        allowed_fields = [
            'nombre', 'descripcion', 'zona', 'precio_base', 'duracion_minutos',
            'sesiones_recomendadas', 'tecnologia', 'is_active'
        ]
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        if update_data:
            result = supabase.table('services').update(update_data).eq('id', service_id).execute()
            
            if result.data:
                return jsonify({
                    'message': 'Servicio actualizado exitosamente',
                    'service': result.data[0]
                })
            else:
                return jsonify({'error': 'Error al actualizar servicio'}), 500
        else:
            return jsonify({'error': 'No hay datos para actualizar'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@services_bp.route('/zones', methods=['GET'])
@require_auth
def get_zones():
    """Obtener lista de zonas disponibles"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        result = supabase.table('services').select('zona').eq('is_active', True).execute()
        
        # Extraer zonas únicas
        zones = list(set([service['zona'] for service in result.data if service['zona']]))
        zones.sort()
        
        return jsonify({
            'zones': zones
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

