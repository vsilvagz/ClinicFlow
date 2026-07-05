"""Bot de Telegram del asistente conversacional de ClinicFlow.

Es el canal de Telegram del asistente: reúne las mismas dos mitades que la web
—interpretar (modelo de lenguaje) y despachar (servicios de negocio)— pero por
un chat de Telegram. La diferencia clave frente a un login web es que aquí no hay
sesión con cookie: cada persona se identifica por el `chat_id` de su chat, así
que primero debe VINCULAR su cuenta con /vincular <RUN> <contraseña>. A partir de
ahí el bot sabe qué paciente es y opera sobre su cuenta real.

Diseño:
  - Toda la lógica que toca la base de datos vive en funciones SÍNCRONAS puras
    (`_responder`, `_vincular`, `_desvincular`), fáciles de testear sin Telegram
    ni red. Las reglas de negocio siguen en `services/` y `domain/`.
  - `telegram` se importa de forma PEREZOSA dentro de `construir_bot()`: el módulo
    puede importarse (y testearse) aunque la librería no esté instalada, y la app
    web arranca sin problemas cuando no hay token configurado.
  - Los handlers async delegan el trabajo pesado (incluida la llamada al LLM, que
    es de red y lenta) a un hilo con `asyncio.to_thread`, para no bloquear el
    bucle de eventos que comparten el bot y el servidor web.
"""

import asyncio

from app.backend.ai.cliente import interpretar
from app.backend.ai.despachador import despachar
from app.backend.core.config import settings
from app.backend.core.database import SessionLocal
from app.backend.core.rut import parsear_run
from app.backend.models.conversacion import ROL_ASISTENTE, ROL_USUARIO
from app.backend.repositories.conversacion import RepositorioConversacion
from app.backend.repositories.usuarios import RepositorioUsuarios
from app.backend.services.usuarios_service import (
    CredencialesInvalidas,
    SoloPacientesEnTelegram,
    desvincular_telegram,
    vincular_telegram,
)

# ──────────────────────────────────────────────────────────────────────────────
# Textos fijos que el bot envía. Se centralizan para mantener un tono coherente.
# ──────────────────────────────────────────────────────────────────────────────

MENSAJE_BIENVENIDA = (
    "¡Hola! Soy el asistente de ClinicFlow. 🩺\n\n"
    "Para atenderte necesito saber quién eres. Vincula tu cuenta con:\n"
    "  /vincular <RUN> <contraseña>\n"
    "Por ejemplo:  /vincular 44444444 demo1234\n\n"
    "Después podrás pedirme cosas como «agenda una hora de cardiología para el "
    "lunes a las 10», «cancela mi cita» o «¿qué horas hay disponibles?».\n"
    "Escribe /ayuda para ver todo lo que puedo hacer."
)

MENSAJE_AYUDA = (
    "Puedo ayudarte con tus horas médicas. Primero vincula tu cuenta y luego "
    "escríbeme en lenguaje natural. Ejemplos:\n"
    "  • «Agenda una hora de cardiología para mañana a las 9».\n"
    "  • «¿Qué horas de pediatría hay el viernes?».\n"
    "  • «Reagenda mi cita al martes a las 15».\n"
    "  • «Cancela mi hora de cardiología».\n"
    "  • «Inscríbeme en la lista de espera de cardiología».\n"
    "  • «¿Cuáles son mis próximas citas?».\n\n"
    "Comandos:\n"
    "  /vincular <RUN> <contraseña> — asocia tu cuenta a este chat.\n"
    "  /salir — desvincula tu cuenta de este chat.\n"
    "  /ayuda — muestra esta ayuda."
)

MENSAJE_NO_VINCULADO = (
    "Aún no vinculas tu cuenta a este chat. Hazlo con:\n"
    "  /vincular <RUN> <contraseña>\n"
    "Por ejemplo:  /vincular 44444444 demo1234"
)

MENSAJE_USO_VINCULAR = (
    "Uso: /vincular <RUN> <contraseña>\n"
    "Por ejemplo:  /vincular 44444444 demo1234"
)

MENSAJE_ERROR_GENERICO = (
    "Ups, algo salió mal procesando tu mensaje. Intenta de nuevo en un momento."
)


# ──────────────────────────────────────────────────────────────────────────────
# Lógica síncrona (con base de datos). No depende de Telegram: se puede testear
# directamente. Cada función abre su propia sesión y la cierra al terminar.
# ──────────────────────────────────────────────────────────────────────────────

def _responder(chat_id: int, texto: str) -> str:
    """Interpreta el mensaje del chat y devuelve la respuesta del asistente.

    Resuelve el paciente a partir del `chat_id`; si el chat no está vinculado,
    pide vincular. En caso contrario reúne el historial (contexto multi-turno),
    interpreta la intención con el modelo y la ejecuta contra los servicios.
    """
    db = SessionLocal()
    try:
        paciente = RepositorioUsuarios(db).obtener_paciente_por_chat(chat_id)
        if paciente is None:
            return MENSAJE_NO_VINCULADO

        chat = RepositorioConversacion(db)
        # El historial previo se carga ANTES de añadir el turno actual, para no
        # duplicarlo, igual que en el asistente web.
        historial = [
            (t.rol, t.contenido)
            for t in chat.ultimos_de_paciente(paciente.run_usuario)
        ]
        intencion = interpretar(texto, historial=historial)
        respuesta = despachar(db, paciente.run_usuario, intencion)

        chat.agregar_turno(paciente.run_usuario, ROL_USUARIO, texto)
        chat.agregar_turno(paciente.run_usuario, ROL_ASISTENTE, respuesta)
        return respuesta
    finally:
        db.close()


def _vincular(chat_id: int, args: list[str]) -> str:
    """Procesa el comando /vincular y devuelve el mensaje de respuesta."""
    if len(args) < 2:
        return MENSAJE_USO_VINCULAR

    run = parsear_run(args[0])
    # La contraseña puede traer espacios: unimos el resto de los argumentos.
    password = " ".join(args[1:])
    if run is None:
        return (
            "El RUN no es válido. Ejemplo:\n"
            "  /vincular 12.345.678-9 tu_contraseña"
        )

    db = SessionLocal()
    try:
        paciente = vincular_telegram(db, run, password, chat_id)
    except CredencialesInvalidas:
        return "RUN o contraseña incorrectos. Revisa tus datos e intenta de nuevo."
    except SoloPacientesEnTelegram:
        return "Solo las cuentas de paciente pueden usar el bot de Telegram."
    finally:
        db.close()

    return (
        f"¡Listo, {paciente.nombre}! Tu cuenta quedó vinculada a este chat. "
        "Ya puedes pedirme agendar, cancelar, reagendar o consultar tus horas. "
        "Escribe /ayuda para ver ejemplos."
    )


def _desvincular(chat_id: int) -> str:
    """Procesa el comando /salir y devuelve el mensaje de respuesta."""
    db = SessionLocal()
    try:
        habia_vinculo = desvincular_telegram(db, chat_id)
    finally:
        db.close()
    if habia_vinculo:
        return "Tu cuenta fue desvinculada de este chat. Hasta pronto. 👋"
    return "Este chat no tenía ninguna cuenta vinculada."


# ──────────────────────────────────────────────────────────────────────────────
# Handlers de Telegram (async). Son finos: delegan a las funciones síncronas de
# arriba en un hilo aparte y se limitan a enviar la respuesta. No se anota su
# firma con tipos de `telegram` para no forzar la importación de la librería al
# cargar el módulo.
# ──────────────────────────────────────────────────────────────────────────────

async def _enviar(update, texto: str) -> None:
    """Responde al chat, tolerando que el update no traiga mensaje."""
    if update.message is not None:
        await update.message.reply_text(texto)


async def cmd_start(update, context) -> None:
    await _enviar(update, MENSAJE_BIENVENIDA)


async def cmd_ayuda(update, context) -> None:
    await _enviar(update, MENSAJE_AYUDA)


async def cmd_vincular(update, context) -> None:
    chat_id = update.effective_chat.id
    try:
        texto = await asyncio.to_thread(_vincular, chat_id, context.args)
    except Exception:  # noqa: BLE001 — el bot nunca debe caerse por un error puntual.
        texto = MENSAJE_ERROR_GENERICO
    await _enviar(update, texto)


async def cmd_salir(update, context) -> None:
    chat_id = update.effective_chat.id
    try:
        texto = await asyncio.to_thread(_desvincular, chat_id)
    except Exception:  # noqa: BLE001
        texto = MENSAJE_ERROR_GENERICO
    await _enviar(update, texto)


async def on_mensaje(update, context) -> None:
    if update.message is None or not update.message.text:
        return
    chat_id = update.effective_chat.id
    try:
        texto = await asyncio.to_thread(_responder, chat_id, update.message.text)
    except Exception:  # noqa: BLE001
        texto = MENSAJE_ERROR_GENERICO
    await _enviar(update, texto)


# ──────────────────────────────────────────────────────────────────────────────
# Construcción del bot. Importa `telegram` de forma perezosa: solo se necesita si
# hay token configurado. Devuelve None cuando no hay token, para que la app web
# arranque sin bot (y sin exigir la librería) en entornos sin Telegram.
# ──────────────────────────────────────────────────────────────────────────────

def construir_bot():
    """Arma la Application de Telegram con sus handlers, o None si no hay token."""
    token = settings.telegram_bot_token
    if not token:
        return None

    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        MessageHandler,
        filters,
    )

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("ayuda", cmd_ayuda))
    application.add_handler(CommandHandler("vincular", cmd_vincular))
    application.add_handler(CommandHandler("salir", cmd_salir))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_mensaje)
    )
    return application


# ──────────────────────────────────────────────────────────────────────────────
# Ejecución como proceso independiente: `python -m app.backend.bot.interactive_telegram`.
# Útil para desarrollo o para correr el bot separado de la web. En despliegue, la
# app lo arranca en su mismo proceso desde el lifespan de FastAPI (ver main.py).
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot = construir_bot()
    if bot is None:
        raise SystemExit(
            "Configura TELEGRAM_BOT_TOKEN en el entorno para arrancar el bot."
        )
    print("Bot de ClinicFlow encendido. Ctrl+C para detener…")
    bot.run_polling()
