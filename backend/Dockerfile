# Dockerfile para Backend con Selenium + Chrome
FROM python:3.11-slim

# Instalar Chrome y dependencias
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Instalar ChromeDriver
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1) \
    && wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$CHROME_VERSION.0.6778.87/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    || wget -q "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION" -O /tmp/version \
    && wget -q "https://chromedriver.storage.googleapis.com/$(cat /tmp/version)/chromedriver_linux64.zip" -O /tmp/chromedriver.zip \
    ; unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver*/chromedriver /usr/local/bin/ 2>/dev/null || mv /tmp/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/*

# Directorio de trabajo
WORKDIR /app

# Copiar requirements e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Crear directorio de descargas
RUN mkdir -p /app/downloads

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV DOWNLOAD_DIR=/app/downloads
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

# Puerto
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
