import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes
import os

# Cargar unidades
with open("unidades.json") as f:
    unidades = json.load(f)

TOKEN = os.getenv("BOT_TOKEN")

print("TOKEN CARGADO:", TOKEN)  # Solo para debug, eliminar después

if not TOKEN:
    raise Exception("ERROR: BOT_TOKEN no está configurado en Render.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = """
👋 ¡Hola! Bienvenido al bot de rastreo de unidades.

📌 Para consultar una unidad:
- Haz clic en la unidad que deseas ver
- Recibirás información completa."""
    keyboard = [[InlineKeyboardButton(u, callback_data=u)] for u in unidades.keys()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(mensaje, reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    unidad = query.data
    u = unidades[unidad]
    mensaje = f"""
🚛 Unidad: {unidad}
📄 Placas: {u['placas']}
🏁 Origen: {u['origen']}
🎯 Destino: {u['destino']}
📍 Ubicación: {u['posicion']['lat']}, {u['posicion']['lon']}
⏱ ETA: {u['eta_minutos']} min
👨‍✈️ Chofer: {u['chofer']}
🚀 Velocidad: {u['velocidad']} km/h
🌍 Ver mapa: https://maps.google.com/?q={u['posicion']['lat']},{u['posicion']['lon']}
"""
    await query.edit_message_text(text=mensaje)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
