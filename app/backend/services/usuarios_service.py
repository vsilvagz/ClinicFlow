"""Casos de uso sobre usuarios y sus roles.

Cada rol se crea con su propia subclase ORM (herencia de tabla única). El
servicio valida las reglas que el esquema no puede comprobar por sí solo, como
que la especialidad de un médico exista realmente.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.backend.core.security import hash_password, verificar_password
from app.backend.domain.enums import RolUsuario
from app.backend.domain.errores import MedicoNoEncontrado
from app.backend.domain.usuarios import Administrador, Usuario
from app.backend.models.especialidades import EspecialidadORM
from app.backend.models.usuarios import (
    AdministradorORM,
    MedicoORM,
    PacienteORM,
    RecepcionistaORM,
    UsuarioORM,
)
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.schemas.usuarios import (
    AdministradorCrear,
    MedicoCrear,
    PacienteCrear,
    RecepcionistaCrear,
)


class UsuarioYaExiste(Exception):
    """Ya hay un usuario registrado con ese RUN."""


class UsuarioNoEncontrado(Exception):
    """No existe un usuario con el RUN indicado."""


class UltimoAdministrador(Exception):
    """La operación dejaría al sistema sin administradores activos."""


class EspecialidadNoEncontrada(Exception):
    """La especialidad indicada para el médico no existe."""


class CredencialesInvalidas(Exception):
    """El RUN o la contraseña no son correctos al vincular Telegram."""


class SoloPacientesEnTelegram(Exception):
    """Solo las cuentas de paciente pueden vincularse al bot de Telegram."""


def _verificar_run_libre(db: Session, run: int) -> None:
    if db.get(UsuarioORM, run) is not None:
        raise UsuarioYaExiste(f"Ya existe un usuario con RUN {run}.")


def _hash(datos) -> str:
    """Hash de la contraseña si se entregó; cadena vacía si el usuario no tendrá login."""
    return hash_password(datos.password) if datos.password else ""


def crear_paciente(db: Session, datos: PacienteCrear) -> PacienteORM:
    _verificar_run_libre(db, datos.run_usuario)
    paciente = PacienteORM(
        run_usuario=datos.run_usuario,
        nombre=datos.nombre,
        correo=datos.correo,
        telefono=datos.telefono,
        password_hash=_hash(datos),
    )
    db.add(paciente)
    db.commit()
    db.refresh(paciente)
    return paciente


def crear_medico(db: Session, datos: MedicoCrear) -> MedicoORM:
    _verificar_run_libre(db, datos.run_usuario)
    if db.get(EspecialidadORM, datos.especialidad_id) is None:
        raise EspecialidadNoEncontrada(
            f"No existe la especialidad con id {datos.especialidad_id}."
        )

    medico = MedicoORM(
        run_usuario=datos.run_usuario,
        nombre=datos.nombre,
        correo=datos.correo,
        telefono=datos.telefono,
        especialidad_id=datos.especialidad_id,
        password_hash=_hash(datos),
    )
    db.add(medico)
    db.commit()
    db.refresh(medico)
    return medico


def crear_recepcionista(db: Session, datos: RecepcionistaCrear) -> RecepcionistaORM:
    _verificar_run_libre(db, datos.run_usuario)
    recepcionista = RecepcionistaORM(
        run_usuario=datos.run_usuario,
        nombre=datos.nombre,
        correo=datos.correo,
        telefono=datos.telefono,
        clinica_rut=datos.clinica_rut,
        password_hash=_hash(datos),
    )
    db.add(recepcionista)
    db.commit()
    db.refresh(recepcionista)
    return recepcionista


def crear_administrador(db: Session, datos: AdministradorCrear) -> AdministradorORM:
    _verificar_run_libre(db, datos.run_usuario)
    admin = AdministradorORM(
        run_usuario=datos.run_usuario,
        nombre=datos.nombre,
        correo=datos.correo,
        telefono=datos.telefono,
        password_hash=_hash(datos),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def listar_usuarios(db: Session) -> list[UsuarioORM]:
    return RepositorioUsuarios(db).listar()


def listar_medicos(db: Session) -> list[MedicoORM]:
    return RepositorioUsuarios(db).listar_medicos()


def listar_pacientes(db: Session) -> list[PacienteORM]:
    return RepositorioUsuarios(db).listar_pacientes()


def obtener_paciente(db: Session, run: int) -> PacienteORM | None:
    """Devuelve el paciente con ese RUN, o None si no está registrado."""
    return RepositorioUsuarios(db).obtener_paciente(run)


def listar_medicos_por_especialidad(db: Session, especialidad_id: int) -> list[MedicoORM]:
    return RepositorioUsuarios(db).listar_medicos_por_especialidad(especialidad_id)


def autenticar(db: Session, run: int, password: str) -> UsuarioORM | None:
    """Valida las credenciales y devuelve el usuario, o None si no calzan.

    Falla (devuelve None) tanto si el usuario no existe como si la contraseña es
    incorrecta o el usuario no tiene credenciales configuradas.
    """
    usuario = db.get(UsuarioORM, run)
    if usuario is None or not usuario.activo:
        return None
    if not verificar_password(password, usuario.password_hash):
        return None
    return usuario


# ──────────────────────────────────────────────────────────────────────────────
# Vinculación de cuentas con el bot de Telegram.
# El bot identifica a cada persona por su `chat_id`. Aquí se asocia ese chat a la
# cuenta del paciente tras verificar sus credenciales, de modo que el bot opere
# siempre sobre la cuenta correcta (no sobre un paciente fijo). Las reglas de
# negocio del asistente siguen viviendo en los servicios de citas/espera; esto
# solo resuelve "qué paciente es este chat".
# ──────────────────────────────────────────────────────────────────────────────

def vincular_telegram(db: Session, run: int, password: str, chat_id: int) -> PacienteORM:
    """Vincula un chat de Telegram a la cuenta de un paciente.

    Verifica las credenciales con el mismo mecanismo que el login web y exige que
    la cuenta sea de paciente. Un chat solo puede quedar vinculado a una cuenta:
    si el chat ya estaba asociado a otra (o esta cuenta tenía otro chat), se
    libera el vínculo previo antes de crear el nuevo.
    """
    usuario = autenticar(db, run, password)
    if usuario is None:
        raise CredencialesInvalidas("RUN o contraseña incorrectos.")
    if usuario.rol != RolUsuario.PACIENTE:
        raise SoloPacientesEnTelegram("Solo los pacientes pueden usar el bot.")

    # Liberar el chat de cualquier cuenta que lo tuviera (respeta la unicidad
    # chat↔cuenta y permite revincular el chat a otro paciente).
    previos = db.scalars(
        select(UsuarioORM).where(UsuarioORM.telegram_chat_id == chat_id)
    ).all()
    for previo in previos:
        previo.telegram_chat_id = None
    db.flush()

    usuario.telegram_chat_id = chat_id
    db.commit()
    db.refresh(usuario)
    return usuario


def desvincular_telegram(db: Session, chat_id: int) -> bool:
    """Quita el vínculo de un chat de Telegram. Devuelve True si había vínculo."""
    paciente = RepositorioUsuarios(db).obtener_paciente_por_chat(chat_id)
    if paciente is None:
        return False
    paciente.telegram_chat_id = None
    db.commit()
    return True


def obtener_medico(db: Session, run: int) -> MedicoORM:
    medico = RepositorioUsuarios(db).obtener_medico(run)
    if medico is None:
        raise MedicoNoEncontrado(f"No existe un médico con RUN {run}.")
    return medico


# ──────────────────────────────────────────────────────────────────────────────
# Administración de usuarios (acciones del administrador).
# El servicio reconstruye los objetos de dominio, ejecuta el método del
# `Administrador` —donde viven las reglas— y vuelca el resultado al ORM.
# ──────────────────────────────────────────────────────────────────────────────

def _a_usuario_dominio(orm: UsuarioORM) -> Usuario:
    """Objeto de dominio transitorio para validar y aplicar comportamiento."""
    dom = Usuario(orm.run_usuario, orm.nombre, orm.correo, orm.telefono)
    dom._activo = orm.activo
    return dom


def _a_admin_dominio(orm: UsuarioORM) -> Administrador:
    """Reconstruye al administrador que ejecuta la acción."""
    return Administrador(orm.run_usuario, orm.nombre, orm.correo, orm.telefono)


def _administradores_activos_distintos_de(db: Session, run: int) -> int:
    """Cuenta administradores activos cuyo RUN no es el indicado."""
    return db.scalar(
        select(func.count())
        .select_from(AdministradorORM)
        .where(AdministradorORM.run_usuario != run, AdministradorORM.activo.is_(True))
    )


def editar_usuario(
    db: Session,
    actor: UsuarioORM,
    run: int,
    nombre: str | None = None,
    correo: str | None = None,
    telefono: int | None = None,
) -> UsuarioORM:
    """Actualiza los datos de contacto de un usuario (valida el correo)."""
    objetivo = db.get(UsuarioORM, run)
    if objetivo is None:
        raise UsuarioNoEncontrado(f"No existe un usuario con RUN {run}.")

    dom = _a_usuario_dominio(objetivo)
    _a_admin_dominio(actor).editar_usuario(dom, nombre=nombre, correo=correo, telefono=telefono)

    objetivo.nombre = dom.nombre
    objetivo.correo = dom.correo
    objetivo.telefono = dom.telefono
    db.commit()
    db.refresh(objetivo)
    return objetivo


def cambiar_estado_usuario(
    db: Session, actor: UsuarioORM, run: int, activo: bool
) -> UsuarioORM:
    """Activa o desactiva a un usuario, sin dejar al sistema sin administradores."""
    objetivo = db.get(UsuarioORM, run)
    if objetivo is None:
        raise UsuarioNoEncontrado(f"No existe un usuario con RUN {run}.")

    admin = _a_admin_dominio(actor)
    dom = _a_usuario_dominio(objetivo)
    if activo:
        admin.reactivar_usuario(dom)
    else:
        if (
            objetivo.rol == RolUsuario.ADMINISTRADOR
            and objetivo.activo
            and _administradores_activos_distintos_de(db, run) == 0
        ):
            raise UltimoAdministrador("No puedes desactivar al último administrador activo.")
        admin.desactivar_usuario(dom)  # lanza ValueError si se desactiva a sí mismo

    objetivo.activo = dom.activo
    db.commit()
    db.refresh(objetivo)
    return objetivo


def resetear_password(db: Session, run: int, nueva: str) -> UsuarioORM:
    """Asigna una nueva contraseña a un usuario (concern de seguridad: solo aquí)."""
    objetivo = db.get(UsuarioORM, run)
    if objetivo is None:
        raise UsuarioNoEncontrado(f"No existe un usuario con RUN {run}.")
    if not nueva or len(nueva) < 4:
        raise ValueError("La contraseña debe tener al menos 4 caracteres.")

    objetivo.password_hash = hash_password(nueva)
    db.commit()
    db.refresh(objetivo)
    return objetivo


def cambiar_rol(
    db: Session,
    run: int,
    nuevo_rol: RolUsuario,
    especialidad_id: int | None = None,
    clinica_rut: str | None = None,
) -> UsuarioORM:
    """Reclasifica a un usuario cambiando el discriminador de la herencia.

    Es una operación de persistencia (no de dominio): se actualiza la columna
    `rol` y los campos propios del nuevo rol, limpiando los que no aplican.
    """
    objetivo = db.get(UsuarioORM, run)
    if objetivo is None:
        raise UsuarioNoEncontrado(f"No existe un usuario con RUN {run}.")

    valores = {"rol": nuevo_rol, "especialidad_id": None, "clinica_rut": None}
    if nuevo_rol == RolUsuario.MEDICO:
        if not especialidad_id or db.get(EspecialidadORM, especialidad_id) is None:
            raise EspecialidadNoEncontrada("Un médico necesita una especialidad válida.")
        valores["especialidad_id"] = especialidad_id
    elif nuevo_rol == RolUsuario.RECEPCIONISTA:
        rut = (clinica_rut or "").strip()
        if not rut:
            raise ValueError("Una recepcionista necesita el RUT de una clínica.")
        valores["clinica_rut"] = rut

    if (
        objetivo.rol == RolUsuario.ADMINISTRADOR
        and nuevo_rol != RolUsuario.ADMINISTRADOR
        and objetivo.activo
        and _administradores_activos_distintos_de(db, run) == 0
    ):
        raise UltimoAdministrador("No puedes quitar el rol al último administrador activo.")

    tabla = UsuarioORM.__table__
    db.execute(tabla.update().where(tabla.c.run_usuario == run).values(**valores))
    db.commit()
    # Cambió la subclase polimórfica: se descarta la instancia en memoria para
    # que al releer se materialice como el tipo correcto.
    db.expunge_all()
    return db.get(UsuarioORM, run)
