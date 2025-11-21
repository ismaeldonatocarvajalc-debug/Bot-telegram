import os
import logging
import time
import json
import csv
import io
import re
import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# ---------------------------------------------------------
# 1. INFRAESTRUCTURA (Servidor Ligero)
# ---------------------------------------------------------
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    # Desactivamos logs del servidor web para ahorrar espacio en consola
    def log_message(self, format, *args):
        return

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"--- Servidor Web Activo en puerto {port} ---")
    server.serve_forever()

# ---------------------------------------------------------
# 2. DATOS
# ---------------------------------------------------------
UNIDADES = {}
HISTORIAL_RAM = [] 
ALERTAS_ENVIADAS = {} 
CHATS_SUSCRITOS = set() 

LIMITE_VELOCIDAD = 110 
DEFAULT_LIMIT = 120 

def cargar_datos():
    global UNIDADES
    try:
        with open('unidades.json', 'r', encoding='utf-8') as f:
            UNIDADES = json.load(f)
    except Exception as e:
        print(f"Error JSON: {e}")
        UNIDADES = {}

def parse_tiempo_a_minutos(tiempo_str):
    if not tiempo_str: return 0
    total_min = 0
    dias = re.search(r'(\d+)d', tiempo_str)
    horas = re.search(r'(\d+)h', tiempo_str)
    mins = re.search(r'(\d+)m', tiempo_str)
    if dias: total_min += int(dias.group(1)) * 1440
    if horas: total_min += int(horas.group(1)) * 60
    if mins: total_min += int(mins.group(1))
    return total_min

# ---------------------------------------------------------
# 3. MONITOR AUTOMÁTICO (Optimizado)
# ---------------------------------------------------------
async def monitor_automatico(context: ContextTypes.DEFAULT_TYPE):
    cargar_datos() 
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M") # Sin segundos para ahorrar ram
    
    if not UNIDADES: return

    for nombre, u in UNIDADES.items():
        velocidad = u.get('velocidad', 0)
        en_taller = u.get('en_taller', False)
        chofer = u.get('chofer', 'Sin Asignar')
        tiempo_str = u.get('tiempo_detenido', '0m')
        minutos_detenido = parse_tiempo_a_minutos(tiempo_str)
        limite = u.get('limite_estadia', DEFAULT_LIMIT)

        estatus_historial = "RUTA"
        if en_taller: estatus_historial = "TALLER"
        elif velocidad > LIMITE_VELOCIDAD: estatus_historial = f"EXCESO {velocidad}"
        elif velocidad > 0 and (chofer == "Sin Asignar" or chofer == ""): estatus_historial = "SIN CHOFER"
        elif velocidad == 0:
            if minutos_detenido > limite: estatus_historial = f"⚠️ EXCEDIDO"
            else: estatus_historial = "DETENIDO"

        registro = {
            "t": timestamp, "u": nombre, "v": velocidad, "e": estatus_historial,
            "ref": u.get('referencia')[:20] # Recortamos texto largo para ahorrar RAM
        }
        HISTORIAL_RAM.append(registro)

        # ALERTAS PUSH
        if velocidad == 0 and not en_taller and minutos_detenido > limite:
            ultima_alerta = ALERTAS_ENVIADAS.get(nombre, 0)
            ahora = time.time()
            if (ahora - ultima_alerta) > 14400:
                mensaje_alerta = f"🚨 *ESTADÍA EXCEDIDA* 🚨\n🚛 {nombre}\n⏱ {tiempo_str} (Max {limite}m)\n📍 {u.get('referencia')}"
                for chat_id in CHATS_SUSCRITOS:
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=mensaje_alerta, parse_mode="Markdown")
                    except: pass
                ALERTAS_ENVIADAS[nombre] = ahora
        else:
            if nombre in ALERTAS_ENVIADAS: del ALERTAS_ENVIADAS[nombre]
                
    # --- OPTIMIZACIÓN DE MEMORIA ---
    # Bajamos de 5000 a 1000 registros máximo para no saturar la RAM gratis
    if len(HISTORIAL_RAM) > 1000: 
        del HISTORIAL_RAM[:100]

# ---------------------------------------------------------
# 4. LÓGICA VISUAL
# ---------------------------------------------------------
def armar_teclado_menu():
    keyboard = []
    for nombre, datos in UNIDADES.items():
        vel = datos.get('velocidad', 0)
        en_taller = datos.get('en_taller', False)
        chofer = datos.get('chofer', 'Sin Asignar')
        
        if en_taller: icono = "🔧"; txt = "Mantenimiento"
        elif vel > 0 and (chofer == "Sin Asignar" or chofer == ""): icono = "👻"; txt = "SIN CHOFER"
        elif vel > LIMITE_VELOCIDAD: icono = "🚨"; txt = f"{vel} km/h"
        elif vel > 0: icono = "🟢"; txt = f"{vel} km/h"
        else: icono = "🔴"; txt = f"{datos.get('tiempo_detenido', '0m')}"
            
        keyboard.append([InlineKeyboardButton(f"{icono} {nombre} ({txt})", callback_data=nombre)])
    return InlineKeyboardMarkup(keyboard)

# ---------------------------------------------------------
# 5. COMANDOS
# ---------------------------------------------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargar_datos()
    user = update.effective_user
    await update.message.reply_text(f"👋 Hola {user.first_name}.", reply_markup=armar_teclado_menu())

async def activar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    CHATS_SUSCRITOS.add(chat_id)
    await update.message.reply_text("🔔 Alertas ON")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "MENU_PRINCIPAL":
        cargar_datos()
        await query.edit_message_text("👋 Panel Geotab.", reply_markup=armar_teclado_menu())
        return
    if data in UNIDADES:
        u = UNIDADES[data]
        msg = f"🚛 *{data}*\nRef: `{u.get('referencia')}`\nPlacas: `{u.get('placas')}`\nVel: *{u.get('velocidad')} km/h*\nChofer: {u.get('chofer')}"
        kb = [[InlineKeyboardButton("🔙 Volver", callback_data="MENU_PRINCIPAL")]]
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HISTORIAL_RAM: return await update.message.reply_text("⏳ Sin datos...")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Fecha', 'Unidad', 'Vel', 'Estatus', 'Ref'])
    for r in HISTORIAL_RAM:
        writer.writerow([r['t'], r['u'], r['v'], r['e'], r['ref']])
    output.seek(0)
    doc = io.BytesIO(output.getvalue().encode('utf-8'))
    doc.name = f"Historial.csv"
    await update.message.reply_document(document=doc)

async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📊 Total Unidades: {len(UNIDADES)}")

# ---------------------------------------------------------
# 6. EJECUCIÓN
# ---------------------------------------------------------
def main():
    if not TOKEN: return
    cargar_datos()
    Thread(target=run_dummy_server, daemon=True).start()
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.job_queue.run_repeating(monitor_automatico, interval=60, first=10)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("activar", activar))
    app.add_handler(CommandHandler("resumen", resumen))
    app.add_handler(CommandHandler("historial", historial))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("--- Bot Optimizado V2 (Polling Fix) ---")
    # CORRECCIÓN: Eliminamos los timeouts manuales que causaban error
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
