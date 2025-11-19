import os
import logging
import time
import json
import requests
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DEL SERVIDOR DUMMY (Engaña a Render)
# ---------------------------------------------------------
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_dummy_server():
    # Render asigna un puerto dinámico en la variable PORT
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"--- Dummy server escuchando en el puerto {port} ---")
    server.serve_forever()

# ---------------------------------------------------------
# 2. AUTO-PING (Evita que el bot se duerma)
# ---------------------------------------------------------
def ping_self():
    """Se llama a sí mismo cada 10 minutos para mantenerse despierto"""
    url = os.environ.get("RENDER_EXTERNAL_URL") 
    
    if not url:
        print("⚠️ No se encontró RENDER_EXTERNAL_URL. El auto-ping no funcionará hasta el deploy.")
        return

    print(f"--- Iniciando Auto-Ping a: {url} ---")
    while True:
        time.sleep(600)  # 600 segundos = 10 minutos
        try:
            response = requests.get(url)
            print(f"Ping enviado a {url}. Estado: {response.status_code}")
        except Exception as e:
            print(f"Error en auto-ping: {e}")

# ---------------------------------------------------------
# 3. CARGA DE DATOS (JSON)
# ---------------------------------------------------------
UNIDADES = {}

def cargar_datos():
    global UNIDADES
    try:
        with open('unidades.json', 'r', encoding='utf-8') as f:
            UNIDADES = json.load(f)
            print(f"--- Datos cargados: {len(UNIDADES)} unidades ---")
    except FileNotFoundError:
        print("⚠️ ERROR: No existe 'unidades.json'. Sube el archivo a GitHub.")
        UNIDADES = {} 
    except json.JSONDecodeError:
        print("⚠️ ERROR: Formato inválido en 'unidades.json'.")

# ---------------------------------------------------------
# 4. LÓGICA DEL BOT (Botones)
# ---------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargar_datos() # Recarga el JSON al usar /start
    
    if not UNIDADES:
        await update.message.reply_text("⚠️ No hay datos de unidades disponibles.")
        return

    mensaje = "👋 **Sistema de Rastreo**\n\nSelecciona una unidad para ver detalles:"
    
    # Crea un botón por cada clave en el JSON
    keyboard = [[InlineKeyboardButton(u, callback_data=u)] for u in UNIDADES.keys()]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(mensaje, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Avisa a Telegram que recibimos el clic
    
    data = query.data
    
    # Opción: Volver al Menú
    if data == "MENU_PRINCIPAL":
        keyboard = [[InlineKeyboardButton(u, callback_data=u)] for u in UNIDADES.keys()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Selecciona una unidad:", reply_markup=reply_markup)
        return

    # Opción: Mostrar Info de Unidad
    if data in UNIDADES:
        u = UNIDADES[data]
        
        mensaje_detalle = f"""
🚛 *Unidad:* {data}
📄 *Placas:* `{u.get('placas', 'N/A')}`
🏁 *Origen:* {u.get('origen', '?')}
🎯 *Destino:* {u.get('destino', '?')}
⏱ *ETA:* {u.get('eta_minutos', 0)} min
👨‍✈️ *Chofer:* {u.get('chofer', 'Desconocido')}
🚀 *Velocidad:* {u.get('velocidad', 0)} km/h

📍 *Ubicación:* `{u['posicion']['lat']}, {u['posicion']['lon']}`
[🌍 Ver en Mapa](https://maps.google.com/?q={u['posicion']['lat']},{u['posicion']['lon']})
        """
        
        # Botón para regresar
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data="MENU_PRINCIPAL")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text=mensaje_detalle, parse_mode="Markdown", reply_markup=reply_markup)

# ---------------------------------------------------------
# 5. EJECUCIÓN PRINCIPAL
# ---------------------------------------------------------
def main():
    if not TOKEN:
        print("ERROR FATAL: No hay BOT_TOKEN en las variables de entorno.")
        return

    cargar_datos()

    # Iniciar hilos en segundo plano (Servidor y Ping)
    Thread(target=run_dummy_server, daemon=True).start()
    Thread(target=ping_self, daemon=True).start()

    # Iniciar el Bot
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("--- Bot iniciado correctamente ---")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
