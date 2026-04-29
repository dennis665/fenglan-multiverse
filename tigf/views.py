from utils.logger_utils import time_tracker

#! 包裝整個 import 區塊或初始化邏輯
with time_tracker("tigf"):
    import io
    import re
    import warnings
    import zipfile
    from datetime import datetime
    from decimal import Decimal, InvalidOperation
    from urllib.parse import quote

    import pandas as pd
    from django.core.cache import cache
    from django.http import HttpResponse, JsonResponse
    from django.shortcuts import render

    from utils.decorators import staff_required


def get_all_files(uploaded_files):
    """
    輔助函式：將上傳的檔案清單（包含 ZIP）轉換為字典 {檔名: 檔案內容或對象}
    """
    files_data = {}
    for f in uploaded_files:
        if f.name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(f) as z:
                    for name in z.namelist():
                        #! 排除資料夾與系統暫存檔
                        if name.endswith("/") or "__MACOSX" in name:
                            continue
                        #! 讀取 ZIP 內的檔案內容
                        files_data[name] = io.BytesIO(z.read(name))
            except zipfile.BadZipFile:
                #! 若 ZIP 損毀則跳過或記錄
                pass
        else:
            files_data[f.name] = f
    return files_data


def normalize_val(val):
    """資料正規化：處理日期格式 (2024-05-14 -> 20240514) 與數值字串"""
    if pd.isna(val):
        return ""
    s = str(val).strip()
    if "-" in s and len(s) == 10:
        s = s.replace("-", "")
    return s


def smart_read_csv(file_obj, **kwargs):
    """
    自動嘗試不同編碼讀取 CSV，解決 utf-8 編碼報錯問題
    """
    encodings = ["utf-8-sig", "cp950", "utf-8", "big5"]
    content = file_obj.read()
    if "dtype" not in kwargs:
        kwargs["dtype"] = str
    for enc in encodings:
        try:
            #! 每次嘗試需將指標重置或使用 io.BytesIO
            df = pd.read_csv(io.BytesIO(content), encoding=enc, **kwargs)
            return df
        except (UnicodeDecodeError, Exception):
            continue
    #! 若全部失敗，拋出原始錯誤
    file_obj.seek(0)
    return pd.read_csv(file_obj, **kwargs)


def smart_read_excel(file_obj, **kwargs):
    """讀取 Excel 並過濾掉煩人的 Header/Footer 警告"""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
        #! 確保指標在開頭
        file_obj.seek(0)
        return pd.read_excel(file_obj, **kwargs)


#! 獨立的數值與日期比對函式：處理日期正規化、0.0 == "" 以及浮點數誤差
def is_value_matched(
    val_r,
    val_db,
    rule_str_match=True,
    rule_date_check=True,
    rule_empty_zero=True,
    rule_tolerance=True,
):
    #! 基礎清理與正規化
    str_r = str(val_r).strip().replace("nan", "").replace("None", "")
    str_db = str(val_db).strip().replace("nan", "").replace("None", "")

    #! 字串完全相同 (包含兩者皆為空字串)
    if rule_str_match and str_r == str_db:
        return True

    if rule_date_check:
        #! 日期格式正規化比對 (處理如 20250130 = 2025-01-30)
        #! 移除所有非數字字元後嘗試進行日期長度檢查
        date_r = re.sub(r"[^0-9]", "", str_r)
        date_db = re.sub(r"[^0-9]", "", str_db)

        #! 若兩者清理後皆為 8 位數字且內容相同，視為日期匹配
        if len(date_r) == 8 and len(date_db) == 8 and date_r == date_db:
            try:
                #! 確保字串符合基本日期邏輯 (例如不會出現 20251340)
                datetime.strptime(date_r, "%Y%m%d")
                return True
            except ValueError:
                #! 若非有效日期則跳過，進入後續數值比對
                pass

    #! 數值比對：將空字串視為 0 進行 Decimal 轉換
    try:
        if rule_empty_zero:
            dec_r = Decimal(str_r) if str_r else Decimal("0")
            dec_db = Decimal(str_db) if str_db else Decimal("0")
        else:
            #! 若未啟用空值視為 0，遇空字串轉 Decimal 會拋出 InvalidOperation 並略過比對
            dec_r = Decimal(str_r)
            dec_db = Decimal(str_db)

        if rule_tolerance:
            #! 誤差小於 1e-5 視為相同
            if abs(dec_r - dec_db) < Decimal("1e-5"):
                return True
        else:
            #! 關閉容差：必須絕對相等
            if dec_r == dec_db:
                return True
    except InvalidOperation:
        #! 若無法轉為數值 (例如純文字與空字串比對)，則回傳不匹配
        pass

    return False


#! 欄位轉換函式：將 Excel 英文欄位名稱轉換為從 1 開始的整數索引
def excel_column_to_number(column_str):
    #! 基礎清理：轉為大寫並去除空格
    column_str = str(column_str).upper().strip()

    number = 0
    #! 遍歷字串中的每個字母，並依照 26 進制原理進行加權計算
    for char in column_str:
        #! ord(char) 取得字元編碼，'A' 的編碼為 65，減去 64 得到 A=1
        if "A" <= char <= "Z":
            number = number * 26 + (ord(char) - ord("A") + 1)
        else:
            #! 若字串包含非英文字母則回傳 0 或拋出錯誤
            return 0

    return number


@staff_required
def tigf_dashboard(request):
    #! 雙層結構: { '1234567': { 'A011': {'report': True, 'template': True, 'db': True} } }
    file_status_map = {}
    error_files = []

    if request.method == "POST":
        action = request.POST.get("action", "check")
        dict_report = get_all_files(request.FILES.getlist("files_report"))
        dict_template = get_all_files(request.FILES.getlist("files_template"))
        dict_db = get_all_files(request.FILES.getlist("files_db"))

        #! 預處理共用的範本檔與資料庫檔
        global_templates = {n.split(".")[0]: obj for n, obj in dict_template.items()}
        global_dbs = {n.split("_")[2]: obj for n, obj in dict_db.items() if "_" in n}

        if action == "check":
            #! 掃描申報檔並建立 公司編號 -> 報表編號 結構
            for name, obj in dict_report.items():
                #! 檔名解析：M202506 1234567 A011 00 (長度20)
                #! M202506 (0~7) | 1234567 (7~14) | A011 (14~18)
                if len(name) < 18:
                    error_files.append(f"申報檔格式異常：{name}")
                    continue

                cno = name[7:14]  # * 公司編號
                fid = name[14:18]  # * 報表編號

                if cno not in file_status_map:
                    file_status_map[cno] = {}

                #! 檢查這張報表是否具備共用的 template 與 db
                file_status_map[cno][fid] = {
                    "report": True,
                    "template": fid in global_templates,
                    "db": fid in global_dbs,
                }

            #! 排序與驗證是否全部齊全
            sorted_map = {k: dict(sorted(v.items())) for k, v in sorted(file_status_map.items())}
            all_matched = True
            has_files = False

            for cno, fids in sorted_map.items():
                for fid, status in fids.items():
                    has_files = True
                    if not (status["report"] and status["template"] and status["db"]):
                        all_matched = False

            if not has_files:
                all_matched = False

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"status_map": sorted_map, "all_matched": all_matched, "errors": error_files})

        elif action == "compare":
            diff_summary = []
            session_key = request.session.session_key or request.session.create()

            #! 從 request 中取得前端設定的 4 項規則開關，若為字串 "true" 則轉為布林值 True
            rule_str_match = request.POST.get("rule_str_match") == "true"
            rule_date_check = request.POST.get("rule_date_check") == "true"
            rule_empty_zero = request.POST.get("rule_empty_zero") == "true"
            rule_tolerance = request.POST.get("rule_tolerance") == "true"

            #! 解析申報檔
            for name, report_obj in dict_report.items():
                if len(name) < 18:
                    continue
                cno = name[7:14]
                fid = name[14:18]

                if fid in global_templates and fid in global_dbs:
                    try:
                        ignore_rows = set()
                        ignore_data = ""
                        ignore_column_num = 0
                        ignore_column_name = ""
                        start_row = 8

                        #! 讀取範本 Config
                        df_config = smart_read_excel(global_templates[fid], sheet_name="config", header=None)
                        if pd.notna(df_config.iloc[3, 1]):
                            start_row = int(df_config.iloc[3, 1])

                        #! 抓取忽略檢查值的行 (通常是A-合計)
                        if pd.notna(df_config.iloc[18, 1]):
                            ignore_column, *_, ignore_data = str(df_config.iloc[18, 1]).split("-")
                            ignore_column_num = excel_column_to_number(ignore_column)

                        val_ignore = str(df_config.iloc[10, 1])
                        if val_ignore and val_ignore.lower() != "nan":
                            ignore_rows = {int(x.strip()) for x in val_ignore.split(",") if x.strip().isdigit()}

                        #! 讀取 Schema
                        df_schema = smart_read_excel(global_templates[fid], sheet_name="schema", skiprows=7)
                        mapping = dict(zip(df_schema["中文欄位名稱"], df_schema["COLUMN_NAME"]))

                        #! 讀取申報檔並處理雙層標題
                        df_r = smart_read_excel(report_obj, header=None)
                        row_upper = df_r.iloc[start_row - 4]
                        row_lower = df_r.iloc[start_row - 3]

                        if row_upper.astype(str).str.strip().replace(["nan", "None"], "").eq("").all():
                            df_r.columns = row_lower
                        else:
                            new_columns = []
                            top_l = ""
                            for upper, lower in zip(row_upper, row_lower):
                                top = str(upper).strip() if pd.notna(upper) else ""
                                bottom = str(lower).strip() if pd.notna(lower) else ""
                                if top and bottom:
                                    new_columns.append(f"{top}_{bottom}")
                                    top_l = top
                                elif top:
                                    new_columns.append(top)
                                elif not top_l:
                                    new_columns.append(bottom)
                                else:
                                    new_columns.append(f"{top_l}_{bottom}")
                            df_r.columns = new_columns

                        #! 讀取共用 DB 檔，並進行過濾
                        df_db_full = smart_read_csv(global_dbs[fid])
                        df_db_full["Cno"] = df_db_full["Cno"].astype(str).str.strip()
                        df_db = df_db_full[df_db_full["Cno"] == str(cno)]

                        if "isdel" in df_db.columns:
                            df_db = df_db[df_db["isdel"].isna() | (df_db["isdel"].astype(str).str.strip() == "")]

                        #! 取得目標比對欄位
                        target_cols = [c for c in df_r.columns if c in mapping]
                        if not target_cols:
                            diff_summary.append(
                                {"cno": cno, "fid": fid, "diff_count": 0, "schema_error": True}
                            )
                            continue

                        #! === 核心優化：建立 DB 字典 (支援重複主鍵) ===
                        pk_ch = target_cols[0]
                        pk_en = mapping[pk_ch]

                        #! 忽略欄位名
                        if ignore_column_num:
                            ignore_column_name = target_cols[ignore_column_num - 1]

                        #! 將字典的值改為 List，用來存放相同 Key 的多筆資料，並加入 used 標記
                        db_lookup = {}
                        for _, row in df_db.iterrows():
                            k = str(row[pk_en]).strip().replace("nan", "").replace("None", "")
                            if k:
                                if k not in db_lookup:
                                    db_lookup[k] = []
                                #! 將資料與使用狀態打包存入
                                db_lookup[k].append({"data": row, "used": False})

                        #! 開始比對
                        diff_list = []

                        for i in range(len(df_r)):
                            if (i + 1) < start_row or (i + 1) in ignore_rows:
                                continue

                            row_r = df_r.iloc[i]
                            r_key_val = (
                                str(row_r[pk_ch]).strip().replace("nan", "").replace("None", "")
                            )

                            if not r_key_val:
                                continue

                            #! 判斷是否忽略行
                            if (
                                ignore_column_name
                                and ignore_column_name == pk_ch
                                and r_key_val == ignore_data
                            ):
                                continue

                            #! 檢查主鍵是否存在於 DB
                            if r_key_val not in db_lookup:
                                diff_list.append(
                                    {
                                        "行號": i + 1,
                                        "中文欄位": pk_ch,
                                        "英文欄位": pk_en,
                                        "申報值": r_key_val,
                                        "DB值": "DB 此行無對應資料",
                                    }
                                )
                                continue

                            #! 找出 DB 中該主鍵「尚未被比對過」的資料
                            available_db_items = [
                                item for item in db_lookup[r_key_val] if not item["used"]
                            ]

                            if not available_db_items:
                                #! 代表申報檔裡該主鍵的數量，比 DB 裡的還要多
                                diff_list.append(
                                    {
                                        "行號": i + 1,
                                        "中文欄位": pk_ch,
                                        "英文欄位": pk_en,
                                        "申報值": r_key_val,
                                        "DB值": "DB 缺漏此行資料",
                                    }
                                )
                                continue

                            #! 取出第一筆可用的 DB 資料，並標記為已使用
                            db_item = available_db_items[0]
                            row_db = db_item["data"]
                            db_item["used"] = True  # * 關鍵：上鎖，下一行申報檔就不會再比對到同一筆

                            #! 逐欄比對 (保持原本的邏輯)
                            for ch_col in target_cols:
                                en_col = mapping[ch_col]
                                if en_col not in row_db:
                                    continue

                                val_r = row_r[ch_col]
                                val_db = row_db[en_col]

                                if not is_value_matched(
                                    val_r,
                                    val_db,
                                    rule_str_match,
                                    rule_date_check,
                                    rule_empty_zero,
                                    rule_tolerance,
                                ):
                                    diff_list.append(
                                        {
                                            "行號": i + 1,
                                            "中文欄位": ch_col,
                                            "英文欄位": en_col,
                                            "申報值": val_r,
                                            "DB值": val_db,
                                        }
                                    )

                        diff_count = len(diff_list)
                        if diff_count > 0:
                            df_diff = pd.DataFrame(diff_list)
                            excel_buf = io.BytesIO()
                            df_diff.to_excel(excel_buf, index=False, engine="openpyxl")
                            cache.set(f"diff_{session_key}_{cno}_{fid}", excel_buf.getvalue(), 3600)

                        diff_summary.append(
                            {
                                "cno": cno,
                                "fid": fid,
                                "diff_count": diff_count,
                                "schema_error": False,
                            }
                        )

                    except Exception as e:
                        print(f"處理 {cno}-{fid} 時發生錯誤: {e}")

            return JsonResponse({"action": "compare_results", "diff_results": diff_summary})

    return render(request, "core/tigf_dashboard.html", {"status_map": file_status_map, "all_matched": False})


@staff_required
def download_diff_csv(request, cno, fid):
    """
    從快取讀取比對差異 CSV 並提供下載
    """
    #! 取得 Session Key (必須與 compare 寫入時的一致)
    session_key = request.session.session_key
    if not session_key:
        return HttpResponse("連線已逾期，請重新整理頁面並重新比對。", status=400)

    #! 組合快取 Key
    cache_key = f"diff_{session_key}_{cno}_{fid}"
    excel_data = cache.get(cache_key)

    #! 檢查資料是否存在
    if not excel_data:
        #! 如果快取過期（1小時）或找不到資料
        return HttpResponse("找不到比對資料或檔案已過期，請重新執行比對。", status=404)

    #! 建立 HttpResponse
    #! 指定內容類型為 CSV
    response = HttpResponse(
        excel_data, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    #! 設定下載檔名 (Content-Disposition)
    #! 建議檔名加上 fid，方便使用者辨識
    filename = f"安定比對差異檔_{cno}_{fid}.xlsx"
    response["Content-Disposition"] = f"attachment; filename*=utf-8''{quote(filename)}"

    return response