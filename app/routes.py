# =================================================================
# 1. IMPORTACIONES
# =================================================================
import pandas as pd
from sqlalchemy import or_
from io import BytesIO
from datetime import datetime, timedelta, date
from functools import wraps

from flask import render_template, request, redirect, url_for, flash, send_file
from flask_login import login_user, logout_user, current_user, login_required

from app import app, db, login
from app.models import Recepcionista, Cita, Cliente, Terapeuta, Gabinete, Tratamiento, BloqueoHorario, Disponibilidad
from app.forms import LoginForm, RegistrationForm, ChangePasswordForm, EditClientForm


# =================================================================
# 2. DECORADORES Y AYUDANTES
# =================================================================
@login.user_loader
def load_user(id):
    return Recepcionista.query.get(int(id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            return render_template('unauthorized.html'), 403
        return f(*args, **kwargs)
    return decorated_function


# =================================================================
# 3. RUTAS DE AUTENTICACIÓN
# =================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = Recepcionista.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Usuario o contraseña inválidos', 'danger')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('dashboard')
        return redirect(next_page)
    return render_template('login.html', title='Iniciar Sesión', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


# =================================================================
# 4. RUTAS PRINCIPALES DE LA APLICACIÓN
# =================================================================
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    ahora = datetime.now()
    hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = hoy_inicio + timedelta(days=1)
    citas_hoy = Cita.query.filter(Cita.fecha_hora_inicio.between(hoy_inicio, hoy_fin)).order_by(Cita.fecha_hora_inicio).all()
    total_citas = len(citas_hoy)
    citas_finalizadas = sum(1 for c in citas_hoy if c.estado == 'Finalizada')
    citas_canceladas = sum(1 for c in citas_hoy if c.estado == 'Cancelada')
    citas_pendientes = total_citas - citas_finalizadas - citas_canceladas
    proxima_cita = next((c for c in citas_hoy if c.fecha_hora_inicio > ahora and c.estado not in ['Finalizada', 'Cancelada']), None)
    return render_template('dashboard.html', title="Dashboard", total_citas=total_citas, citas_finalizadas=citas_finalizadas,
                           citas_canceladas=citas_canceladas, citas_pendientes=citas_pendientes, proxima_cita=proxima_cita,
                           citas_hoy=citas_hoy)

@app.route('/agenda')
@login_required
def agenda():
    vista = request.args.get('vista', 'grilla_diaria', type=str)
    fecha_str = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'), type=str)
    fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d')
    
    todos_los_terapeutas = Terapeuta.query.order_by(Terapeuta.nombre).all()
    
    franjas_horarias = []
    hora_temp = fecha_dt.replace(hour=7, minute=0)
    while hora_temp.hour < 23:
        franjas_horarias.append(hora_temp.strftime('%H:%M'))
        hora_temp += timedelta(minutes=30)
    
    context = {
        "vista_actual": vista,
        "fecha_actual": fecha_dt,
        "todos_los_terapeutas": todos_los_terapeutas,
        "gabinetes": Gabinete.query.order_by(Gabinete.nombre).all(),
        "tratamientos": Tratamiento.query.order_by(Tratamiento.nombre).all(),
        "clientes": Cliente.query.order_by(Cliente.nombre).all(),
        "franjas_horarias": franjas_horarias,
    }

    if vista == 'grilla_diaria':
        inicio_dia = fecha_dt.replace(hour=0, minute=0, second=0)
        fin_dia = inicio_dia + timedelta(days=1)
        
        terapeutas_disponibles_ids = {d.terapeuta_id for d in Disponibilidad.query.filter_by(fecha=fecha_dt.date()).all()}
        terapeutas_para_vista = [t for t in todos_los_terapeutas if t.id in terapeutas_disponibles_ids]
        
        agenda_diaria = {}
        if terapeutas_para_vista:
            citas_dia = Cita.query.filter(Cita.fecha_hora_inicio.between(inicio_dia, fin_dia)).all()
            bloqueos_dia = BloqueoHorario.query.filter(BloqueoHorario.fecha_hora_inicio.between(inicio_dia, fin_dia)).all()
            
            for franja in franjas_horarias:
                agenda_diaria[franja] = {t.id: {'status': 'no_disponible', 'evento': None, 'render': True, 'rowspan': 1} for t in terapeutas_para_vista}
            
            for terapeuta in terapeutas_para_vista:
                disponibilidades_dia = Disponibilidad.query.filter_by(terapeuta_id=terapeuta.id, fecha=fecha_dt.date()).all()
                if disponibilidades_dia:
                    for franja in franjas_horarias:
                        hora_franja = datetime.strptime(franja, '%H:%M').time()
                        for d in disponibilidades_dia:
                            if d.hora_inicio <= hora_franja < d.hora_fin:
                                agenda_diaria[franja][terapeuta.id]['status'] = 'disponible'
                                break 
            
            for evento in sorted(citas_dia + bloqueos_dia, key=lambda x: x.fecha_hora_inicio):
                if evento.terapeuta_id in {t.id for t in terapeutas_para_vista}:
                    duracion = (evento.fecha_hora_fin - evento.fecha_hora_inicio).total_seconds() / 60
                    rowspan = int(duracion / 30) if duracion > 0 else 1
                    franja_inicio_str = evento.fecha_hora_inicio.strftime('%H:%M')
                    if franja_inicio_str in agenda_diaria:
                        status = 'cita' if isinstance(evento, Cita) else 'bloqueo'
                        agenda_diaria[franja_inicio_str][evento.terapeuta_id] = {'status': status, 'evento': evento, 'render': True, 'rowspan': rowspan}
                        hora_iter = evento.fecha_hora_inicio + timedelta(minutes=30)
                        while hora_iter < evento.fecha_hora_fin:
                            franja_temp_str = hora_iter.strftime('%H:%M')
                            if franja_temp_str in agenda_diaria:
                                agenda_diaria[franja_temp_str][evento.terapeuta_id]['render'] = False
                            hora_iter += timedelta(minutes=30)
        
        context.update({"terapeutas": terapeutas_para_vista, "agenda_diaria": agenda_diaria})

    elif vista == 'vista_columnas':
        inicio_dia = fecha_dt.replace(hour=0, minute=0, second=0)
        fin_dia = inicio_dia + timedelta(days=1)
        terapeutas_disponibles_ids = {d.terapeuta_id for d in Disponibilidad.query.filter_by(fecha=fecha_dt.date()).all()}
        citas = Cita.query.filter(Cita.fecha_hora_inicio.between(inicio_dia, fin_dia)).order_by(Cita.fecha_hora_inicio).all()
        bloqueos = BloqueoHorario.query.filter(BloqueoHorario.fecha_hora_inicio.between(inicio_dia, fin_dia)).all()
        eventos = sorted(citas + bloqueos, key=lambda x: x.fecha_hora_inicio)
        context.update({"terapeutas_disponibles_ids": terapeutas_disponibles_ids, "eventos": eventos, "terapeutas": todos_los_terapeutas})

    elif vista == 'semana':
        start_of_week = fecha_dt - timedelta(days=fecha_dt.weekday())
        end_of_week = start_of_week + timedelta(days=7)
        dias_de_la_semana = [start_of_week + timedelta(days=i) for i in range(7)]
        
        citas_semana = Cita.query.filter(Cita.fecha_hora_inicio.between(start_of_week, end_of_week)).all()
        bloqueos_semana = BloqueoHorario.query.filter(BloqueoHorario.fecha_hora_inicio.between(start_of_week, end_of_week)).all()
        eventos_semana = sorted(citas_semana + bloqueos_semana, key=lambda x: x.fecha_hora_inicio)
        
        agenda_semanal = {franja: {i: {'eventos': [], 'render': True, 'rowspan': 1} for i in range(7)} for franja in franjas_horarias}

        for evento in eventos_semana:
            dia_idx = evento.fecha_hora_inicio.weekday()
            franja_inicio_str = evento.fecha_hora_inicio.strftime('%H:%M')
            
            if franja_inicio_str in agenda_semanal:
                if evento not in agenda_semanal[franja_inicio_str][dia_idx]['eventos']:
                    agenda_semanal[franja_inicio_str][dia_idx]['eventos'].append(evento)
                    duracion = (evento.fecha_hora_fin - evento.fecha_hora_inicio).total_seconds() / 60
                    rowspan = int(duracion / 30) if duracion > 0 else 1
                    agenda_semanal[franja_inicio_str][dia_idx]['rowspan'] = max(agenda_semanal[franja_inicio_str][dia_idx]['rowspan'], rowspan)
                    hora_iter = evento.fecha_hora_inicio + timedelta(minutes=30)
                    while hora_iter < evento.fecha_hora_fin:
                        franja_temp_str = hora_iter.strftime('%H:%M')
                        if franja_temp_str in agenda_semanal:
                            agenda_semanal[franja_temp_str][dia_idx]['render'] = False
                        hora_iter += timedelta(minutes=30)
                        
        context.update({"dias_de_la_semana": dias_de_la_semana, "agenda_semanal": agenda_semanal})
    
    return render_template('agenda.html', **context)

@app.route('/citas/nueva', methods=['POST'])
@login_required
def nueva_cita():
    try:
        terapeuta_id = int(request.form.get('terapeuta_id'))
        fecha = request.form.get('fecha')
        hora = request.form.get('hora')
        cliente_id = request.form.get('cliente_id')
        gabinete_id = request.form.get('gabinete_id')
        tratamiento_id = request.form.get('tratamiento_id')

        if not all([terapeuta_id, fecha, hora, cliente_id, gabinete_id, tratamiento_id]):
            flash('Todos los campos son obligatorios.', 'danger')
            return redirect(url_for('agenda', fecha=fecha or datetime.now().strftime('%Y-%m-%d')))

        fecha_hora_inicio = datetime.strptime(f"{fecha} {hora}", '%Y-%m-%d %H:%M')
        tratamiento = Tratamiento.query.get(tratamiento_id)
        fecha_hora_fin = fecha_hora_inicio + timedelta(minutes=tratamiento.duracion)

        disponibilidad_valida = False
        disponibilidades_dia = Disponibilidad.query.filter_by(terapeuta_id=terapeuta_id, fecha=fecha_hora_inicio.date()).all()
        for d in disponibilidades_dia:
            if d.hora_inicio <= fecha_hora_inicio.time() and d.hora_fin >= fecha_hora_fin.time():
                disponibilidad_valida = True
                break
        
        if not disponibilidad_valida:
            flash(f'El terapeuta no tiene disponibilidad definida para ese horario.', 'danger')
            return redirect(url_for('agenda', fecha=fecha))

        bloqueo_existente = BloqueoHorario.query.filter(BloqueoHorario.terapeuta_id == terapeuta_id, BloqueoHorario.fecha_hora_inicio < fecha_hora_fin, BloqueoHorario.fecha_hora_fin > fecha_hora_inicio).first()
        if bloqueo_existente:
            flash(f'El horario seleccionado está bloqueado por: "{bloqueo_existente.titulo}".', 'danger')
            return redirect(url_for('agenda', fecha=fecha))

        cita_terapeuta_existente = Cita.query.filter(Cita.terapeuta_id == terapeuta_id, Cita.fecha_hora_inicio < fecha_hora_fin, Cita.fecha_hora_fin > fecha_hora_inicio).first()
        if cita_terapeuta_existente:
            flash('El terapeuta ya tiene otra cita en ese horario.', 'danger')
            return redirect(url_for('agenda', fecha=fecha))

        cita_gabinete_existente = Cita.query.filter(Cita.gabinete_id == gabinete_id, Cita.fecha_hora_inicio < fecha_hora_fin, Cita.fecha_hora_fin > fecha_hora_inicio).first()
        if cita_gabinete_existente:
            gabinete_obj = Gabinete.query.get(gabinete_id)
            flash(f'Error: El gabinete "{gabinete_obj.nombre}" ya está ocupado.', 'danger')
            return redirect(url_for('agenda', fecha=fecha))

        cita_cliente_existente = Cita.query.filter(Cita.cliente_id == cliente_id, Cita.fecha_hora_inicio < fecha_hora_fin, Cita.fecha_hora_fin > fecha_hora_inicio).first()
        if cita_cliente_existente:
            flash(f'Advertencia: El cliente ya tiene otra cita en un horario similar.', 'warning')
        
        nueva_cita = Cita(fecha_hora_inicio=fecha_hora_inicio, fecha_hora_fin=fecha_hora_fin, cliente_id=cliente_id, terapeuta_id=terapeuta_id, gabinete_id=gabinete_id, tratamiento_id=tratamiento_id, estado='Agendada', recepcionista_id=current_user.id)
        db.session.add(nueva_cita)
        db.session.commit()
        flash('¡Cita agendada con éxito!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocurrió un error al agendar la cita: {str(e)}', 'danger')
    return redirect(url_for('agenda', fecha=request.form.get('fecha')))

@app.route('/citas/editar/<int:id>', methods=['POST'])
@login_required
def editar_cita(id):
    cita_a_editar = Cita.query.get_or_404(id)
    fecha_original = cita_a_editar.fecha_hora_inicio.strftime('%Y-%m-%d')
    try:
        terapeuta_id, fecha, hora = int(request.form.get('terapeuta_id')), request.form.get('fecha'), request.form.get('hora')
        cliente_id, gabinete_id, tratamiento_id = request.form.get('cliente_id'), request.form.get('gabinete_id'), request.form.get('tratamiento_id')
        
        fecha_hora_inicio = datetime.strptime(f"{fecha} {hora}", '%Y-%m-%d %H:%M')
        tratamiento = Tratamiento.query.get(tratamiento_id)
        fecha_hora_fin = fecha_hora_inicio + timedelta(minutes=tratamiento.duracion)

        disponibilidad_valida = False
        disponibilidades_dia = Disponibilidad.query.filter_by(terapeuta_id=terapeuta_id, fecha=fecha_hora_inicio.date()).all()
        for d in disponibilidades_dia:
            if d.hora_inicio <= fecha_hora_inicio.time() and d.hora_fin >= fecha_hora_fin.time():
                disponibilidad_valida = True
                break
        
        if not disponibilidad_valida:
            flash(f'El terapeuta no tiene disponibilidad definida para ese horario.', 'danger')
            return redirect(url_for('agenda', fecha=fecha))

        bloqueo_existente = BloqueoHorario.query.filter(BloqueoHorario.terapeuta_id == terapeuta_id, BloqueoHorario.fecha_hora_inicio < fecha_hora_fin, BloqueoHorario.fecha_hora_fin > fecha_hora_inicio).first()
        if bloqueo_existente:
            flash(f'El horario seleccionado está bloqueado por: "{bloqueo_existente.titulo}".', 'danger')
            return redirect(url_for('agenda', fecha=fecha))

        cita_terapeuta_existente = Cita.query.filter(Cita.id != id, Cita.terapeuta_id == terapeuta_id, Cita.fecha_hora_inicio < fecha_hora_fin, Cita.fecha_hora_fin > fecha_hora_inicio).first()
        if cita_terapeuta_existente:
            flash('El terapeuta ya tiene otra cita en ese horario.', 'danger')
            return redirect(url_for('agenda', fecha=fecha))

        cita_gabinete_existente = Cita.query.filter(Cita.id != id, Cita.gabinete_id == gabinete_id, Cita.fecha_hora_inicio < fecha_hora_fin, Cita.fecha_hora_fin > fecha_hora_inicio).first()
        if cita_gabinete_existente:
            gabinete_obj = Gabinete.query.get(gabinete_id)
            flash(f'Error: El gabinete "{gabinete_obj.nombre}" ya está ocupado.', 'danger')
            return redirect(url_for('agenda', fecha=fecha))

        cita_cliente_existente = Cita.query.filter(Cita.id != id, Cita.cliente_id == cliente_id, Cita.fecha_hora_inicio < fecha_hora_fin, Cita.fecha_hora_fin > fecha_hora_inicio).first()
        if cita_cliente_existente:
            flash(f'Advertencia: El cliente ya tiene otra cita en un horario similar.', 'warning')

        cita_a_editar.cliente_id, cita_a_editar.terapeuta_id, cita_a_editar.gabinete_id = int(cliente_id), int(terapeuta_id), int(gabinete_id)
        cita_a_editar.tratamiento_id, cita_a_editar.fecha_hora_inicio, cita_a_editar.fecha_hora_fin = int(tratamiento_id), fecha_hora_inicio, fecha_hora_fin
        db.session.commit()
        flash('Cita actualizada con éxito!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocurrió un error al actualizar la cita: {str(e)}', 'danger')
    return redirect(url_for('agenda', fecha=request.form.get('fecha', fecha_original)))

@app.route('/citas/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_cita(id):
    cita_a_eliminar = Cita.query.get_or_404(id)
    fecha_cita = cita_a_eliminar.fecha_hora_inicio.strftime('%Y-%m-%d')
    try:
        db.session.delete(cita_a_eliminar)
        db.session.commit()
        flash('Cita eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la cita: {str(e)}', 'danger')
    return redirect(url_for('agenda', fecha=fecha_cita))

@app.route('/citas/cambiar_estado/<int:id>', methods=['POST'])
@login_required
def cambiar_estado_cita(id):
    cita = Cita.query.get_or_404(id)
    fecha_cita = cita.fecha_hora_inicio.strftime('%Y-%m-%d')
    try:
        nuevo_estado = request.form.get('estado')
        if nuevo_estado:
            cita.estado = nuevo_estado
            db.session.commit()
            flash('Estado de la cita actualizado con éxito.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocurrió un error al actualizar el estado: {str(e)}', 'danger')
    vista_actual = request.args.get('vista', 'grilla_diaria')
    return redirect(url_for('agenda', fecha=fecha_cita, vista=vista_actual))

# =================================================================
# 5. RUTAS DE CONFIGURACIÓN Y GESTIÓN
# =================================================================
@app.route('/configuracion')
@login_required
@admin_required
def configuracion():
    return render_template('configuracion.html', title='Configuración')

@app.route('/clientes', methods=['GET', 'POST'])
@login_required
def gestionar_clientes():
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre')
            telefono = request.form.get('telefono')
            email = request.form.get('email')
            tipo_membresia = request.form.get('tipo_membresia')
            vencimiento_str = request.form.get('vencimiento_membresia')
            
            vencimiento_fecha = None
            if vencimiento_str and tipo_membresia in ['Mensual', 'Anual']:
                vencimiento_fecha = datetime.strptime(vencimiento_str, '%Y-%m-%d').date()

            if not nombre or not telefono:
                flash('Nombre y teléfono son campos obligatorios.', 'danger')
                return redirect(url_for('gestionar_clientes'))
            
            cliente_existente = Cliente.query.filter_by(telefono=telefono).first()
            if cliente_existente:
                flash('Ya existe un cliente con ese número de teléfono.', 'warning')
                return redirect(url_for('gestionar_clientes'))
            
            nuevo_cliente = Cliente(
                nombre=nombre, 
                telefono=telefono, 
                email=email, 
                tipo_membresia=tipo_membresia,
                vencimiento_membresia=vencimiento_fecha
            )
            db.session.add(nuevo_cliente)
            db.session.commit()
            flash('¡Cliente agregado con éxito!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error al guardar el cliente: {str(e)}', 'danger')
        return redirect(url_for('gestionar_clientes'))
        
    q = request.args.get('q', '', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    query = Cliente.query
    if q:
        query = query.filter(or_(Cliente.nombre.ilike(f'%{q}%'), Cliente.telefono.like(f'%{q}%')))
    clientes_paginados = query.order_by(Cliente.nombre).paginate(page=page, per_page=per_page, error_out=False)
    form = EditClientForm(original_telefono=None)
    return render_template('manage_clientes.html', clientes_paginados=clientes_paginados, form=form, title='Gestionar Clientes', query_busqueda=q, per_page=per_page)

# --- INICIO: RUTA EDITAR CLIENTE REFACTORIZADA ---
@app.route('/clientes/editar/<int:id>', methods=['POST'])
@login_required
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    form = EditClientForm(original_telefono=cliente.telefono, data=request.form)

    if form.validate_on_submit():
        cliente.nombre = form.nombre.data
        cliente.telefono = form.telefono.data
        cliente.email = form.email.data
        cliente.tipo_membresia = form.tipo_membresia.data
        
        if cliente.tipo_membresia in ['Mensual', 'Anual']:
            cliente.vencimiento_membresia = form.vencimiento_membresia.data
        else:
            cliente.vencimiento_membresia = None
            
        db.session.commit()
        flash('¡Cliente actualizado con éxito!', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error al editar: {error}', 'danger')

    return redirect(url_for('gestionar_clientes'))
# --- FIN: RUTA EDITAR CLIENTE REFACTORIZADA ---

@app.route('/clientes/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_cliente(id):
    cliente_a_eliminar = Cliente.query.get_or_404(id)
    if cliente_a_eliminar.citas:
        flash('Este cliente no se puede eliminar porque tiene citas en su historial.', 'danger')
    else:
        db.session.delete(cliente_a_eliminar)
        db.session.commit()
        flash('Cliente eliminado correctamente.', 'success')
    return redirect(url_for('gestionar_clientes'))

@app.route('/cliente/<int:cliente_id>')
@login_required
def detalle_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    citas = Cita.query.filter_by(cliente_id=cliente.id).order_by(Cita.fecha_hora_inicio.desc()).all()
    total_gastado = sum(c.tratamiento.precio for c in citas if c.estado == 'Finalizada' and c.tratamiento.precio)
    citas_finalizadas = sum(1 for c in citas if c.estado == 'Finalizada')
    return render_template('detalle_cliente.html', title=f"Detalle de {cliente.nombre}", cliente=cliente, citas=citas,
                           total_gastado=total_gastado, citas_finalizadas=citas_finalizadas)

@app.route('/configuracion/terapeutas', methods=['GET', 'POST'])
@login_required
@admin_required
def gestionar_terapeutas():
    if request.method == 'POST':
        nombre, especialidad = request.form.get('nombre'), request.form.get('especialidad')
        if nombre:
            nuevo_terapeuta = Terapeuta(nombre=nombre, especialidad=especialidad)
            db.session.add(nuevo_terapeuta)
            db.session.commit()
            flash('¡Terapeuta agregado con éxito!', 'success')
        else:
            flash('El nombre del terapeuta es obligatorio.', 'danger')
        return redirect(url_for('gestionar_terapeutas'))
    terapeutas = Terapeuta.query.all()
    return render_template('manage_terapeutas.html', terapeutas=terapeutas, title='Gestionar Terapeutas')

@app.route('/configuracion/terapeutas/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar_terapeuta(id):
    terapeuta_a_eliminar = Terapeuta.query.get_or_404(id)
    if terapeuta_a_eliminar.citas or terapeuta_a_eliminar.bloqueos or terapeuta_a_eliminar.disponibilidades:
        flash('No se puede eliminar un terapeuta con citas, disponibilidades o bloqueos asociados.', 'danger')
        return redirect(url_for('gestionar_terapeutas'))
        
    db.session.delete(terapeuta_a_eliminar)
    db.session.commit()
    flash('Terapeuta eliminado correctamente.', 'warning')
    return redirect(url_for('gestionar_terapeutas'))

@app.route('/configuracion/terapeutas/<int:terapeuta_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def detalle_terapeuta_config(terapeuta_id):
    terapeuta = Terapeuta.query.get_or_404(terapeuta_id)
    
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'disponibilidad':
            fecha_str = request.form.get('fecha')
            hora_inicio = request.form.get('hora_inicio')
            hora_fin = request.form.get('hora_fin')
            if all([fecha_str, hora_inicio, hora_fin]):
                nueva_disponibilidad = Disponibilidad(
                    terapeuta_id=terapeuta.id, 
                    fecha=datetime.strptime(fecha_str, '%Y-%m-%d').date(),
                    hora_inicio=datetime.strptime(hora_inicio, '%H:%M').time(),
                    hora_fin=datetime.strptime(hora_fin, '%H:%M').time()
                )
                db.session.add(nueva_disponibilidad)
                db.session.commit()
                flash('Horario de disponibilidad añadido con éxito.', 'success')
            else:
                flash('Todos los campos son obligatorios para añadir disponibilidad.', 'danger')
        
        elif form_type == 'bloqueo':
            titulo = request.form.get('titulo')
            fecha = request.form.get('fecha')
            hora_inicio = request.form.get('hora_inicio')
            hora_fin = request.form.get('hora_fin')
            if all([titulo, fecha, hora_inicio, hora_fin]):
                fecha_hora_inicio = datetime.strptime(f"{fecha} {hora_inicio}", "%Y-%m-%d %H:%M")
                fecha_hora_fin = datetime.strptime(f"{fecha} {hora_fin}", "%Y-%m-%d %H:%M")
                nuevo_bloqueo = BloqueoHorario(
                    titulo=titulo, 
                    fecha_hora_inicio=fecha_hora_inicio, 
                    fecha_hora_fin=fecha_hora_fin, 
                    terapeuta_id=terapeuta.id
                )
                db.session.add(nuevo_bloqueo)
                db.session.commit()
                flash('Bloqueo de horario creado con éxito.', 'success')
            else:
                flash('Todos los campos son obligatorios para crear un bloqueo.', 'danger')
                
        return redirect(url_for('detalle_terapeuta_config', terapeuta_id=terapeuta.id))

    disponibilidades = sorted(terapeuta.disponibilidades, key=lambda d: d.fecha, reverse=True)
    bloqueos = sorted(terapeuta.bloqueos, key=lambda b: b.fecha_hora_inicio, reverse=True)
    
    return render_template('detalle_terapeuta_config.html', 
                           terapeuta=terapeuta, 
                           disponibilidades=disponibilidades, 
                           bloqueos=bloqueos,
                           title=f"Configurar a {terapeuta.nombre}")

@app.route('/configuracion/terapeutas/disponibilidad/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar_disponibilidad_terapeuta(id):
    disponibilidad = Disponibilidad.query.get_or_404(id)
    terapeuta_id = disponibilidad.terapeuta_id
    db.session.delete(disponibilidad)
    db.session.commit()
    flash('El horario de disponibilidad ha sido eliminado.', 'success')
    return redirect(url_for('detalle_terapeuta_config', terapeuta_id=terapeuta_id))

@app.route('/configuracion/terapeutas/bloqueo/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar_bloqueo_terapeuta(id):
    bloqueo = BloqueoHorario.query.get_or_404(id)
    terapeuta_id = bloqueo.terapeuta_id
    db.session.delete(bloqueo)
    db.session.commit()
    flash('El bloqueo de horario ha sido eliminado.', 'success')
    return redirect(url_for('detalle_terapeuta_config', terapeuta_id=terapeuta_id))


@app.route('/configuracion/gabinetes', methods=['GET', 'POST'])
@login_required
@admin_required
def gestionar_gabinetes():
    if request.method == 'POST':
        nombre, descripcion = request.form.get('nombre'), request.form.get('descripcion')
        if nombre:
            nuevo_gabinete = Gabinete(nombre=nombre, descripcion=descripcion)
            db.session.add(nuevo_gabinete)
            db.session.commit()
            flash('Gabinete agregado con éxito!', 'success')
        else:
            flash('El nombre del gabinete es obligatorio.', 'danger')
        return redirect(url_for('gestionar_gabinetes'))
    gabinetes = Gabinete.query.all()
    return render_template('manage_gabinetes.html', gabinetes=gabinetes, title='Gestionar Gabinetes')

@app.route('/configuracion/gabinetes/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar_gabinete(id):
    gabinete_a_eliminar = Gabinete.query.get_or_404(id)
    db.session.delete(gabinete_a_eliminar)
    db.session.commit()
    flash('Gabinete eliminado correctamente.', 'warning')
    return redirect(url_for('gestionar_gabinetes'))

@app.route('/configuracion/tratamientos', methods=['GET', 'POST'])
@login_required
@admin_required
def gestionar_tratamientos():
    if request.method == 'POST':
        nombre, duracion, precio = request.form.get('nombre'), request.form.get('duracion'), request.form.get('precio')
        if nombre and duracion:
            nuevo_tratamiento = Tratamiento(nombre=nombre, duracion=int(duracion), precio=float(precio) if precio else None)
            db.session.add(nuevo_tratamiento)
            db.session.commit()
            flash('Tratamiento agregado con éxito!', 'success')
        else:
            flash('Nombre y duración son obligatorios.', 'danger')
        return redirect(url_for('gestionar_tratamientos'))
    tratamientos = Tratamiento.query.all()
    return render_template('manage_tratamientos.html', tratamientos=tratamientos, title='Gestionar Tratamientos')

@app.route('/configuracion/tratamientos/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar_tratamiento(id):
    tratamiento_a_eliminar = Tratamiento.query.get_or_404(id)
    db.session.delete(tratamiento_a_eliminar)
    db.session.commit()
    flash('Tratamiento eliminado correctamente.', 'warning')
    return redirect(url_for('gestionar_tratamientos'))

@app.route('/configuracion/usuarios')
@login_required
@admin_required
def gestionar_usuarios():
    form = ChangePasswordForm()
    usuarios = Recepcionista.query.order_by(Recepcionista.username).all()
    return render_template('manage_usuarios.html', usuarios=usuarios, form=form, title="Gestionar Usuarios")

@app.route('/configuracion/usuarios/cambiar_password/<int:id>', methods=['POST'])
@login_required
@admin_required
def cambiar_password_usuario(id):
    form = ChangePasswordForm()
    user_to_update = Recepcionista.query.get_or_404(id)
    if form.validate_on_submit():
        user_to_update.set_password(form.password.data)
        db.session.commit()
        flash(f'La contraseña para el usuario {user_to_update.username} ha sido actualizada con éxito.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error en el campo {getattr(form, field).label.text}: {error}', 'danger')
    return redirect(url_for('gestionar_usuarios'))

@app.route('/configuracion/usuarios/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar_usuario(id):
    usuario_a_eliminar = Recepcionista.query.get_or_404(id)
    if usuario_a_eliminar.id == current_user.id:
        flash('No puedes eliminar tu propia cuenta.', 'danger')
        return redirect(url_for('gestionar_usuarios'))
    db.session.delete(usuario_a_eliminar)
    db.session.commit()
    flash('Usuario eliminado correctamente.', 'success')
    return redirect(url_for('gestionar_usuarios'))

@app.route('/admin/crear_usuario', methods=['GET', 'POST'])
#@login_required
#@admin_required
def crear_usuario():
    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data if form.email.data else None
        user = Recepcionista(username=form.username.data, email=email)
        user.set_password(form.password.data)
        user.is_admin = form.is_admin.data
        db.session.add(user)
        db.session.commit()
        flash('¡Nuevo usuario creado con éxito!', 'success')
        return redirect(url_for('gestionar_usuarios'))
    return render_template('crear_usuario.html', title='Crear Nuevo Usuario', form=form)

# =================================================================
# 6. RUTA DE REPORTES
# =================================================================
@app.route('/reportes', methods=['GET', 'POST'])
@login_required
def reportes():
    if request.method == 'POST':
        fecha_inicio_str, fecha_fin_str, formato = request.form.get('fecha_inicio'), request.form.get('fecha_fin'), request.form.get('formato')
        if not fecha_inicio_str or not fecha_fin_str:
            flash('Debes seleccionar una fecha de inicio y una fecha de fin.', 'warning')
            return redirect(url_for('reportes'))
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        citas_query = Cita.query.filter(Cita.fecha_hora_inicio.between(fecha_inicio, fecha_fin)).order_by(Cita.fecha_hora_inicio).all()
        if not citas_query:
            flash('No se encontraron citas en el rango de fechas seleccionado.', 'info')
            return redirect(url_for('reportes'))
        datos_reporte = [{'Fecha': c.fecha_hora_inicio.strftime('%Y-%m-%d'), 'Hora': c.fecha_hora_inicio.strftime('%H:%M'), 'Cliente': c.cliente.nombre, 'Teléfono Cliente': c.cliente.telefono, 'Tratamiento': c.tratamiento.nombre, 'Duración (min)': c.tratamiento.duracion, 'Terapeuta': c.terapeuta.nombre, 'Gabinete': c.gabinete.nombre, 'Estado': c.estado, 'Agendado Por': c.agendado_por.username if c.agendado_por else 'Sistema'} for c in citas_query]
        df = pd.DataFrame(datos_reporte)
        if formato == 'excel':
            output = BytesIO()
            df.to_excel(output, index=False, sheet_name='Reporte Citas')
            output.seek(0)
            return send_file(output, download_name='reporte_citas.xlsx', as_attachment=True)
        else:
            tabla_html = df.to_html(classes='table table-striped table-hover', index=False, border=0)
            return render_template('reporte_resultado.html', tabla_html=tabla_html, title="Resultado del Reporte")
    return render_template('reportes.html', title="Generar Reportes")
