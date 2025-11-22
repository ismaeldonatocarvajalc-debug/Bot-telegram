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
# 3. MONITOR AUTOMÁTICO
# ---------------------------------------------------------
async def monitor_automatico(context: ContextTypes.DEFAULT_TYPE):
    cargar_datos() 
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if not UNIDADES: return

    for nombre, u in UNIDADES.items():
        velocidad = u.get('velocidad', 0)
        en_taller = u.get('en_taller', False)
        chofer = u.get('chofer', 'Sin Asignar')
        tiempo_str = u.get('tiempo_detenido', '0m')
        minutos_detenido = parse_tiempo_a_minutos(tiempo_str)
        limite = u.get('limite_estadia', DEFAULT_LIMIT)

        estatus_historial = "EN RUTA"
        if en_taller: estatus_historial = "TALLER"
        elif velocidad > LIMITE_VELOCIDAD: estatus_historial = f"EXCESO {velocidad}"
        elif velocidad > 0 and (chofer == "Sin Asignar" or chofer == ""): estatus_historial = "SIN CHOFER"
        elif velocidad == 0:
            if minutos_detenido > limite: estatus_historial = f"⚠️ EXCEDIDO"
            else: estatus_historial = "DETENIDO"

        registro = {
            "t": timestamp, "u": nombre, "p": u.get('placas'),
            "v": velocidad, "e": estatus_historial,
            "ref": u.get('referencia')[:30] 
        }
        HISTORIAL_RAM.append(registro)

        # Alertas Push
        if velocidad == 0 and not en_taller and minutos_detenido > limite:
            ultima_alerta = ALERTAS_ENVIADAS.get(nombre, 0)
            ahora = time.time()
            if (ahora - ultima_alerta) > 14400:
                # Aquí también agregué el link al mapa en la alerta 🚨🗺️
                mensaje = f"🚨 *ESTADÍA EXCEDIDA* 🚨\n🚛 {nombre}\n⏱ {tiempo_str} (Max {limite}m)\n📍 {u.get('referencia')}\n[Ver Mapa](https://maps.google.com/?q={u['posicion']['lat']},{u['posicion']['lon']})"
                for chat_id in CHATS_SUSCRITOS:
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=mensaje, parse_mode="Markdown")
                    except: pass
                ALERTAS_ENVIADAS[nombre] = ahora
        else:
            if nombre in ALERTAS_ENVIADAS: del ALERTAS_ENVIADAS[nombre]
                
    if len(HISTORIAL_RAM) > 1500: 
        del HISTORIAL_RAM[:200]

# ---------------------------------------------------------
# 4. VISUALIZACIÓN
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
    
    mensaje = f"""
👋 **¡Hola {user.first_name}! Bienvenido al Bot Rastreador** 🚛

Aquí puedes monitorear la operación de las unidades en tiempo real.
Selecciona una unidad del menú o utiliza los siguientes comandos:

🔔 **Alertas y Configuración**
/activar - Recibir notificaciones automáticas de excesos

📊 **Monitoreo en Vivo**
/estadias - Ver unidades con mayor tiempo detenidas (Top)
/resumen - Vistazo rápido de la unidad (En Ruta vs Stop)
/buscar [placa] - Encontrar una unidad específica

📂 **Reportes y Auditoría**
/reporte - Descargar reporte general (Excel)
/reporte estadias - Reporte detallado de tiempos excedidos
/reporte taller - Lista de unidades en mantenimiento
/historial - Bitácora de actividad reciente (Caja Negra)

👇 **Selecciona una unidad para ver su ubicación y estatus:**
    """
    await update.message.reply_text(mensaje, reply_markup=armar_teclado_menu(), parse_mode="Markdown")

async def activar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    CHATS_SUSCRITOS.add(update.effective_chat.id)
    await update.message.reply_text("🔔 **Alertas Activadas**\nTe avisaré si una unidad excede su tiempo.", parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "MENU_PRINCIPAL":
        cargar_datos()
        await query.edit_message_text("👋 Panel Geotab Telegram.", reply_markup=armar_teclado_menu())
        return

    if data in UNIDADES:
        u = UNIDADES[data]
        limite = u.get('limite_estadia', DEFAULT_LIMIT)
        
        if u.get('en_taller'): status = "🔧 EN TALLER"
        elif u.get('velocidad') == 0: status = f"🔴 DETENIDO ({u.get('tiempo_detenido')})"
        else: status = "🟢 EN RUTA"
        
        # --- AQUI AGREGUÉ EL MAPA ---
        msg = f"""
🚛 *{data}*
Estado: *{status}*
⏳ Tol: *{limite} min*
📍 Ref: `{u.get('referencia')}`
📄 Placas: `{u.get('placas')}`
🚀 Velocidad: *{u.get('velocidad')} km/h*
👨‍✈️ Chofer: {u.get('chofer')}

📍 [Ver Mapa en Google](https://maps.google.com/?q={u['posicion']['lat']},{u['posicion']['lon']})
        """
        
        botones = []
        if u.get('telefono'):
             botones.append([InlineKeyboardButton("📞 Llamar Chofer", url=f"https://wa.me/{u.get('telefono')}")])
        botones.append([InlineKeyboardButton("🔙 Volver", callback_data="MENU_PRINCIPAL")])
        
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(botones))

async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargar_datos()
    total = len(UNIDADES)
    mov = sum(1 for u in UNIDADES.values() if u.get('velocidad', 0) > 0)
    stop = total - mov
    await update.message.reply_text(f"📊 *Resumen*\nTotal: {total}\n🟢 Ruta: {mov}\n🔴 Stop: {stop}", parse_mode="Markdown")

async def estadias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargar_datos()
    detenidas = []
    for n, u in UNIDADES.items():
        if u.get('velocidad') == 0 and not u.get('en_taller'):
            mins = parse_tiempo_a_minutos(u.get('tiempo_detenido', '0m'))
            limite = u.get('limite_estadia', DEFAULT_LIMIT)
            detenidas.append({'n': n, 'm': mins, 't': u.get('tiempo_detenido'), 'l': limite})
    
    detenidas.sort(key=lambda x: x['m'], reverse=True)
    if not detenidas: return await update.message.reply_text("✅ Cero estadías.")
    
    msg = "⏳ **Control Estadías**\n\n"
    for d in detenidas[:10]:
        alerta = "⚠️ EXCEDIDO" if d['m'] > d['l'] else "✅ OK"
        msg += f"{alerta} **{d['n']}**\n   ⏱ {d['t']} (Max {d['l']}m)\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def reporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cargar_datos()
    tipo = context.args[0].lower() if context.args else "general"
    output = io.StringIO()
    writer = csv.writer(output)
    
    if tipo == "estadias":
        writer.writerow(['Unidad', 'Tiempo', 'Limite', 'Minutos', 'Norma', 'Ref'])
        for n, u in UNIDADES.items():
            if u.get('velocidad') == 0 and not u.get('en_taller'):
                mins = parse_tiempo_a_minutos(u.get('tiempo_detenido', '0m'))
                norma = "EXCEDIDO" if mins > u.get('limite_estadia', DEFAULT_LIMIT) else "OK"
                writer.writerow([n, u.get('tiempo_detenido'), u.get('limite_estadia'), mins, norma, u.get('referencia')])
        filename = "Reporte_Estadias.csv"
    elif tipo == "taller":
        writer.writerow(['Unidad', 'Ubicación', 'Tiempo', 'Responsable'])
        for n, u in UNIDADES.items():
            if u.get('en_taller'): writer.writerow([n, u.get('referencia'), u.get('tiempo_detenido'), u.get('chofer')])
        filename = "Reporte_Taller.csv"
    else:
        writer.writerow(['Unidad', 'Vel', 'Chofer', 'Ref'])
        for n, u in UNIDADES.items():
            writer.writerow([n, u.get('velocidad'), u.get('chofer'), u.get('referencia')])
        filename = "Reporte_General.csv"
            
    output.seek(0)
    doc = io.BytesIO(output.getvalue().encode('utf-8'))
    doc.name = filename
    await update.message.reply_document(document=doc, caption=f"📊 Reporte: {tipo.upper()}")

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args).lower()
    if not query: 
        await update.message.reply_text("🔍 Uso: `/buscar [placa]`", parse_mode="Markdown")
        return
    cargar_datos()
    encontradas = [k for k, v in UNIDADES.items() if query in k.lower()]
    if len(encontradas) == 1: await update.message.reply_text(f"✅ Encontrada: {encontradas[0]}")
    else: await update.message.reply_text(f"🔍 {len(encontradas)} coincidencias.")

async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HISTORIAL_RAM: 
        await update.message.reply_text("⏳ Sin datos aún... espera 1 minuto.")
        return
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Fecha', 'Unidad', 'Vel', 'Estatus', 'Ref'])
    for r in HISTORIAL_RAM:
        writer.writerow([r['t'], r['u'], r['v'], r['e'], r['ref']])
    output.seek(0)
    doc = io.BytesIO(output.getvalue().encode('utf-8'))
    doc.name = f"Historial.csv"
    await update.message.reply_document(document=doc, caption="🕒 Bitácora Reciente")

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
    app.add_handler(CommandHandler("reporte", reporte))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("estadias", estadias))
    app.add_handler(CommandHandler("historial", historial))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("--- Bot Definitivo con Mapa ---")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
