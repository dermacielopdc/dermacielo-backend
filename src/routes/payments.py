from flask import Blueprint, request, jsonify
from ..config.supabase_client import get_supabase_client
from ..utils.auth import token_required
from datetime import datetime, timedelta
import uuid

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/payments', methods=['GET'])
@token_required
def get_payments(current_user):
    """Obtener lista de pagos con filtros"""
    try:
        supabase = get_supabase_client()
        
        # Parámetros de filtro
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        payment_method = request.args.get('payment_method')
        search = request.args.get('search', '')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        
        # Construir query base
        query = supabase.table('payments').select('''
            *,
            cashier:users!payments_cashier_id_fkey(id, full_name),
            appointments:payment_appointments(
                appointment_id,
                amount,
                appointments(
                    id,
                    patients(nombre_completo),
                    services(nombre, zona)
                )
            )
        ''')
        
        # Aplicar filtros
        if date_from:
            query = query.gte('created_at', f"{date_from}T00:00:00")
        if date_to:
            query = query.lte('created_at', f"{date_to}T23:59:59")
        if payment_method:
            query = query.eq('payment_method', payment_method)
        if search:
            # Buscar en número de ticket o nombre de paciente
            query = query.or_(f"ticket_number.ilike.%{search}%")
        
        # Ordenar y paginar
        query = query.order('created_at', desc=True)
        query = query.range((page - 1) * limit, page * limit - 1)
        
        result = query.execute()
        
        # Procesar datos para agregar información adicional
        payments = []
        for payment in result.data:
            payment_data = {
                **payment,
                'services_count': len(payment.get('appointments', [])),
                'patient_name': None
            }
            
            # Si solo hay un paciente, mostrar su nombre
            if payment.get('appointments'):
                patients = set()
                for apt in payment['appointments']:
                    if apt.get('appointments', {}).get('patients'):
                        patients.add(apt['appointments']['patients']['nombre_completo'])
                
                if len(patients) == 1:
                    payment_data['patient_name'] = list(patients)[0]
                elif len(patients) > 1:
                    payment_data['patient_name'] = f"{len(patients)} pacientes"
            
            payments.append(payment_data)
        
        return jsonify({
            'success': True,
            'payments': payments,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': len(result.data)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@payments_bp.route('/payments/stats', methods=['GET'])
@token_required
def get_payment_stats(current_user):
    """Obtener estadísticas de pagos"""
    try:
        supabase = get_supabase_client()
        
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Pagos de hoy
        today_result = supabase.table('payments').select('total_amount').gte(
            'created_at', f"{today}T00:00:00"
        ).lte('created_at', f"{today}T23:59:59").execute()
        
        # Pagos de la semana
        week_result = supabase.table('payments').select('total_amount').gte(
            'created_at', f"{week_ago}T00:00:00"
        ).execute()
        
        # Pagos del mes
        month_result = supabase.table('payments').select('total_amount').gte(
            'created_at', f"{month_ago}T00:00:00"
        ).execute()
        
        stats = {
            'total_today': sum(p['total_amount'] for p in today_result.data),
            'count_today': len(today_result.data),
            'total_week': sum(p['total_amount'] for p in week_result.data),
            'total_month': sum(p['total_amount'] for p in month_result.data)
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@payments_bp.route('/payments/process', methods=['POST'])
@token_required
def process_payment(current_user):
    """Procesar un nuevo pago"""
    try:
        data = request.get_json()
        supabase = get_supabase_client()
        
        # Validar datos requeridos
        if not data.get('appointments') or not data.get('payment_method'):
            return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
        
        # Generar número de ticket
        ticket_number = f"T{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
        
        # Crear el pago principal
        payment_data = {
            'ticket_number': ticket_number,
            'payment_method': data['payment_method'],
            'total_amount': data['total_amount'],
            'amount_paid': data.get('amount_paid'),
            'discount': data.get('discount', 0),
            'change_amount': data.get('change_amount', 0),
            'cashier_id': current_user['id'],
            'created_at': datetime.now().isoformat()
        }
        
        payment_result = supabase.table('payments').insert(payment_data).execute()
        payment_id = payment_result.data[0]['id']
        
        # Crear registros de payment_appointments
        appointment_payments = []
        for apt in data['appointments']:
            appointment_payments.append({
                'payment_id': payment_id,
                'appointment_id': apt['appointment_id'],
                'amount': apt['amount']
            })
        
        supabase.table('payment_appointments').insert(appointment_payments).execute()
        
        # Actualizar las citas como pagadas
        for apt in data['appointments']:
            supabase.table('appointments').update({
                'is_paid': True,
                'metodo_pago': data['payment_method']
            }).eq('id', apt['appointment_id']).execute()
        
        return jsonify({
            'success': True,
            'payment_id': payment_id,
            'ticket_id': payment_id,
            'ticket_number': ticket_number
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@payments_bp.route('/payments/<payment_id>', methods=['GET'])
@token_required
def get_payment(current_user, payment_id):
    """Obtener detalles de un pago específico"""
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('payments').select('''
            *,
            cashier:users!payments_cashier_id_fkey(id, full_name),
            appointments:payment_appointments(
                appointment_id,
                amount,
                appointments(
                    id,
                    fecha_hora,
                    numero_sesion,
                    precio_sesion,
                    patients(nombre_completo, telefono, localidad),
                    services(nombre, zona, precio_base)
                )
            )
        ''').eq('id', payment_id).execute()
        
        if not result.data:
            return jsonify({'success': False, 'error': 'Pago no encontrado'}), 404
        
        return jsonify({
            'success': True,
            'payment': result.data[0]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@payments_bp.route('/payments/export', methods=['GET'])
@token_required
def export_payments(current_user):
    """Exportar pagos a CSV"""
    try:
        # Obtener filtros
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        payment_method = request.args.get('payment_method')
        
        supabase = get_supabase_client()
        
        query = supabase.table('payments').select('''
            *,
            cashier:users!payments_cashier_id_fkey(full_name),
            appointments:payment_appointments(
                appointments(
                    patients(nombre_completo),
                    services(nombre, zona)
                )
            )
        ''')
        
        # Aplicar filtros
        if date_from:
            query = query.gte('created_at', f"{date_from}T00:00:00")
        if date_to:
            query = query.lte('created_at', f"{date_to}T23:59:59")
        if payment_method:
            query = query.eq('payment_method', payment_method)
        
        result = query.execute()
        
        # Generar CSV
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow([
            'Ticket', 'Fecha', 'Hora', 'Paciente', 'Servicios', 
            'Método Pago', 'Subtotal', 'Descuento', 'Total', 'Cajero'
        ])
        
        # Datos
        for payment in result.data:
            created_at = datetime.fromisoformat(payment['created_at'].replace('Z', '+00:00'))
            
            # Obtener información de pacientes y servicios
            patients = set()
            services = []
            for apt in payment.get('appointments', []):
                if apt.get('appointments'):
                    apt_data = apt['appointments']
                    if apt_data.get('patients'):
                        patients.add(apt_data['patients']['nombre_completo'])
                    if apt_data.get('services'):
                        services.append(apt_data['services']['nombre'])
            
            patient_names = ', '.join(patients) if patients else 'N/A'
            service_names = ', '.join(services) if services else 'N/A'
            
            writer.writerow([
                payment.get('ticket_number', payment['id']),
                created_at.strftime('%Y-%m-%d'),
                created_at.strftime('%H:%M'),
                patient_names,
                service_names,
                payment['payment_method'],
                payment['total_amount'] + payment.get('discount', 0),
                payment.get('discount', 0),
                payment['total_amount'],
                payment.get('cashier', {}).get('full_name', 'Sistema')
            ])
        
        output.seek(0)
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=pagos_{datetime.now().strftime("%Y%m%d")}.csv'}
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

