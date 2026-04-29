from utils.logger_utils import time_tracker

#! 包裝整個 import 區塊或初始化邏輯
with time_tracker("invest"):
    import json
    from decimal import Decimal, InvalidOperation

    from django.conf import settings
    from django.contrib import messages
    from django.contrib.auth.decorators import login_required
    from django.db.models import Sum
    from django.http import JsonResponse
    from django.shortcuts import redirect, render

    from .forms import AIRoboAdvisorForm, TransactionForm
    from .models import Holding, Portfolio, Stock, StockPrice, Transaction

    FALLBACK_MODELS = [
        "gemini-flash-latest",  # * 首選：最新主力 (每天 20 次)
        "gemini-2.5-flash",  # * 備援 1：前代主力 (每天額外 20 次)
        "gemini-3.1-flash-lite-preview",  # * 備援 2：超級救星！(每天 500 次，不再 404)
        "gemini-flash-lite-latest",  # * 備援 3：官方動態 Lite 捷徑
        "gemini-2.0-flash",  # * 備援 4：老將壓陣
    ]

@login_required
def portfolio_dashboard(request):
    #! 取得或建立使用者的預設投資組合
    portfolio, created = Portfolio.objects.get_or_create(user=request.user, defaults={"name": "我的核心理財計畫"})

    #! 處理表單送出 (新增交易)
    if request.method == "POST":
        #! 判斷是「更新目標金額」還是「新增交易」
        if "update_target" in request.POST:
            new_target = request.POST.get("target_monthly_income")
            new_yield = request.POST.get("expected_dividend_yield")
            try:
                if new_target:
                    portfolio.target_monthly_income = Decimal(new_target)
                if new_yield:
                    portfolio.expected_dividend_yield = Decimal(new_yield)
                portfolio.save()
                messages.success(request, "✅ 已成功更新被動收入目標與殖利率！")
            except Exception:
                messages.error(request, "❌ 輸入的數值格式錯誤。")
            return redirect("invest:dashboard")

        else:
            #! 處理新增交易表單
            form = TransactionForm(request.POST)
            if form.is_valid():
                transaction = form.save(commit=False)
                transaction.portfolio = portfolio
                transaction.save()
                messages.success(request, f"成功紀錄一筆 {transaction.get_transaction_type_display()} 交易！")
                return redirect("invest:dashboard")
    else:
        form = TransactionForm()

    #! 統計「已實現總損益」與「累計領取股息」
    #! 統計賣出股票賺的價差
    realized_capital_gain = Transaction.objects.filter(portfolio=portfolio, transaction_type="SELL").aggregate(
        total=Sum("realized_pnl")
    )["total"] or Decimal("0")

    #! 統計領到的現金股息
    total_dividends = Transaction.objects.filter(portfolio=portfolio, transaction_type="DIVIDEND").aggregate(
        total=Sum("realized_pnl")
    )["total"] or Decimal("0")

    #! 兩者相加就是你真正放進口袋的錢！
    total_realized_pnl = realized_capital_gain + total_dividends

    #! 抓取庫存並計算損益
    holdings = Holding.objects.filter(portfolio=portfolio, total_shares__gt=0).select_related("stock", "stock__price")

    total_cost = Decimal("0")
    total_market_value = Decimal("0")
    holding_details = []

    for h in holdings:
        cost = h.total_shares * h.average_cost
        total_cost += cost

        #! 嘗試取得最新報價，若無報價則以成本價計算市值
        current_price = getattr(h.stock, "price", None)
        price_val = current_price.current_price if current_price else h.average_cost

        market_value = h.total_shares * price_val
        total_market_value += market_value

        unrealized_pnl = market_value - cost
        pnl_percent = (unrealized_pnl / cost) * Decimal("100") if cost > 0 else Decimal("0")

        holding_details.append(
            {
                "stock": h.stock,
                "shares": h.total_shares,
                "avg_cost": h.average_cost,
                "current_price": price_val,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "pnl_percent": pnl_percent,
            }
        )

    #! 動態計算總體損益與財富自由進度
    total_unrealized_pnl = total_market_value - total_cost
    total_pnl_percent = (total_unrealized_pnl / total_cost) * Decimal("100") if total_cost > 0 else Decimal("0")

    #! 動態計算所需本金：假設殖利率 5%，需本金 = 每月目標 * 12個月 / 0.05 = 每月目標 * 240
    yield_rate = portfolio.expected_dividend_yield / Decimal("100")
    if yield_rate > Decimal("0"):
        target_value = (portfolio.target_monthly_income * Decimal("12")) / yield_rate
    else:
        target_value = Decimal("0")  # * 避免除以零的錯誤
    progress_percent = (
        min((total_market_value / target_value) * Decimal("100"), Decimal("100")) if target_value > 0 else Decimal("0")
    )

    # * 判斷是否為「零庫存」的新手
    is_newbie = not holdings.exists()
    robo_form = None
    if is_newbie:
        robo_form = AIRoboAdvisorForm()

    #! 個人資產比例圓餅圖 (Pie Chart) 資料
    pie_labels = [f"{item['stock'].symbol} {item['stock'].name}" for item in holding_details]
    #! 注意：Decimal 不能直接轉 JSON，必須先轉成 float
    pie_data = [float(item["market_value"]) for item in holding_details]

    #! 準備：大盤最新統計 Top 10 資料
    #! 漲幅前 10 名
    top_gainers = (
        StockPrice.objects.filter(stock__is_active=True).select_related("stock").order_by("-daily_change_percent")[:10]
    )
    gainers_labels = [f"{p.stock.symbol} {p.stock.name}" for p in top_gainers]
    gainers_data = [float(p.daily_change_percent) for p in top_gainers]

    #! 跌幅前 10 名
    top_losers = (
        StockPrice.objects.filter(stock__is_active=True).select_related("stock").order_by("daily_change_percent")[:10]
    )
    losers_labels = [f"{p.stock.symbol} {p.stock.name}" for p in top_losers]
    losers_data = [float(p.daily_change_percent) for p in top_losers]

    #! 股價最高前 10 名
    highest_prices = (
        StockPrice.objects.filter(stock__is_active=True).select_related("stock").order_by("-current_price")[:10]
    )
    high_price_labels = [f"{p.stock.symbol} {p.stock.name}" for p in highest_prices]
    high_price_data = [float(p.current_price) for p in highest_prices]

    #! 股價最低前 10 名 (過濾掉 0 元的異常資料)
    lowest_prices = (
        StockPrice.objects.filter(stock__is_active=True, current_price__gt=0)
        .select_related("stock")
        .order_by("current_price")[:10]
    )
    low_price_labels = [f"{p.stock.symbol} {p.stock.name}" for p in lowest_prices]
    low_price_data = [float(p.current_price) for p in lowest_prices]

    context = {
        "portfolio": portfolio,  # * 把 portfolio 傳到前端，這樣才知道目前的目標設定值
        "form": form,
        "holdings": holding_details,
        "total_cost": total_cost,
        "total_market_value": total_market_value,
        "total_unrealized_pnl": total_unrealized_pnl,
        "total_pnl_percent": total_pnl_percent,
        "progress_percent": progress_percent,
        "target_value": target_value,
        "total_realized_pnl": total_realized_pnl,
        "total_dividends": total_dividends,
        "is_newbie": is_newbie,  # * 傳遞新手標記
        "robo_form": robo_form,  # * 傳遞 AI 問卷表單
    }

    #! 統計圖表
    context.update(
        {
            "pie_labels": json.dumps(pie_labels),
            "pie_data": json.dumps(pie_data),
            "gainers_labels": json.dumps(gainers_labels),
            "gainers_data": json.dumps(gainers_data),
            "losers_labels": json.dumps(losers_labels),
            "losers_data": json.dumps(losers_data),
            "high_price_labels": json.dumps(high_price_labels),
            "high_price_data": json.dumps(high_price_data),
            "low_price_labels": json.dumps(low_price_labels),
            "low_price_data": json.dumps(low_price_data),
        }
    )
    return render(request, "invest/dashboard.html", context)


def generate_ai_plan(request):
    if request.method != "POST":
        return redirect("invest:dashboard")

    form = AIRoboAdvisorForm(request.POST)
    if not form.is_valid():
        messages.error(request, "表單資料有誤，請重新填寫。")
        return redirect("invest:dashboard")

    from google import genai
    #! 取得使用者輸入的參數
    data = form.cleaned_data
    risk_map = {"LOW": "保守", "MEDIUM": "穩健", "HIGH": "積極"}
    risk_str = risk_map.get(data["risk_tolerance"])

    #! 初始化 Gemini Client
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    #! 設定系統提示詞 (System Instruction)：專注於角色扮演與規定 JSON 格式
    dynamic_instruction = """
    你是一位台灣頂級的專業理財顧問 (Robo-Advisor)。
    請務必只輸出符合以下格式的 JSON 字串，不要包含任何 Markdown 標記 (如 ```json) 或其他說明文字：
    {
        "strategy_name": "策略名稱 (例如：穩健成長高息配置)",
        "expected_annual_return": 預期年化報酬率 (數字，例如 6.5),
        "analysis": "針對該客戶的現狀與目標，給出一段約 100 字的專業分析與可行性評估",
        "holdings": [
            {
                "symbol": "台股代碼 (如 0050)",
                "name": "ETF 名稱 (如 元大台灣50)",
                "weight": 配置權重 (數字，總和需為 100),
                "reason": "推薦理由 (約 30 字)"
            }
        ]
    }
    """

    #! 組合使用者查詢 (Contents)：專注於傳遞客戶真實數據
    user_query = f"""
    請根據以下客戶資料，為他規劃一個「台股 ETF」投資組合配置。
    - 年齡：{data["current_age"]} 歲
    - 每月可定期定額投入：{data["monthly_investment"]} 元台幣
    - 目標每月被動收入：{data["target_monthly_income"]} 元台幣
    - 預計達成時間：{data["target_years"]} 年
    - 風險承受度：{risk_str}型
    """

    for model_name in FALLBACK_MODELS:
        try:
            print(f"🤖 正在嘗試使用模型: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                config={"system_instruction": dynamic_instruction},
                contents=user_query,
            )

            #! 清洗可能帶有 Markdown 標記的回傳字串並解析 JSON
            raw_text = response.text.strip() if response.text else ""
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            ai_result = json.loads(raw_text.strip())

            #! 渲染結果頁面
            return render(request, "invest/ai_plan_result.html", {"plan": ai_result, "user_data": data})
        except Exception as e:
            error_msg = str(e)
            #! 檢查是否為 429 額度耗盡錯誤
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"⚠️ 模型 {model_name} 額度已滿 (429)，準備切換下一個備援模型...")
                continue  # * 忽略錯誤，進入下一次迴圈換模型
            else:
                #! 如果是其他錯誤 (例如 JSON 解析失敗、系統斷線)，就不換模型，直接報錯
                print(f"❌ 發生非額度相關錯誤: {error_msg}")
                return redirect("invest:dashboard")

    messages.error(request, "AI 顧問目前正在休息，請稍後再試。")
    return redirect("invest:dashboard")


@login_required
def apply_ai_plan(request):
    if request.method == "POST":
        #! 接住前端傳來的 AI 建議數值
        target_income = request.POST.get("target_monthly_income")
        expected_return = request.POST.get("expected_return")

        if target_income and expected_return:
            try:
                #! 抓出使用者的預設投資組合
                portfolio, created = Portfolio.objects.get_or_create(
                    user=request.user, defaults={"name": "我的核心理財計畫"}
                )

                #! 覆寫目標與殖利率
                portfolio.target_monthly_income = Decimal(str(target_income))
                portfolio.expected_dividend_yield = Decimal(str(expected_return))
                portfolio.save()

                #! 跳出成功的提示訊息
                messages.success(
                    request,
                    f"🎉 成功套用 AI 專屬策略！已將目標月收入設為 NT$ {target_income}，並依據 AI 規劃將預期殖利率調整為 {expected_return}%。",
                )

            except (InvalidOperation, ValueError):
                messages.error(request, "匯入數值時發生錯誤，請再試一次。")
        else:
            messages.warning(request, "找不到完整的 AI 策略資料。")

    #! 完成後，直接導回儀表板
    return redirect("invest:dashboard")


@login_required
def stock_history_api(request, symbol):
    """提供給前端畫圖用的歷史股價 API"""
    try:
        import yfinance as yf
        stock = Stock.objects.get(symbol=symbol, is_active=True)
        yf_symbol = f"{stock.symbol}.TW" if stock.exchange == "TWSE" else f"{stock.symbol}.TWO"

        ticker = yf.Ticker(yf_symbol)
        #! 抓取過去 6 個月的歷史資料 (period 可以改成 '1mo', '1y' 等)
        hist = ticker.history(period="6mo")

        if hist.empty:
            return JsonResponse({"error": "找不到歷史資料"}, status=404)

        #! 把日期跟收盤價抽出來整理成陣列
        dates = [date.strftime("%Y-%m-%d") for date in hist.index]
        prices = [round(float(price), 2) for price in hist["Close"].tolist()]

        return JsonResponse({"symbol": stock.symbol, "name": stock.name, "dates": dates, "prices": prices})

    except Stock.DoesNotExist:
        return JsonResponse({"error": "系統中無此股票"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
