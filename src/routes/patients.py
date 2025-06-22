from flask import Blueprint, request, jsonify
from src.config.supabase_client import get_supabase_client
from src.utils.auth import require_auth, require_role

patients_bp = Blueprint('patients', __name__)

@patients_bp.route('', methods=['GET'])
@require_auth
def get_patients():
    """Obtener lista de pacientes"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Parámetros de consulta
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        search = request.args.get('search', '')
        
        # Construir consulta
        query = supabase.table('patients').select('*')
        
        if search:
            query = query.or_(f'nombre_completo.ilike.%{search}%,telefono.ilike.%{search}%')
        
        # Aplicar paginación
        offset = (page - 1) * limit
        result = query.range(offset, offset + limit - 1).execute()
        
        return jsonify({
            'patients': result.data,
            'page': page,
            'limit': limit
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@patients_bp.route('', methods=['POST'])
@require_auth
@require_role(['administrador', 'cajero'])
def create_patient():
    """Crear nuevo paciente"""
    try:
        data = request.get_json()
        
        required_fields = ['nombre_completo', 'telefono']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} es requerido'}), 400
        
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Verificar si el teléfono ya existe
        existing_patient = supabase.table('patients').select('id').eq('telefono', data['telefono']).execute()
        if existing_patient.data:
            return jsonify({'error': 'Ya existe un paciente con este teléfono'}), 400
        
        # Crear paciente
        patient_data = {
            'numero_cliente': data.get('numero_cliente'),
            'nombre_completo': data['nombre_completo'],
            'telefono': data['telefono'],
            'cumpleanos': data.get('cumpleanos'),
            'sexo': data.get('sexo'),
            'localidad': data.get('localidad'),
            'zonas_tratamiento': data.get('zonas_tratamiento', []),
            'precio_total': data.get('precio_total'),
            'metodo_pago_preferido': data.get('metodo_pago_preferido'),
            'observaciones': data.get('observaciones'),
            'is_active': True
        }
        
        result = supabase.table('patients').insert(patient_data).execute()
        
        if result.data:
            return jsonify({
                'message': 'Paciente creado exitosamente',
                'patient': result.data[0]
            }), 201
        else:
            return jsonify({'error': 'Error al crear paciente'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@patients_bp.route('/<patient_id>', methods=['GET'])
@require_auth
def get_patient(patient_id):
    """Obtener información de un paciente específico"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        result = supabase.table('patients').select('*').eq('id', patient_id).execute()
        
        if not result.data:
            return jsonify({'error': 'Paciente no encontrado'}), 404
        
        return jsonify({
            'patient': result.data[0]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@patients_bp.route('/<patient_id>', methods=['PUT'])
@require_auth
@require_role(['administrador', 'cajero'])
def update_patient(patient_id):
    """Actualizar información de un paciente"""
    try:
        data = request.get_json()
        
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Verificar que el paciente existe
        existing_patient = supabase.table('patients').select('id').eq('id', patient_id).execute()
        if not existing_patient.data:
            return jsonify({'error': 'Paciente no encontrado'}), 404
        
        # Actualizar paciente
        update_data = {}
        allowed_fields = [
            'numero_cliente', 'nombre_completo', 'telefono', 'cumpleanos', 
            'sexo', 'localidad', 'zonas_tratamiento', 'precio_total',
            'metodo_pago_preferido', 'observaciones', 'consentimiento_firmado',
            'fecha_consentimiento', 'is_active'
        ]
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        if update_data:
            result = supabase.table('patients').update(update_data).eq('id', patient_id).execute()
            
            if result.data:
                return jsonify({
                    'message': 'Paciente actualizado exitosamente',
                    'patient': result.data[0]
                })
            else:
                return jsonify({'error': 'Error al actualizar paciente'}), 500
        else:
            return jsonify({'error': 'No hay datos para actualizar'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@patients_bp.route('/<patient_id>/treatments', methods=['GET'])
@require_auth
def get_patient_treatments(patient_id):
    """Obtener historial de tratamientos de un paciente"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        result = supabase.table('patient_treatments').select('*, services(*)').eq('patient_id', patient_id).execute()
        
        return jsonify({
            'treatments': result.data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

