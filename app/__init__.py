import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# 1. Crear la instancia de la aplicación PRIMERO.
# Esta es la línea que debe ir antes que las demás.
app = Flask(__name__)

# 2. Ahora que 'app' existe, podemos configurarla.
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SECRET_KEY'] = 'una-clave-secreta-muy-dificil-de-adivinar'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'agenda.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 3. Inicializar las extensiones de Flask, pasándoles la 'app'.
db = SQLAlchemy(app)
login = LoginManager(app)

# 4. Configurar Flask-Login para que sepa cuál es la página de inicio de sesión.
# Si un usuario no autenticado intenta acceder a una página protegida, será redirigido aquí.
login.login_view = 'login'
login.login_message = 'Por favor, inicia sesión para acceder a esta página.'
login.login_message_category = 'info'


# 5. Importar los modelos y las rutas al final.
# Esto es importante para evitar errores de importación circular.
from app import routes, models
