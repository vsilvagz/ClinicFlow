"""Cliente del asistente: traduce lenguaje natural a una intención estructurada.

Habla con cualquier servidor compatible con la API de OpenAI (Groq en la nube,
un llama.cpp local, etc.) según la configuración. El modelo solo clasifica el
mensaje y extrae parámetros; nunca ejecuta acciones ni decide reglas de negocio.

El módulo separa tres responsabilidades para poder probar la lógica sin red:
  - `construir_mensajes`: arma el prompt (puro).
  - `parsear_intencion`: valida la respuesta del modelo (puro y tolerante a fallos).
  - `interpretar`: orquesta y realiza la llamada al proveedor.
"""

import json
from datetime import datetime
from functools import lru_cache

from app.backend.ai.intenciones import AccionAsistente, IntencionAsistente
from app.backend.core.config import settings

# Días de la semana en español para dar contexto temporal al modelo y que
# resuelva expresiones relativas ("mañana", "el viernes") a fechas concretas.
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _descripcion_campos() -> str:
    """Lista los campos del contrato a partir del modelo, para no duplicarlos."""
    lineas = []
    for nombre, campo in IntencionAsistente.model_fields.items():
        lineas.append(f'  - "{nombre}": {campo.description}')
    return "\n".join(lineas)


def _instrucciones_sistema() -> str:
    acciones = ", ".join(a.value for a in AccionAsistente)
    return (
        "Eres el asistente de una plataforma de gestión clínica. Tu tarea es "
        "interpretar el mensaje de un paciente y devolver SOLO un objeto JSON, "
        "sin texto adicional ni bloques de código.\n\n"
        f'El campo "accion" debe ser uno de: {acciones}.\n'
        "Si el mensaje no corresponde a ninguna acción, usa \"desconocida\".\n\n"
        "El objeto JSON tiene estos campos:\n"
        f"{_descripcion_campos()}\n\n"
        "Reglas:\n"
        "  - Extrae solo lo que el paciente realmente dijo; no inventes datos.\n"
        "  - Resuelve fechas y horas relativas a partir de la fecha actual que "
        "se indica, y exprésalas en formato ISO 8601.\n"
        "  - Deja en null cualquier parámetro que el paciente no haya indicado.\n"
        '  - Escribe "respuesta" en español, breve y cordial.'
    )


def construir_mensajes(mensaje: str, ahora: datetime) -> list[dict]:
    """Arma la lista de mensajes para la API a partir del texto del paciente."""
    contexto_temporal = (
        f"Fecha y hora actual: {ahora.isoformat(timespec='minutes')} "
        f"({_DIAS[ahora.weekday()]})."
    )
    return [
        {"role": "system", "content": _instrucciones_sistema()},
        {"role": "system", "content": contexto_temporal},
        {"role": "user", "content": mensaje},
    ]


def parsear_intencion(contenido: str) -> IntencionAsistente:
    """Valida la respuesta del modelo; si algo falla, devuelve DESCONOCIDA.

    Tolera que el modelo envuelva el JSON en un bloque de código ```json.
    """
    texto = contenido.strip()
    if texto.startswith("```"):
        # Quita la primera línea (``` o ```json) y el cierre ```.
        texto = texto.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        datos = json.loads(texto)
        return IntencionAsistente.model_validate(datos)
    except Exception:
        return IntencionAsistente(
            accion=AccionAsistente.DESCONOCIDA,
            respuesta="No entendí tu solicitud. ¿Puedes reformularla?",
        )


@lru_cache
def _cliente_openai():
    """Crea (una sola vez) el cliente compatible con OpenAI desde la config."""
    from openai import OpenAI

    return OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


def interpretar(mensaje: str, ahora: datetime | None = None) -> IntencionAsistente:
    """Interpreta el mensaje del paciente y devuelve una intención validada.

    Si no hay proveedor configurado o la llamada falla, devuelve una intención
    DESCONOCIDA con un mensaje claro, de modo que la aplicación nunca se rompa
    por culpa del modelo.
    """
    ahora = ahora or datetime.now()

    if not settings.llm_api_key:
        return IntencionAsistente(
            accion=AccionAsistente.DESCONOCIDA,
            respuesta="El asistente no está disponible en este momento.",
        )

    try:
        respuesta = _cliente_openai().chat.completions.create(
            model=settings.llm_model,
            messages=construir_mensajes(mensaje, ahora),
            response_format={"type": "json_object"},
            temperature=0,
        )
        return parsear_intencion(respuesta.choices[0].message.content or "")
    except Exception:
        return IntencionAsistente(
            accion=AccionAsistente.DESCONOCIDA,
            respuesta="No pude procesar tu solicitud en este momento.",
        )
