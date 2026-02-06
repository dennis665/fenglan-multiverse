import io
import warnings
import zipfile

import pandas as pd
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render

from utils.decorators import staff_required
from utils.logger_utils import jinfo_error


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
    #! 初始化資料
    file_status_map = {}  # * 格式: { 'A011': {'report': True, 'template': True, 'db': True} }
    error_files = []  # * 紀錄錯誤的檔案

    if request.method == "POST":
        action = request.POST.get("action", "check")
        #! 獲取上傳檔案
        dict_report = get_all_files(request.FILES.getlist("files_report"))
        dict_template = get_all_files(request.FILES.getlist("files_template"))
        dict_db = get_all_files(request.FILES.getlist("files_db"))
        if action == "check":
            #! 掃描並填充對應關係
            for name in dict_report.keys():
                fid = name[-11:-7]
                if len(fid) != 4 or len(name) != 25:
                    error_files.append(f"申報檔：{name}")
                    continue
                file_status_map[fid] = {"report": True, "template": False, "db": False}

            #! 交叉比對範本與資料庫檔是否存在
            for name in dict_template.keys():
                fid = name.split(".")[0]
                if len(fid) != 4 or len(name) != 9:
                    error_files.append(f"範本檔：{name}")
                    continue
                if fid in file_status_map:
                    file_status_map[fid]["template"] = True
                else:
                    file_status_map[fid] = {"report": False, "template": True, "db": False}

            for name in dict_db.keys():
                try:
                    fid = name.split("_")[2]
                    if len(fid) != 4 or "_" not in name:
                        error_files.append(f"資料庫檔：{name}")
                        continue
                    if fid in file_status_map:
                        file_status_map[fid]["db"] = True
                    else:
                        file_status_map[fid] = {"report": False, "template": False, "db": True}
                except Exception:
                    error_files.append(f"資料庫檔：{name}")

            sorted_map = dict(sorted(file_status_map.items()))

            #! 檢查是否全部滿足 (控制按鈕)
            all_matched = (
                all(v["report"] and v["template"] and v["db"] for v in sorted_map.values()) if sorted_map else False
            )

            #! 如果是 AJAX 請求，回傳 JSON
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"status_map": sorted_map, "all_matched": all_matched, "errors": error_files})
        elif action == "compare":
            #! --- 深度資料比對邏輯 ---
            diff_summary = []
            session_key = request.session.session_key or request.session.create()

            #! 檔案配對字典
            report_mapping = {n[-11:-7]: obj for n, obj in dict_report.items() if len(n[-11:-7]) == 4}
            template_mapping = {n.split(".")[0]: obj for n, obj in dict_template.items()}
            db_mapping = {n.split("_")[2]: obj for n, obj in dict_db.items() if "_" in n}

            for fid in report_mapping.keys():
                if fid in template_mapping and fid in db_mapping:
                    try:
                        ignore_rows = set()  # * 忽略的列數
                        start_row = 8  # * 開始的列數

                        #! 讀取範本 Excel 的 config
                        df_config = smart_read_excel(template_mapping[fid], sheet_name="config", header=None)
                        #! 讀取 B4: 規則套用開始列數 (索引為 3, 1)
                        val_start = df_config.iloc[3, 1]
                        if pd.notna(val_start):
                            start_row = int(val_start)
                        #! 讀取 B11: 忽略檢核列數 (索引為 10, 1)
                        val_ignore = str(df_config.iloc[10, 1])
                        if val_ignore and val_ignore.lower() != "nan":
                            #! 解析如 "8,31,32" 的字串轉為整數集合
                            ignore_rows = {int(x.strip()) for x in val_ignore.split(",") if x.strip().isdigit()}

                        #! 讀取範本 Excel 的 schema 頁籤建立對照表
                        df_schema = smart_read_excel(template_mapping[fid], sheet_name="schema", skiprows=7)
                        mapping = dict(zip(df_schema["中文欄位名稱"], df_schema["COLUMN_NAME"]))

                        #! 讀取申報檔 Excel 資料
                        df_r = smart_read_excel(report_mapping[fid], header=None)
                        #! 取 start_row - 2 那一列作為 Columns (Excel row 8 -> row 6, index 是 5)
                        header_idx = start_row - 3
                        df_r.columns = df_r.iloc[header_idx]

                        #! 讀取 DB CSV
                        df_db = smart_read_csv(db_mapping[fid])

                        #! 執行比對
                        diff_list = []
                        target_cols = [c for c in df_r.columns if c in mapping]
                        db_i = -1

                        for i in range(len(df_r)):
                            #! 跳過非資料 row 或忽略 row
                            if (i + 1) < start_row or (i + 1) in ignore_rows:
                                continue
                            db_i += 1
                            for ch_col in target_cols:
                                en_col = mapping[ch_col]
                                if en_col not in df_db.columns:
                                    continue

                                val_r = normalize_val(df_r.iloc[i][ch_col])
                                val_db = normalize_val(df_db.iloc[db_i][en_col])

                                if val_r != val_db:
                                    #! 數值容錯（如 10.0 == 10）
                                    try:
                                        if float(val_r) == float(val_db):
                                            continue
                                    except Exception:
                                        pass

                                    diff_list.append(
                                        {
                                            "行號": i + 1,
                                            "中文欄位": ch_col,
                                            "英文欄位": en_col,
                                            "申報值": val_r,
                                            "DB值": val_db,
                                        }
                                    )

                        #! 存入差異並暫存
                        diff_count = len(diff_list)
                        if diff_count > 0:
                            df_diff = pd.DataFrame(diff_list)
                            csv_buf = io.StringIO()
                            df_diff.to_csv(csv_buf, index=False, encoding="utf-8-sig")
                            cache.set(f"diff_{session_key}_{fid}", csv_buf.getvalue(), 3600)

                        diff_summary.append({"fid": fid, "diff_count": diff_count})
                    except Exception as e:
                        jinfo_error(e)

            return JsonResponse({"action": "compare_results", "diff_results": diff_summary})
    return render(request, "core/tigf_dashboard.html", {"status_map": file_status_map, "all_matched": False})


@staff_required
def download_diff_csv(request, fid):
    """
    從快取讀取比對差異 CSV 並提供下載
    """
    #! 取得 Session Key (必須與 compare 寫入時的一致)
    session_key = request.session.session_key
    if not session_key:
        return HttpResponse("連線已逾期，請重新整理頁面並重新比對。", status=400)

    #! 組合快取 Key
    cache_key = f"diff_{session_key}_{fid}"
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
    filename = f"TIGF_Diff_{fid}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response