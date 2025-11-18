# main.py
import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configuración de logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Cargar token desde variable de entorno
TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    raise ValueError("No se encontró BOT_TOKEN en las variables de entorno")

# Función para /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy tu bot funcionando con PTB v20 🚀")

# Función principal
async def main():
    # Crear la aplicación
    app = ApplicationBuilder().token(TOKEN).build()

    # Agregar handlers
    app.add_handler(CommandHandler("start", start))

    # Ejecutar bot
    await app.run_polling()

# Arrancar la app
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

