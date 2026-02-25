FROM python:3.11-slim

WORKDIR /app

# 安裝所需套件
RUN pip install --no-cache-dir flask pymysql pandas tenacity requests

# 複製應用程式程式碼
COPY . .

# 設定環境變數
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py

EXPOSE 5001

CMD ["python", "app.py"]
