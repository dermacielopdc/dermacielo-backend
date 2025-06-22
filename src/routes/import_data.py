from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import pandas as pd
import os
from datetime import datetime
from ..config.supabase_client import get_supabase_client
from ..utils.auth import token_required
import uuid

import_bp = Blueprint('import', __name__)

UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_phone_number(phone):
    """Limpiar y formatear número de teléfono"""
    if pd.isna(phone):
        return None
    phone_str = str(phone).strip()
    # Remover caracteres no numéricos excepto +
    phone_clean = ''.join(c for c in phone_str if c.isdigit() or c == '+')
    return phone_clean if phone_clean else None

def parse_date(date_value):
    """Parsear fecha desde Excel"""
    if pd.isna(date_value):
        return None
    
    if isinstance(date_value, str):
        # Intentar varios formatos de fecha
        formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']
        for fmt in formats:
            try:
                return datetime.strptime(date_value, fmt).date().isoformat()
            except ValueError:
                continue
    elif hasattr(date_value, 'date'):
        return date_value.date().isoformat()
    
    return None

@import_bp.route('/import/patients', methods=['POST'])
@token_required
def import_patients(current_user):
    """Importar pacientes desde Excel"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No se encontró archivo'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No se seleccionó archivo'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Formato de archivo no permitido'}), 400
        
        # Guardar archivo temporalmente
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Leer Excel
        df = pd.read_excel(filepath)
        
        # Mapear columnas (basado en el archivo de pacientes analizado)
        column_mapping = {
            'NOMBRE COMPLETO': 'nombre_completo',
            'TELEFONO': 'telefono',
            'LOCALIDAD': 'localidad',
            'ZONA DE TRATAMIENTO': 'zonas_tratamiento',
            'FECHA DE NACIMIENTO': 'fecha_nacimiento',
            'OBSERVACIONES': 'observaciones'
        }
        
        # Renombrar columnas
        df_mapped = df.rename(columns=column_mapping)
        
        supabase = get_supabase_client()
        imported_count = 0
        errors = []
        
        for index, row in df_mapped.iterrows():
            try:
                # Validar datos requeridos
                if pd.isna(row.get('nombre_completo')):
                    errors.append(f"Fila {index + 2}: Nombre completo requerido")
                    continue
                
                # Preparar datos del paciente
                patient_data = {
                    'nombre_completo': str(row['nombre_completo']).strip(),
                    'telefono': clean_phone_number(row.get('telefono')),
                    'localidad': str(row.get('localidad', '')).strip() if not pd.isna(row.get('localidad')) else None,
                    'fecha_nacimiento': parse_date(row.get('fecha_nacimiento')),
                    'observaciones': str(row.get('observaciones', '')).strip() if not pd.isna(row.get('observaciones')) else None,
                    'created_at': datetime.now().isoformat()
                }
                
                # Procesar zonas de tratamiento
                zonas = row.get('zonas_tratamiento')
                if not pd.isna(zonas):
                    zonas_list = [z.strip() for z in str(zonas).split(',')]
                    patient_data['zonas_tratamiento'] = zonas_list
                
                # Verificar si el paciente ya existe
                existing = supabase.table('patients').select('id').eq('nombre_completo', patient_data['nombre_completo']).execute()
                
                if existing.data:
                    # Actualizar paciente existente
                    supabase.table('patients').update(patient_data).eq('id', existing.data[0]['id']).execute()
                else:
                    # Crear nuevo paciente
                    supabase.table('patients').insert(patient_data).execute()
                
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Fila {index + 2}: {str(e)}")
        
        # Limpiar archivo temporal
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'imported_count': imported_count,
            'total_rows': len(df),
            'errors': errors
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@import_bp.route('/import/payments', methods=['POST'])
@token_required
def import_payments(current_user):
    """Importar pagos/abonos desde Excel"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No se encontró archivo'}), 400
        
        file = request.files['file']
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Formato de archivo no permitido'}), 400
        
        # Guardar archivo temporalmente
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Leer Excel
        df = pd.read_excel(filepath)
        
        # Mapear columnas (basado en archivos de abonos/transferencias)
        column_mapping = {
            'FECHA': 'fecha',
            'PACIENTE': 'paciente',
            'SERVICIO': 'servicio',
            'MONTO': 'monto',
            'METODO': 'metodo_pago',
            'OBSERVACIONES': 'observaciones'
        }
        
        df_mapped = df.rename(columns=column_mapping)
        
        supabase = get_supabase_client()
        imported_count = 0
        errors = []
        
        for index, row in df_mapped.iterrows():
            try:
                # Validar datos requeridos
                if pd.isna(row.get('paciente')) or pd.isna(row.get('monto')):
                    errors.append(f"Fila {index + 2}: Paciente y monto son requeridos")
                    continue
                
                # Buscar paciente
                patient_name = str(row['paciente']).strip()
                patient_result = supabase.table('patients').select('id').eq('nombre_completo', patient_name).execute()
                
                if not patient_result.data:
                    errors.append(f"Fila {index + 2}: Paciente '{patient_name}' no encontrado")
                    continue
                
                patient_id = patient_result.data[0]['id']
                
                # Preparar datos del pago
                payment_data = {
                    'patient_id': patient_id,
                    'total_amount': float(row['monto']),
                    'payment_method': str(row.get('metodo_pago', 'efectivo')).lower(),
                    'ticket_number': f"IMP{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}",
                    'cashier_id': current_user['id'],
                    'created_at': parse_date(row.get('fecha')) or datetime.now().isoformat(),
                    'is_imported': True,
                    'import_notes': str(row.get('observaciones', '')).strip() if not pd.isna(row.get('observaciones')) else None
                }
                
                # Insertar pago
                supabase.table('payments').insert(payment_data).execute()
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Fila {index + 2}: {str(e)}")
        
        # Limpiar archivo temporal
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'imported_count': imported_count,
            'total_rows': len(df),
            'errors': errors
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@import_bp.route('/import/appointments', methods=['POST'])
@token_required
def import_appointments(current_user):
    """Importar citas desde Excel"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No se encontró archivo'}), 400
        
        file = request.files['file']
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Formato de archivo no permitido'}), 400
        
        # Guardar archivo temporalmente
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Leer Excel
        df = pd.read_excel(filepath)
        
        # Mapear columnas
        column_mapping = {
            'FECHA': 'fecha',
            'HORA': 'hora',
            'PACIENTE': 'paciente',
            'SERVICIO': 'servicio',
            'SESION': 'numero_sesion',
            'PRECIO': 'precio_sesion',
            'ESTADO': 'status'
        }
        
        df_mapped = df.rename(columns=column_mapping)
        
        supabase = get_supabase_client()
        imported_count = 0
        errors = []
        
        for index, row in df_mapped.iterrows():
            try:
                # Validar datos requeridos
                if pd.isna(row.get('paciente')) or pd.isna(row.get('fecha')):
                    errors.append(f"Fila {index + 2}: Paciente y fecha son requeridos")
                    continue
                
                # Buscar paciente
                patient_name = str(row['paciente']).strip()
                patient_result = supabase.table('patients').select('id').eq('nombre_completo', patient_name).execute()
                
                if not patient_result.data:
                    errors.append(f"Fila {index + 2}: Paciente '{patient_name}' no encontrado")
                    continue
                
                patient_id = patient_result.data[0]['id']
                
                # Buscar servicio (usar servicio por defecto si no se encuentra)
                service_id = None
                if not pd.isna(row.get('servicio')):
                    service_name = str(row['servicio']).strip()
                    service_result = supabase.table('services').select('id').eq('nombre', service_name).execute()
                    if service_result.data:
                        service_id = service_result.data[0]['id']
                
                # Construir fecha y hora
                fecha = parse_date(row['fecha'])
                hora = str(row.get('hora', '10:00')).strip()
                fecha_hora = f"{fecha}T{hora}:00"
                
                # Preparar datos de la cita
                appointment_data = {
                    'patient_id': patient_id,
                    'service_id': service_id,
                    'fecha_hora': fecha_hora,
                    'numero_sesion': int(row.get('numero_sesion', 1)),
                    'precio_sesion': float(row.get('precio_sesion', 0)) if not pd.isna(row.get('precio_sesion')) else None,
                    'status': str(row.get('status', 'agendada')).lower(),
                    'created_at': datetime.now().isoformat(),
                    'is_imported': True
                }
                
                # Insertar cita
                supabase.table('appointments').insert(appointment_data).execute()
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Fila {index + 2}: {str(e)}")
        
        # Limpiar archivo temporal
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'imported_count': imported_count,
            'total_rows': len(df),
            'errors': errors
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@import_bp.route('/import/preview', methods=['POST'])
@token_required
def preview_import(current_user):
    """Vista previa de archivo Excel antes de importar"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No se encontró archivo'}), 400
        
        file = request.files['file']
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Formato de archivo no permitido'}), 400
        
        # Guardar archivo temporalmente
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Leer Excel (solo primeras 10 filas)
        df = pd.read_excel(filepath, nrows=10)
        
        # Convertir a formato JSON serializable
        preview_data = {
            'columns': df.columns.tolist(),
            'rows': df.fillna('').to_dict('records'),
            'total_rows': len(pd.read_excel(filepath)),
            'filename': filename
        }
        
        # Limpiar archivo temporal
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'preview': preview_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

