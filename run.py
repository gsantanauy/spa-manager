from app import app, db
from app.models import Terapeuta, Gabinete, Tratamiento, Cliente, Cita
import click

# Esto crea un contexto de aplicación para que podamos trabajar con 'db'
@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'Terapeuta': Terapeuta, 'Gabinete': Gabinete, 'Tratamiento': Tratamiento, 'Cliente': Cliente, 'Cita': Cita}
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
if __name__ == '__main__':
    # El host '0.0.0.0' hace que el servidor sea visible en tu red local.
    # Otros PCs podrán acceder usando la IP de la máquina anfitriona.
    # Ejemplo: http://192.168.1.105:5000
    app.run(host='0.0.0.0', port=5000, debug=True)
