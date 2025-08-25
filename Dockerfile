# Imagen base: Selenium + Chrome preinstalado
FROM selenium/standalone-chrome:latest

# Directorio de trabajo
WORKDIR /app

# Copiar dependencias
COPY requirements.txt .

# Instalar librerías Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el proyecto
COPY . .

# Variables de entorno útiles para Render / contenedores
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Exponer puerto FastAPI
EXPOSE 8000

# Ajustes para Selenium headless en contenedor
ENV DISPLAY=:99
ENV CHROME_DRIVER=/usr/bin/chromedriver

# Comando de arranque FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
