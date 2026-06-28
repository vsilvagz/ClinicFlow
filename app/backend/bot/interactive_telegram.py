import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Usa una variable de entorno para el token por seguridad
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "PONER_TOKEN_AQUI")

async def start(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="¡Hola! Soy el bot de ClinicFlow.")

async def echo(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Recibí tu mensaje: {update.message.text}")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))
    
    print("Bot encendido...")
    application.run_polling()
