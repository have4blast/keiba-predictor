FROM python:3.11-slim

WORKDIR /app

# システム依存（lxml ビルドに必要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ディレクトリを確保（ボリュームマウント前に存在させる）
RUN mkdir -p data/raw data/features models logs

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
