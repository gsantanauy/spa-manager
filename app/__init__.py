import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

app = Flask(__name__)

# Configuración de la base de datos (sin cambios)
database_uri = os.environ.get('DATABASE_URL')
if database_uri and database_uri.startswith("postgres://"):
    database_uri = database_uri.replace("postgresql://", "postgresql://", 1)

if not database_uri:
    basedir = os.path.abspath(os.path.dirname(__file__))
    database_uri = 'sqlite:///' + os.path.join(basedir, 'agenda.db')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-de-desarrollo')
app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login = LoginManager(app)

login.login_view = 'login'
login.login_message = 'Por favor, inicia sesión para acceder a esta página.'
login.login_message_category = 'info'

from app import routes, models

# --- INICIO: NUEVO BLOQUE PARA CREAR EL PRIMER ADMIN ---
# Esta sección se ejecuta después de que la app y la DB están inicializadas.
with app.app_context():
    # Nos aseguramos de que todas las tablas estén creadas.
    db.create_all()

    # Buscamos si ya existe algún usuario.
    if not models.Recepcionista.query.first():
        print("La base de datos de usuarios está vacía. Creando usuario administrador por defecto...")
        
        # Leemos las credenciales desde las Variables de Entorno.
        admin_user = os.environ.get('DEFAULT_ADMIN_USER')
        admin_pass = os.environ.get('DEFAULT_ADMIN_PASS')

        if admin_user and admin_pass:
            admin = models.Recepcionista(username=admin_user, is_admin=True)
            admin.set_password(admin_pass)
            db.session.add(admin)
            db.session.commit()
            print(f"Usuario administrador '{admin_user}' creado con éxito.")
        else:
            print("ADVERTENCIA: No se encontraron las variables de entorno DEFAULT_ADMIN_USER o DEFAULT_ADMIN_PASS. No se pudo crear el admin.")
# --- FIN: NUEVO BLOQUE ---