import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from app.backend.ai.cliente import interpretar
from app.backend.ai.despachador import despachar
from app.backend.core.database import SessionLocal 

# Token y un ID de paciente de prueba (para que el bot sepa quién es)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "PONER_TOKEN_AQUI")
PACIENTE_ID_PRUEBA = 1 

async def start(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="¡Hola! Soy ClinicFlow. ¿En qué te puedo ayudar hoy?")

async def echo(update, context):
    mensaje_usuario = update.message.text
    
    # 1. Se crea la sesión de base de datos
    db = SessionLocal()
    try:
        # 2. Se interpreta el mensaje (se convierte en una intención traducida por la ia)
        intencion = interpretar(mensaje_usuario)
        
        # 3. Se despacha la acción (ejecutamos contra la BD)
        respuesta = despachar(db, PACIENTE_ID_PRUEBA, intencion)
        
        # 4. Enviamos la respuesta al paciente
        await context.bot.send_message(chat_id=update.effective_chat.id, text=respuesta)
    finally:
        # Cerramos la conexión a la base de datos
        db.close()

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))
    
    print("Bot encendido y conectado al cerebro de ClinicFlow...")
    application.run_polling()
