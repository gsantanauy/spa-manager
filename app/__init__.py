import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

app = Flask(__name__)

# --- INICIO DEL CAMBIO ---
# Configuración de la base de datos:
# Intenta leer la URL de la base de datos de producción desde las variables de entorno.
# Si no la encuentra, usa la base de datos local SQLite para desarrollo.
database_uri = os.environ.get('DATABASE_URL')
if database_uri and database_uri.startswith("postgres://"):
    database_uri = database_uri.replace("postgres://", "postgresql://", 1)

if not database_uri:
    basedir = os.path.abspath(os.path.dirname(__file__))
    database_uri = 'sqlite:///' + os.path.join(basedir, 'agenda.db')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-de-desarrollo')
app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# --- FIN DEL CAMBIO ---

db = SQLAlchemy(app)
login = LoginManager(app)

login.login_view = 'login'
login.login_message = 'Por favor, inicia sesión para acceder a esta página.'
login.login_message_category = 'info'

from app import routes, models