"""Esquemas Pydantic (DTOs) de los usuarios y sus roles.

La jerarquía de roles del dominio (Paciente, Medico, Recepcionista,
Administrador) se refleja aquí con esquemas de entrada distintos: cada rol pide
exactamente los datos que necesita (p. ej. el médico exige `especialidad_id`).
La salida usa un esquema común más los campos propios de cada rol.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.backend.domain.enums import RolUsuario


# ──────────────────────────────────────────────────────────────────────────────
# Entrada (lo que el cliente envía al crear un usuario).
# ──────────────────────────────────────────────────────────────────────────────

class _UsuarioBase(BaseModel):
    """Campos comunes a todos los roles al registrarse."""

    run_usuario: int = Field(gt=0, description="RUN (sin dígito verificador).")
    nombre: str = Field(min_length=1, max_length=150)
    correo: EmailStr
    telefono: int = Field(gt=0)
    # Opcional: si se entrega, habilita el inicio de sesión de ese usuario.
    password: str | None = Field(default=None, min_length=4, max_length=128)


class PacienteCrear(_UsuarioBase):
    """Un paciente no agrega campos propios."""


class MedicoCrear(_UsuarioBase):
    """Un médico debe declarar la especialidad que atiende."""

    especialidad_id: int = Field(gt=0)


class RecepcionistaCrear(_UsuarioBase):
    """Una recepcionista trabaja en una clínica (identificada por su RUT)."""

    clinica_rut: str = Field(min_length=1, max_length=20)


class AdministradorCrear(_UsuarioBase):
    """Un administrador no agrega campos propios."""


# ──────────────────────────────────────────────────────────────────────────────
# Salida (lo que la API devuelve).
# ──────────────────────────────────────────────────────────────────────────────

class UsuarioLeer(BaseModel):
    """Vista pública común de cualquier usuario."""

    model_config = ConfigDict(from_attributes=True)

    run_usuario: int
    nombre: str
    correo: str
    telefono: int
    rol: RolUsuario


class MedicoLeer(UsuarioLeer):
    """Vista de un médico: añade su especialidad."""

    especialidad_id: int | None = None
