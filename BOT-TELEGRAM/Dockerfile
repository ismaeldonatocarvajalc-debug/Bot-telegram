# --- Usar Python 3.11 slim ---
FROM python:3.11-slim

# --- Establece carpeta de trabajo ---
WORKDIR /app

# --- Copiar archivo de dependencias primero ---
COPY requirements.txt .

# --- Actualiza pip e instala dependencias ---
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# --- Copiar todo el proyecto ---
COPY . .

# --- Configurar variable de entorno para el token ---
ENV BOT_TOKEN=${BOT_TOKEN}

# --- Evitar buffering en logs ---
ENV PYTHONUNBUFFERED=1

# --- Ejecutar bot ---
CMD ["python", "main.py"]
