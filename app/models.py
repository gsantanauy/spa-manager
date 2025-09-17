from app import db
from flask_login import UserMixin
# CAMBIO: Se importa Date para el nuevo campo
from sqlalchemy import Time, Date

# ... (resto de los modelos Recepcionista, Terapeuta, Gabinete, Tratamiento, Cliente, Cita se mantienen igual) ...

class Recepcionista(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    citas_agendadas = db.relationship('Cita', backref='agendado_por', lazy='dynamic')

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

class Terapeuta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    especialidad = db.Column(db.String(100))
    citas = db.relationship('Cita', backref='terapeuta', lazy=True)
    bloqueos = db.relationship('BloqueoHorario', backref='terapeuta', lazy=True, cascade="all, delete-orphan")
    disponibilidades = db.relationship('Disponibilidad', backref='terapeuta', lazy=True, cascade="all, delete-orphan")

class Gabinete(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.String(200))
    citas = db.relationship('Cita', backref='gabinete', lazy=True)

class Tratamiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    duracion = db.Column(db.Integer, nullable=False)
    precio = db.Column(db.Float)
    citas = db.relationship('Cita', backref='tratamiento', lazy=True)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120))
    tipo_membresia = db.Column(db.String(50), nullable=False, default='Huésped')
    vencimiento_membresia = db.Column(db.Date, nullable=True)

class Cita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_hora_inicio = db.Column(db.DateTime, nullable=False)
    fecha_hora_fin = db.Column(db.DateTime, nullable=False)
    estado = db.Column(db.String(50), nullable=False, default='Agendada')
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey('terapeuta.id'), nullable=False)
    gabinete_id = db.Column(db.Integer, db.ForeignKey('gabinete.id'), nullable=False)
    tratamiento_id = db.Column(db.Integer, db.ForeignKey('tratamiento.id'), nullable=False)
    recepcionista_id = db.Column(db.Integer, db.ForeignKey('recepcionista.id'))
    cliente = db.relationship('Cliente', backref=db.backref('citas', lazy=True))

class BloqueoHorario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    fecha_hora_inicio = db.Column(db.DateTime, nullable=False)
    fecha_hora_fin = db.Column(db.DateTime, nullable=False)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey('terapeuta.id'), nullable=False)

# --- INICIO: CAMBIO DEL MODELO DISPONIBILIDAD ---
# Modelo para Disponibilidad por Fecha
class Disponibilidad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Se elimina 'dia_semana' y se añade 'fecha'
    fecha = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    terapeuta_id = db.Column(db.Integer, db.ForeignKey('terapeuta.id'), nullable=False)
# --- FIN: CAMBIO DEL MODELO DISPONIBILIDAD ---