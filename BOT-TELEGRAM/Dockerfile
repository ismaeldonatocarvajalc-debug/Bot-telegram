# Usa Python 3.11 oficial
FROM python:3.11-slim

# Configura el directorio de la app
WORKDIR /app

# Copia archivos necesarios
COPY requirements.txt .
COPY main.py .

# Instala dependencias
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Variables de entorno
# Puedes configurar BOT_TOKEN desde Render Dashboard, no aquí
# ENV BOT_TOKEN=<tu_token_aqui>

# Expone el puerto si necesitas HTTP (no obligatorio para bots de Telegram)
# EXPOSE 8080

# Comando para correr el bot
CMD ["python", "main.py"]
