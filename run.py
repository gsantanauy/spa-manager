from app import app, db
from app.models import Recepcionista, Gabinete, Tratamiento, Cliente, Cita, Terapeuta
import click

# Esto crea un contexto de aplicación para que podamos trabajar con 'db'
@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'Recepcionista': Recepcionista, 'Gabinete': Gabinete, 'Tratamiento': Tratamiento, 'Cliente': Cliente, 'Cita': Cita, 'Terapeuta': Terapeuta}

# Comando para asignar el rol de administrador a un usuario existente
@app.cli.command("make-admin")
@click.argument("username")
def make_admin(username):
    """Asigna el rol de administrador a un usuario existente."""
    user = Recepcionista.query.filter_by(username=username).first()
    if user is None:
        print(f"Error: El usuario '{username}' no fue encontrado.")
        return
    
    user.is_admin = True
    db.session.commit()
    print(f"¡Éxito! El usuario '{username}' ahora es un administrador.")

# Comando para crear un nuevo usuario con permisos de administrador
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
    # El host '0.0.0.0' hace que el servidor sea visible en tu red local.
    app.run(host='0.0.0.0', port=5000, debug=True)