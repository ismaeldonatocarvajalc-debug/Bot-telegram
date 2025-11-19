# main.py
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Obtén el token desde las variables de entorno
TOKEN = os.environ.get("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("No se ha encontrado la variable de entorno TELEGRAM_TOKEN")

# Comando de prueba /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! El bot está funcionando correctamente 🚀")

def main():
    # Crea la aplicación
    app = ApplicationBuilder().token(TOKEN).build()

    # Agrega el comando /start
    app.add_handler(CommandHandler("start", start))

    # Ejecuta el bot
    print("Bot iniciado...")
    app.run_polling()  # Esto maneja el loop de asyncio internamente

if __name__ == "__main__":
    main()
