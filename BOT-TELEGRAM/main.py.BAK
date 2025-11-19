import os
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DEL SERVIDOR DUMMY (Para que Render no te mate)
# ---------------------------------------------------------
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_dummy_server():
    # Render te da el puerto en la variable de entorno PORT
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"--- Dummy server escuchando en el puerto {port} ---")
    server.serve_forever()

# ---------------------------------------------------------
# 2. LÓGICA DEL BOT
# ---------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")

# Handler del comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy tu bot en Render y estoy VIVO 🚀")

# ---------------------------------------------------------
# 3. FUNCIÓN PRINCIPAL (SIN ASYNC)
# ---------------------------------------------------------
def main():
    if not TOKEN:
        print("ERROR: No se encontró la variable BOT_TOKEN.")
        return

    # A) Arrancar el servidor web falso en un hilo separado
    # Esto se ejecuta en paralelo y mantiene a Render feliz
    web_thread = Thread(target=run_dummy_server, daemon=True)
    web_thread.start()

    # B) Configurar el Bot
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print("--- Bot iniciado y esperando mensajes ---")
    
    # C) Ejecutar el polling (BLOQUEANTE)
    # IMPORTANTE: No usar await ni asyncio.run() aquí
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
