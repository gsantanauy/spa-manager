from app import app, db
from app.models import Recepcionista, Gabinete, Tratamiento, Cliente, Cita, Terapeuta
import click

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'Recepcionista': Recepcionista, 'Gabinete': Gabinete, 'Tratamiento': Tratamiento, 'Cliente': Cliente, 'Cita': Cita, 'Terapeuta': Terapeuta}

# --- INICIO: NUEVO COMANDO PARA CREAR LAS TABLAS ---
@app.cli.command("init-db")
def init_db_command():
    """Crea todas las tablas de la base de datos."""
    db.create_all()
    print("Base de datos inicializada y tablas creadas.")
# --- FIN: NUEVO COMANDO ---

@app.cli.command("create-admin")
@click.argument("username")
@click.argument("password")
def create_admin(username, password):
    """Crea un nuevo usuario con permisos de administrador."""
    if Recepcionista.query.filter_by(username=username).first():
        print(f"Error: El usuario '{username}' ya existe.")
        return
    
    user = Recepcionista(username=username, is_admin=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print(f"¡Éxito! Usuario administrador '{username}' creado correctamente.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)