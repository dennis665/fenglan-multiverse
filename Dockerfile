#! 使用 Python 3.13 輕量版作為基底
FROM python:3.13-slim

#! 設定環境變數：防止 Python 產生 pyc 檔案，並讓輸出直接顯示在終端機
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

#! 設定工作目錄
WORKDIR /app

#! 安裝系統依賴 (MySQL 客戶端編譯時需要)
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

#! 安裝 Python 套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

#! 複製專案程式碼
COPY . .

#! 暴露 8000 連接埠
EXPOSE 8000

#! 啟動指令
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]