import io
import warnings
import zipfile
from decimal import Decimal

import pandas as pd
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render

from utils.decorators import staff_required
from utils.logger_utils import jinfo


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

            #! 解析申報檔
            for name, report_obj in dict_report.items():
                if len(name) < 18:
                    continue
                cno = name[7:14]
                fid = name[14:18]

                if fid in global_templates and fid in global_dbs:
                    try:
                        ignore_rows = set()
                        start_row = 8

                        #! 讀取範本 Config
                        df_config = smart_read_excel(global_templates[fid], sheet_name="config", header=None)
                        if pd.notna(df_config.iloc[3, 1]):
                            start_row = int(df_config.iloc[3, 1])

                        val_ignore = str(df_config.iloc[10, 1])
                        if val_ignore and val_ignore.lower() != "nan":
                            ignore_rows = {int(x.strip()) for x in val_ignore.split(",") if x.strip().isdigit()}

                        #! 讀取 Schema
                        df_schema = smart_read_excel(global_templates[fid], sheet_name="schema", skiprows=7)
                        mapping = dict(zip(df_schema["中文欄位名稱"], df_schema["COLUMN_NAME"]))

                        #! 讀取申報檔
                        df_r = smart_read_excel(report_obj, header=None)
                        #! 提取兩列標題列
                        row_upper = df_r.iloc[start_row - 4]  # * 上層標題 (例如：大分類)
                        row_lower = df_r.iloc[start_row - 3]  # * 下層標題 (例如：細目)
                        #! 判斷是不是有雙層標題
                        if row_upper.astype(str).str.strip().replace(["nan", "None"], "").eq("").all():
                            df_r.columns = row_lower
                        else:
                            #! 定義合併邏輯：處理 NaN 並組合名稱
                            new_columns = []
                            top_l = ""
                            for upper, lower in zip(row_upper, row_lower):
                                #! 轉為字串並去除前後空白，如果是 NaN 則變成空字串
                                top = str(upper).strip() if pd.notna(upper) else ""
                                bottom = str(lower).strip() if pd.notna(lower) else ""

                                if top and bottom:
                                    #! 兩行都有值：組合在一起
                                    new_columns.append(f"{top}_{bottom}")
                                    top_l = top
                                elif top:
                                    #! 只有上層有值 (下層空)
                                    new_columns.append(top)
                                else:
                                    #! 只有下層有值，或兩者皆無 (取下層，若下層也空則會是空字串)
                                    new_columns.append(f"{top_l}_{bottom}")

                            #! 正式設定回 DataFrame
                            df_r.columns = new_columns

                        #! 讀取共用 DB 檔，並進行過濾
                        df_db_full = smart_read_csv(global_dbs[fid])
                        df_db_full["Cno"] = df_db_full["Cno"].astype(str).str.strip()

                        #! 公司編號相符
                        df_db = df_db_full[df_db_full["Cno"] == str(cno)]

                        #! isdel 是空的 (處理 NaN, None 或空字串)
                        if "isdel" in df_db.columns:
                            df_db = df_db[df_db["isdel"].isna() | (df_db["isdel"].astype(str).str.strip() == "")]

                        #! 重新重置 index，否則跑迴圈時 index 會對不上
                        df_db = df_db.reset_index(drop=True)

                        #! 開始比對
                        diff_list = []
                        target_cols = [c for c in df_r.columns if c in mapping]
                        db_i = -1

                        for i in range(len(df_r)):
                            if (i + 1) < start_row or (i + 1) in ignore_rows:
                                continue
                            db_i += 1

                            #! 防護：如果申報檔資料列數 > 資料庫篩出的列數
                            if db_i >= len(df_db):
                                diff_list.append(
                                    {
                                        "行號": i + 1,
                                        "中文欄位": "系統提示",
                                        "英文欄位": "N/A",
                                        "申報值": "有資料",
                                        "DB值": "無此筆資料 (DB列數不足)",
                                    }
                                )
                                continue

                            for ch_col in target_cols:
                                en_col = mapping[ch_col]
                                if en_col not in df_db.columns:
                                    continue

                                val_r = normalize_val(df_r.iloc[i][ch_col])
                                val_db = normalize_val(df_db.iloc[db_i][en_col])

                                if val_r != val_db:
                                    try:
                                        #! 嘗試將兩者都轉為 Decimal 進行數值比對
                                        dec_r = Decimal(val_r)
                                        dec_db = Decimal(val_db)
                                        if dec_r == dec_db:
                                            continue
                                        else:
                                            #! 💡 核心邏輯：計算相對誤差
                                            #! 如果誤差小於 0.00001 (1e-5)，視為相同 (因為科學符號四捨五入產生的誤差)
                                            relative_error = abs(dec_r - dec_db)
                                            if relative_error < 1e-5:
                                                continue
                                    except Exception:
                                        jinfo(f"處理 {val_r}-{val_db} 數值錯誤略過")

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
                            csv_buf = io.StringIO()
                            df_diff.to_csv(csv_buf, index=False, encoding="utf-8-sig")
                            #! 加上 cno 作為 cache key 的一部分，避免不同公司同報表互相覆蓋
                            cache.set(f"diff_{session_key}_{cno}_{fid}", csv_buf.getvalue(), 3600)

                        diff_summary.append({"cno": cno, "fid": fid, "diff_count": diff_count})

                    except Exception as e:
                        # jinfo_error(e) # 原本你的錯誤紀錄
                        jinfo(f"處理 {cno}-{fid} 時發生錯誤: {e}")

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
    csv_data = cache.get(cache_key)

    #! 檢查資料是否存在
    if not csv_data:
        #! 如果快取過期（1小時）或找不到資料
        return HttpResponse("找不到比對資料或檔案已過期，請重新執行比對。", status=404)

    #! 建立 HttpResponse
    #! 指定內容類型為 CSV
    response = HttpResponse(csv_data, content_type="text/csv")

    #! 設定下載檔名 (Content-Disposition)
    #! 建議檔名加上 fid，方便使用者辨識
    filename = f"TIGF_Diff_{cno}_{fid}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response