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
# 1. CONFIGURACIÓN DEL SERVIDOR DUMMY & AUTO-PING
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
    # Render asigna el puerto dinámicamente
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"--- Dummy server escuchando en el puerto {port} ---")
    server.serve_forever()

def ping_self():
    """Mantiene el bot despierto"""
    url = os.environ.get("RENDER_EXTERNAL_URL") 
    if not url:
        return
    while True:
        time.sleep(600) # 10 minutos
        try:
            requests.get(url)
        except Exception:
            pass

# ---------------------------------------------------------
# 2. CARGA DE DATOS
# ---------------------------------------------------------
UNIDADES = {}

def cargar_datos():
    global UNIDADES
    try:
        with open('unidades.json', 'r', encoding='utf-8') as f:
            UNIDADES = json.load(f)
    except Exception as e:
        print(f"Error cargando JSON: {e}")
        UNIDADES = {}

# ---------------------------------------------------------
# 3. COMANDOS DEL BOT
# ---------------------------------------------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")

# --- COMANDO /start (CON SEMÁFORO 🚦) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargar_datos()
    
    if not UNIDADES:
        await update.message.reply_text("⚠️ No hay datos de unidades disponibles.")
        return

    user = update.effective_user
    mensaje = f"👋 Hola {user.first_name}, bienvenido a la Torre de Control.\n\nSelecciona una unidad:"
    
    keyboard = []
    for nombre, datos in UNIDADES.items():
        # Lógica del Semáforo: Si velocidad > 0 es verde, si es 0 es rojo
        vel = datos.get('velocidad', 0)
        if vel > 0:
            icono = "🟢" # En movimiento
        elif vel == 0:
            icono = "🔴" # Detenido
        else:
            icono = "⚠️" # Sin datos
            
        # Texto del botón: "🟢 Unidad 01 (85 km/h)"
        texto_boton = f"{icono} {nombre} ({vel} km/h)"
        keyboard.append([InlineKeyboardButton(texto_boton, callback_data=nombre)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(mensaje, reply_markup=reply_markup)

# --- COMANDO /resumen (ESTADÍSTICAS 📊) ---
async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargar_datos()
    total = len(UNIDADES)
    
    # Contamos cuántas se mueven
    movimiento = sum(1 for u in UNIDADES.values() if u.get('velocidad', 0) > 0)
    detenidas = total - movimiento
    
    msg = f"""
📊 **Resumen de Flota**

🚛 Total Unidades: *{total}*
🟢 En Movimiento: *{movimiento}*
🔴 Detenidas: *{detenidas}*
    """
    await update.message.reply_text(msg, parse_mode="Markdown")

# --- COMANDO /buscar (BÚSQUEDA 🔍) ---
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Une lo que escriba el usuario (ej: /buscar unidad 1 -> "unidad 1")
    query = " ".join(context.args).lower()
    
    if not query:
        await update.message.reply_text("🔍 Uso: `/buscar [placa o nombre]`\nEjemplo: `/buscar ABC`", parse_mode="Markdown")
        return

    cargar_datos()
    encontradas = []
    
    for nombre, datos in UNIDADES.items():
        # Busca coincidencia en el Nombre O en las Placas
        if query in nombre.lower() or query in datos.get('placas', '').lower():
            encontradas.append(nombre)

    if not encontradas:
        await update.message.reply_text("❌ No se encontró ninguna unidad con esos datos.")
    elif len(encontradas) == 1:
        # Si solo hay una coincidencia, mostramos el detalle directo
        u = UNIDADES[encontradas[0]]
        await enviar_detalle_unidad(update, found_name=encontradas[0], u_data=u)
    else:
        # Si hay varias, mostramos botones para que elija
        keyboard = [[InlineKeyboardButton(u, callback_data=u)] for u in encontradas]
        await update.message.reply_text(f"🔍 Encontré {len(encontradas)} coincidencias:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- HANDLER DE BOTONES ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Si presionan "Volver al menú"
    if data == "MENU_PRINCIPAL":
        keyboard = []
        for nombre, datos in UNIDADES.items():
            vel = datos.get('velocidad', 0)
            icono = "🟢" if vel > 0 else "🔴"
            texto = f"{icono} {nombre} ({vel} km/h)"
            keyboard.append([InlineKeyboardButton(texto, callback_data=nombre)])
        
        await query.edit_message_text("Selecciona una unidad:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Si presionan una Unidad
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
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data="MENU_PRINCIPAL")]]
        await query.edit_message_text(text=mensaje_detalle, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# Función auxiliar para enviar detalle desde el buscador
async def enviar_detalle_unidad(update, found_name, u_data):
    mensaje_detalle = f"""
🚛 *Unidad:* {found_name}
📄 *Placas:* `{u_data.get('placas', 'N/A')}`
🚀 *Velocidad:* {u_data.get('velocidad', 0)} km/h
📍 [Ver en Mapa](https://maps.google.com/?q={u_data['posicion']['lat']},{u_data['posicion']['lon']})
    """
    await update.message.reply_text(mensaje_detalle, parse_mode="Markdown")

# ---------------------------------------------------------
# 4. EJECUCIÓN PRINCIPAL
# ---------------------------------------------------------
def main():
    if not TOKEN:
        print("ERROR: No se encontró BOT_TOKEN")
        return

    cargar_datos()
    
    # Iniciar hilos de Render (Servidor + Ping)
    Thread(target=run_dummy_server, daemon=True).start()
    Thread(target=ping_self, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()
    
    # Registrar comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("resumen", resumen))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("--- Bot con Mejoras (Sin Seguridad) iniciado ---")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
