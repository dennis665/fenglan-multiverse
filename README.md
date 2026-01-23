CSI Server Portal - 專案開發說明這是一個基於 Django 6.0.1 與 MySQL 8.0.45 構建的入口網站專案，支援 Google OAuth 2.0 登入、Docker 容器化部署以及 Notice 公告系統。📑 目錄環境需求初始建立流程 (Local 模式)Docker 運作流程 (核心開發)資料庫與帳號管理管理工具與清理專案註解規範Google OAuth 設定提醒💻 環境需求項目需求版本Python3.13+DatabaseMySQL 8.0.45ContainerDocker & Docker ComposeOAuthGoogle Cloud Platform OAuth 2.0 Client ID🛠 初始建立流程 (Local 模式)如果你想在本機環境（非 Docker）進行初步測試，請依照以下步驟操作：Bash# 1. 建立專案與進入目錄
mkdir csi_server && cd csi_server

# 2. 安裝虛擬環境 (venv)
python -m venv .venv
source .venv/bin/activate  # Windows 請執行: .venv\Scripts\activate

# 3. 安裝必要套件
pip install -r requirements.txt

# 4. 初始化專案與資料庫
django-admin startproject config .
python manage.py migrate

# 5. 建立管理員與核心 App
python manage.py createsuperuser
python manage.py startapp core
[!TIP]預設啟動開發伺服器指令：python manage.py runserver🐳 Docker 運作流程 (核心開發)這是本專案推薦的開發方式，確保環境一致性。容器啟動與更新Bash#! 建立並啟動所有容器 (修改 Dockerfile 或新增套件後使用)
docker compose up --build

#! 背景啟動 (僅修改 .py 或 .html 檔案後使用)
docker compose up -d

#! 徹底關閉並移除容器 (確保環境變數重載)
docker compose down
🗄 資料庫與帳號管理透過 Docker 指令與容器內的 Django 進行互動：功能指令資料庫遷移docker compose exec web python manage.py migrate建立管理員docker compose exec web python manage.py createsuperuser資料庫模型變更docker compose exec web python manage.py makemigrations🧰 管理工具與清理開發輔助增強版 Shell: docker compose exec web python manage.py shell_plus (自動匯入所有 Model)路由清單: docker compose exec web python manage.py show_urls環境清理Bash#! 移除專案特定的網頁映像檔
docker rmi csi_server-web

#! 清除所有未使用的容器、網路與映像檔
docker system prune

#! 停止容器並一併刪除資料庫 Volume (⚠️ 資料會消失)
docker compose down -v
📝 專案註解規範 (Standard)本專案代碼開發中必須遵循以下註解標籤：#!：用於功能塊初始化、大標題或關鍵邏輯說明。#*：用於設定值解釋、開發者提示或關鍵 Note。#?：用於標記過時 (Deprecated) 或待修復的警告。🔐 Google OAuth 設定提醒[ ] Client ID: 必須於 .env 中正確設定 GOOGLE_CLIENT_ID 與 GOOGLE_CLIENT_SECRET。[ ] Redirect URI: Google Console 必須允許 http://127.0.0.1:8000/accounts/google/login/callback/。[ ] Site ID: 進入 Admin 後台將 example.com 修改為 127.0.0.1:8000 以避免跳轉錯誤。[ ] Root URL: 確保 config/urls.py 已配置空路徑 path('', ...) 導向首頁，避免 404 Page not found 錯誤。