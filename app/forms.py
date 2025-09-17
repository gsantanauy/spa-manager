from flask_wtf import FlaskForm
# CAMBIO: Se añaden SelectField y DateField a la importación
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, DateField
from wtforms.validators import DataRequired, ValidationError, Email, EqualTo, Optional
from app.models import Recepcionista, Cliente

class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired(message="El nombre de usuario es requerido.")])
    password = PasswordField('Contraseña', validators=[DataRequired(message="La contraseña es requerida.")])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Iniciar Sesión')

class RegistrationForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired()])
    email = StringField('Email (Opcional)', validators=[Optional(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    password2 = PasswordField(
        'Repetir Contraseña', validators=[DataRequired(), EqualTo('password', message='Las contraseñas deben coincidir.')])
    is_admin = BooleanField('Asignar como Administrador')
    submit = SubmitField('Crear Usuario')

    def validate_username(self, username):
        user = Recepcionista.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Por favor, utiliza un nombre de usuario diferente.')

    def validate_email(self, email):
        if email.data:
            user = Recepcionista.query.filter_by(email=email.data).first()
            if user is not None:
                raise ValidationError('Esa dirección de email ya está en uso. Por favor, utiliza una diferente.')

class ChangePasswordForm(FlaskForm):
    password = PasswordField('Nueva Contraseña', validators=[DataRequired()])
    password2 = PasswordField(
        'Repetir Nueva Contraseña', 
        validators=[DataRequired(), EqualTo('password', message='Las contraseñas deben coincidir.')]
    )
    submit = SubmitField('Cambiar Contraseña')

class EditClientForm(FlaskForm):
    nombre = StringField('Nombre Completo', validators=[DataRequired()])
    telefono = StringField('Teléfono', validators=[DataRequired()])
    email = StringField('Email (Opcional)', validators=[Optional(), Email()])
    tipo_membresia = SelectField('Tipo de Cliente', choices=[
        ('Huésped', 'Huésped de Hotel'),
        ('Día de Spa', 'Día de Spa'),
        ('Mensual', 'Membresía Mensual'),
        ('Anual', 'Membresía Anual')
    ])
    vencimiento_membresia = DateField('Vencimiento de Membresía', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Guardar Cambios')

    def __init__(self, original_telefono, *args, **kwargs):
        super(EditClientForm, self).__init__(*args, **kwargs)
        self.original_telefono = original_telefono

    def validate_telefono(self, telefono):
        if telefono.data != self.original_telefono:
            cliente = Cliente.query.filter_by(telefono=telefono.data).first()
            if cliente:
                raise ValidationError('Este número de teléfono ya está registrado para otro cliente.')