import os
import logging
import time
import json
import requests
import csv
import io
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
 
# ---------------------------------------------------------
# 1. INFRAESTRUCTURA
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
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    print(f"--- Dummy server en puerto {port} ---")
    server.serve_forever()
 
def ping_self():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url: return
    while True:
        time.sleep(600)
        try: requests.get(url)
        except: pass
 
# ---------------------------------------------------------
# 2. DATOS
# ---------------------------------------------------------
UNIDADES = {}
LIMITE_VELOCIDAD = 110
 
def cargar_datos():
    global UNIDADES
    try:
        with open('unidades.json', 'r', encoding='utf-8') as f:
            UNIDADES = json.load(f)
    except Exception as e:
        print(f"Error JSON: {e}")
        UNIDADES = {}
 
# ---------------------------------------------------------
# 3. LÓGICA VISUAL (Helpers)
# ---------------------------------------------------------
def armar_teclado_menu():
    """Genera los botones del menú principal basado en el estatus actual."""
    keyboard = []
    for nombre, datos in UNIDADES.items():
        vel = datos.get('velocidad', 0)
        en_taller = datos.get('en_taller', False)
        chofer = datos.get('chofer', 'Sin Asignar')
        
        # LÓGICA DE ICONOS
        if en_taller:
            icono = "🔧" # Taller
            estado_txt = "Mantenimiento"
        elif vel > 0 and (chofer == "Sin Asignar" or chofer == ""):
            icono = "👻" # Fantasma
            estado_txt = "SIN CHOFER"
        elif vel > LIMITE_VELOCIDAD:
            icono = "🚨" # Exceso
            estado_txt = f"{vel} km/h"
        elif vel > 0:
            icono = "🟢" # Movimiento
            estado_txt = f"{vel} km/h"
        else:
            icono = "🔴" # Detenido
            tiempo = datos.get('tiempo_detenido', '0m')
            estado_txt = f"Stop: {tiempo}"
            
        texto = f"{icono} {nombre} ({estado_txt})"
        keyboard.append([InlineKeyboardButton(texto, callback_data=nombre)])
    
    return InlineKeyboardMarkup(keyboard)
 
# ---------------------------------------------------------
# 4. COMANDOS
# ---------------------------------------------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")
 
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargar_datos()
    if not UNIDADES:
        await update.message.reply_text("⚠️ Sin datos.")
        return
 
    user = update.effective_user
    mensaje = f"👋 Hola {user.first_name}. Panel Geotab Telegram.\nSelecciona unidad:"
    
    # Usamos el helper para no duplicar código
    reply_markup = armar_teclado_menu()
 
    await update.message.reply_text(mensaje, reply_markup=reply_markup)
 
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # --- AQUÍ ESTABA EL ERROR ---
    if data == "MENU_PRINCIPAL":
        # En lugar de llamar a start(), regeneramos el menú y EDITAMOS el mensaje
        cargar_datos() # Recargar por si hubo cambios
        mensaje = "👋 Panel Geotab Telegram.\nSelecciona unidad:"
        reply_markup = armar_teclado_menu()
        
        await query.edit_message_text(text=mensaje, reply_markup=reply_markup)
        return
    # -----------------------------
 
    if data in UNIDADES:
        u = UNIDADES[data]
        
        # Icono de estatus para el detalle
        if u.get('en_taller'):
            status_icon = "🔧 EN TALLER"
        elif u.get('velocidad') > 0 and (u.get('chofer') == "Sin Asignar" or u.get('chofer') == ""):
            status_icon = "👻 MOVIMIENTO NO AUTORIZADO (Sin Chofer)"
        elif u.get('velocidad') > LIMITE_VELOCIDAD:
             status_icon = "🚨 EXCESO DE VELOCIDAD"
        elif u.get('velocidad') == 0:
            status_icon = f"🔴 DETENIDO (Tiempo: {u.get('tiempo_detenido')})"
        else:
            status_icon = "🟢 EN RUTA"
 
        mensaje = f"""
🚛 *{data}*
Estado: *{status_icon}*
 
📍 Ref: `{u.get('referencia', 'Sin ref')}`
📄 Placas: `{u.get('placas')}`
🚀 Velocidad: *{u.get('velocidad')} km/h*
👨‍✈️ Chofer: {u.get('chofer')}
 
📍 [Ver Mapa en Google](https://maps.google.com/?q={u['posicion']['lat']},{u['posicion']['lon']})
        """
        
        botones = []
        if u.get('telefono'):
            botones.append([InlineKeyboardButton("📞 Llamar Chofer", url=f"https://wa.me/{u.get('telefono')}")])
        botones.append([InlineKeyboardButton("🔙 Volver", callback_data="MENU_PRINCIPAL")])
        
        await query.edit_message_text(text=mensaje, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(botones))
 
async def reporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargar_datos()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Unidad', 'Ref', 'Velocidad', 'Chofer', 'Tiempo Detenido'])
    for n, u in UNIDADES.items():
        writer.writerow([n, u.get('referencia'), u.get('velocidad'), u.get('chofer'), u.get('tiempo_detenido')])
    output.seek(0)
    doc = io.BytesIO(output.getvalue().encode('utf-8'))
    doc.name = "Geotab_Report.csv"
    await update.message.reply_document(document=doc)
 
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args).lower()
    if not query: return
    cargar_datos()
    encontradas = [k for k, v in UNIDADES.items() if query in k.lower()]
    if len(encontradas) == 1:
        await update.message.reply_text(f"Unidad encontrada: {encontradas[0]}")
 
# ---------------------------------------------------------
# 5. EJECUCIÓN
# ---------------------------------------------------------
def main():
    if not TOKEN: return
    cargar_datos()
    Thread(target=run_dummy_server, daemon=True).start()
    Thread(target=ping_self, daemon=True).start()
 
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reporte", reporte))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CallbackQueryHandler(button_handler))
 
    print("--- Bot Geotab Pro Corregido Iniciado ---")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
 
if __name__ == "__main__":
    main()
