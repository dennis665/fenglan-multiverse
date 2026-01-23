# #! CSI Server Portal - 專案開發說明

![Django Version](https://img.shields.io/badge/Django-6.0.1-green) ![Python Version](https://img.shields.io/badge/Python-3.13+-blue) ![Docker](https://img.shields.io/badge/Docker-Supported-blue)

這是一個基於 **Django 6.0.1** 與 **MySQL 8.0.45** 構建的入口網站專案，支援 **Google OAuth 2.0** 登入、**Docker** 容器化部署以及 **Notice** 公告系統。

---

## 📑 目錄
- [環境需求](#環境需求)
- [初始建立流程 (Local 模式)](#初始建立流程-local-模式)
- [Docker 運作流程 (核心開發)](#docker-運作流程-核心開發)
- [資料庫與帳號管理](#資料庫與帳號管理)
- [管理工具與清理](#管理工具與清理)
- [專案註解規範](#專案註解規範)
- [Google OAuth 設定提醒](#google-oauth-設定提醒)

---

## 💻 環境需求
| 項目 | 需求版本 |
| :--- | :--- |
| **Python** | 3.13+ |
| **Database** | MySQL 8.0.45 |
| **Container** | Docker & Docker Compose |
| **OAuth** | Google Cloud Platform OAuth 2.0 Client ID |

---

## 🛠 初始建立流程 (Local 模式)
如果你想在本機環境（非 Docker）進行初步測試，請依照以下步驟操作：

```bash
# 1. 建立專案與進入目錄
mkdir csi_server && cd csi_server

# 2. 安裝虛擬環境 (venv)
python -m venv .venv
source .venv/bin/activate  # #* Windows 請執行: .venv\Scripts\activate

# 3. 安裝必要套件
pip install -r requirements.txt

# 4. 初始化專案與資料庫
django-admin startproject config .
python manage.py migrate

# 5. 建立管理員與核心 App
python manage.py createsuperuser
python manage.py startapp core

