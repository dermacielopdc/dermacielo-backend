from flask import Blueprint, request, jsonify
from src.config.supabase_client import get_supabase_client
from src.utils.auth import require_auth, require_role
from datetime import datetime, timedelta

appointments_bp = Blueprint('appointments', __name__)

@appointments_bp.route('', methods=['GET'])
@require_auth
def get_appointments():
    """Obtener lista de citas"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Parámetros de consulta
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        status = request.args.get('status')
        patient_id = request.args.get('patient_id')
        
        # Construir consulta
        query = supabase.table('appointments').select('''
            *,
            patients(nombre_completo, telefono),
            services(nombre, zona),
            operadora:users!appointments_operadora_id_fkey(full_name),
            cajera:users!appointments_cajera_id_fkey(full_name)
        ''')
        
        if date_from:
            query = query.gte('fecha_hora', date_from)
        if date_to:
            query = query.lte('fecha_hora', date_to)
        if status:
            query = query.eq('status', status)
        if patient_id:
            query = query.eq('patient_id', patient_id)
        
        result = query.order('fecha_hora').execute()
        
        return jsonify({
            'appointments': result.data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@appointments_bp.route('', methods=['POST'])
@require_auth
@require_role(['administrador', 'cajero'])
def create_appointment():
    """Crear nueva cita"""
    try:
        data = request.get_json()
        
        required_fields = ['patient_id', 'service_id', 'fecha_hora']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} es requerido'}), 400
        
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Verificar que el paciente existe
        patient_result = supabase.table('patients').select('id').eq('id', data['patient_id']).execute()
        if not patient_result.data:
            return jsonify({'error': 'Paciente no encontrado'}), 404
        
        # Verificar que el servicio existe
        service_result = supabase.table('services').select('*').eq('id', data['service_id']).execute()
        if not service_result.data:
            return jsonify({'error': 'Servicio no encontrado'}), 404
        
        service = service_result.data[0]
        
        # Crear cita
        appointment_data = {
            'patient_id': data['patient_id'],
            'service_id': data['service_id'],
            'operadora_id': data.get('operadora_id'),
            'cajera_id': request.user['user_id'],  # Usuario actual como cajera
            'fecha_hora': data['fecha_hora'],
            'duracion_minutos': data.get('duracion_minutos', service['duracion_minutos']),
            'numero_sesion': data.get('numero_sesion', 1),
            'status': data.get('status', 'agendada'),
            'precio_sesion': data.get('precio_sesion', service['precio_base']),
            'metodo_pago': data.get('metodo_pago'),
            'observaciones_caja': data.get('observaciones_caja'),
            'proxima_cita': data.get('proxima_cita')
        }
        
        result = supabase.table('appointments').insert(appointment_data).execute()
        
        if result.data:
            return jsonify({
                'message': 'Cita creada exitosamente',
                'appointment': result.data[0]
            }), 201
        else:
            return jsonify({'error': 'Error al crear cita'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@appointments_bp.route('/<appointment_id>', methods=['PUT'])
@require_auth
def update_appointment(appointment_id):
    """Actualizar una cita"""
    try:
        data = request.get_json()
        
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Verificar que la cita existe
        existing_appointment = supabase.table('appointments').select('id').eq('id', appointment_id).execute()
        if not existing_appointment.data:
            return jsonify({'error': 'Cita no encontrada'}), 404
        
        # Actualizar cita
        update_data = {}
        allowed_fields = [
            'fecha_hora', 'duracion_minutos', 'numero_sesion', 'status',
            'precio_sesion', 'metodo_pago', 'observaciones_caja', 
            'observaciones_operadora', 'proxima_cita', 'operadora_id'
        ]
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        if update_data:
            result = supabase.table('appointments').update(update_data).eq('id', appointment_id).execute()
            
            if result.data:
                return jsonify({
                    'message': 'Cita actualizada exitosamente',
                    'appointment': result.data[0]
                })
            else:
                return jsonify({'error': 'Error al actualizar cita'}), 500
        else:
            return jsonify({'error': 'No hay datos para actualizar'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@appointments_bp.route('/calendar', methods=['GET'])
@require_auth
def get_calendar():
    """Obtener citas para el calendario"""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Parámetros de consulta
        date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Obtener citas del día
        start_date = f"{date} 00:00:00"
        end_date = f"{date} 23:59:59"
        
        result = supabase.table('appointments').select('''
            *,
            patients(nombre_completo, telefono),
            services(nombre, zona, duracion_minutos),
            operadora:users!appointments_operadora_id_fkey(full_name)
        ''').gte('fecha_hora', start_date).lte('fecha_hora', end_date).order('fecha_hora').execute()
        
        return jsonify({
            'date': date,
            'appointments': result.data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@appointments_bp.route('/<appointment_id>/complete', methods=['POST'])
@require_auth
@require_role(['administrador', 'cosmetologa'])
def complete_appointment(appointment_id):
    """Marcar cita como completada"""
    try:
        data = request.get_json()
        
        supabase = get_supabase_client()
        if not supabase:
            return jsonify({'error': 'Error de configuración del servidor'}), 500
        
        # Actualizar cita
        update_data = {
            'status': 'completada',
            'observaciones_operadora': data.get('observaciones_operadora', ''),
            'proxima_cita': data.get('proxima_cita')
        }
        
        result = supabase.table('appointments').update(update_data).eq('id', appointment_id).execute()
        
        if result.data:
            return jsonify({
                'message': 'Cita marcada como completada',
                'appointment': result.data[0]
            })
        else:
            return jsonify({'error': 'Error al completar cita'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

