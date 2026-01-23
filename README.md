#! CSI Server Portal - 專案開發說明
這是一個基於 Django 6.0.1 與 MySQL 8.0.45 構建的入口網站專案，支援 Google OAuth 2.0 登入與 Docker 容器化部署。

#! 環境需求
Python: 3.13+

Database: MySQL 8.0.45

Container: Docker & Docker Compose

OAuth: Google Cloud Platform OAuth 2.0 Client ID

#! 初始建立流程 (Local 模式)
如果你想在本機環境（非 Docker）進行初步測試，請依照以下步驟：

Bash
# 1. 建立專案與進入目錄
mkdir csi_server
cd csi_server

# 2. 安裝虛擬環境 (venv)
python -m venv .venv
source .venv/bin/activate  # #* Windows 使用 .venv\Scripts\activate

# 3. 安裝必要套件
pip install -r requirements.txt

# 4. 初始化專案
django-admin startproject config .

# 5. 初始化 Django 內建資料庫 (預設 SQLite)
python manage.py migrate

# 6. 建立管理員與 App
python manage.py createsuperuser
python manage.py startapp core # #* 建立核心功能 App

# 7. 啟動開發伺服器
python manage.py runserver
#! Docker 運作流程 (核心開發)
這是專案最主要的運行方式，確保所有開發者環境一致。

#* 容器啟動與更新
Bash
#! 建立並啟動所有容器 (修改 Dockerfile 或新增套件後使用)
docker compose up --build

#! 背景啟動 (僅修改 .py 或 .html 檔案後使用)
docker compose up -d

#! 徹底關閉並移除容器 (確保環境變數重載)
docker compose down
#* 資料庫與帳號管理
Bash
#! 執行資料庫遷移 (同步 Model 變更至 MySQL)
docker compose exec web python manage.py migrate

#! 建立容器內的超級使用者
docker compose exec web python manage.py createsuperuser
#* 管理工具
Bash
#! 進入增強版 Shell (自動匯入所有 Model)
docker compose exec web python manage.py shell_plus # #* 依賴 django-extensions

#! 查看目前專案所有路由清單
docker compose exec web python manage.py show_urls
#! 清除環境與快取
當環境出現衝突或磁碟空間不足時，請執行以下清理動作。

Bash
#! 移除專案特定的網頁映像檔
docker rmi csi_server-web #

#! 清除所有未使用的容器、網路與映像檔
docker system prune

#! 停止容器並一併刪除資料庫 Volume (警告：資料會消失)
docker compose down -v
#! 專案註解規範 (Standard)
本專案代碼中必須嚴格遵守以下註解標籤：

#!：用於功能塊初始化、大標題或關鍵邏輯說明。

#*：用於設定值解釋、開發者提示或關鍵 Note。

#! Google OAuth 設定提醒
Client ID: 必須於 .env 中設定 GOOGLE_CLIENT_ID。

Redirect URI: Google 控制台必須允許 http://127.0.0.1:8000/accounts/google/login/callback/。

Site ID: 確保 Admin 後台中的 Site Domain 已從 example.com 改為 127.0.0.1:8000。
