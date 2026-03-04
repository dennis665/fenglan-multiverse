import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.timezone import localtime, now
from django.views.decorators.csrf import csrf_exempt

from .ecpay_payment_sdk import ECPayPaymentSdk
from .models import PointPackage, PointTransaction, Product, RechargeOrder, ShopOrder, UserPoints


#! 測試
def ecpay_checkout(request):
    # 【GET 請求】：顯示測試按鈕頁面
    if request.method == "GET":
        return render(request, "finance/test_checkout.html")

    # 【POST 請求】：執行綠界參數打包與跳轉
    if request.method == "POST":
        # 1. 初始化綠界 SDK
        ecpay_payment_sdk = ECPayPaymentSdk(
            MerchantID=settings.MERCHANT_ID, HashKey=settings.HASH_KEY, HashIV=settings.HASH_IV
        )

        # 2. 建立訂單基本資訊
        trade_no = f"CSI{int(time.time())}"  # 確保每次測試編號都不一樣
        order_amount = 1000
        trade_date = localtime(now()).strftime("%Y/%m/%d %H:%M:%S")
        back_url = request.build_absolute_uri(reverse("finance:checkout"))

        # 3. 準備參數字典
        order_params = {
            "MerchantTradeNo": trade_no,
            "MerchantTradeDate": trade_date,
            "TotalAmount": order_amount,
            "TradeDesc": "CSI Portal 點數儲值測試",
            "ItemName": "CSI儲值點數 1000 點",
            # 💡 提示：如果只是先測試畫面跳轉，ReturnURL 隨便填個有效網址即可
            # 等要測試伺服器背景回傳對帳時，再換成你的 Ngrok 網址
            "ReturnURL": "https://www.google.com/",
            # 這是結帳成功後，畫面上的「返回商店」按鈕要導向哪裡
            "ClientBackURL": back_url,
            "ChoosePayment": "ALL",
            "EncryptType": 1,
        }

        try:
            # 4. 【修正錯誤】：將 order_params 傳入，SDK 會幫你算出 CheckMacValue 簽章
            final_params = ecpay_payment_sdk.create_order(order_params)

            # 5. 【修正錯誤】：將網址與剛剛算好的參數，轉換成會自動提交的 HTML 表單
            action_url = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
            html_form = ecpay_payment_sdk.gen_html_post_form(action_url, final_params)

            # 直接回傳給瀏覽器，瀏覽器會收到一堆 hidden input 以及一段自動執行的 JavaScript
            return HttpResponse(html_form)

        except Exception as e:
            return HttpResponse(f"發生錯誤：{e}")
    return HttpResponse("Method Not Allowed", status=405)


@login_required
def recharge_store(request):
    """顯示所有儲值方案"""
    packages = PointPackage.objects.filter(is_active=True).order_by("price")
    return render(request, "finance/recharge_store.html", {"packages": packages})


@login_required
def point_shop(request):
    """商城首頁"""
    products = Product.objects.filter(is_active=True, stock__gt=0)
    wallet, _ = UserPoints.objects.get_or_create(user=request.user)
    return render(request, "finance/shop.html", {"products": products, "wallet": wallet})


@login_required
def process_recharge(request, package_id):
    """處理儲值請求並跳轉綠界"""
    if request.method == "POST":
        package = get_object_or_404(PointPackage, id=package_id)

        # 1. 建立訂單，注意！前綴必須改成 REC，回傳時才能正確路由！
        trade_no = f"REC{int(time.time())}{request.user.id}"

        RechargeOrder.objects.create(
            user=request.user,
            merchant_trade_no=trade_no,
            amount=package.price,
            status="PENDING",
        )

        # 2. 初始化綠界 SDK (使用有 3D 驗證的測試帳號)
        ecpay_payment_sdk = ECPayPaymentSdk(MerchantID="3002607", HashKey="pwFHCqoQZGmho4w6", HashIV="EkRm7iFT261dpevs")
        return_url = request.build_absolute_uri(reverse("finance:ecpay_return"))
        back_url = request.build_absolute_uri(reverse("finance:shop"))

        # 3. 打包綠界參數
        order_params = {
            "MerchantTradeNo": trade_no,
            "MerchantTradeDate": localtime(now()).strftime("%Y/%m/%d %H:%M:%S"),
            "TotalAmount": package.price,
            "TradeDesc": f"CSI Portal 點數儲值 - {package.name}",
            "ItemName": f"{package.name} ({package.deposit_points}點)",
            # ⚠️ 重要：這裡必須填寫你正在運作的 Ngrok 網址
            "ReturnURL": return_url,
            # 結帳完成後，畫面上的「返回商店」要導向哪裡
            "ClientBackURL": back_url,
            "ChoosePayment": "ALL",
            "EncryptType": 1,
        }

        # 4. 產生跳轉 HTML
        action_url = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
        html_form = ecpay_payment_sdk.gen_html_post_form(action_url, ecpay_payment_sdk.create_order(order_params))

        return HttpResponse(html_form)

    return HttpResponse("Method Not Allowed", status=405)


@login_required
def checkout_cart(request):
    """處理結帳與點數扣抵"""
    if request.method == "POST":
        product_id = request.POST.get("product_id")
        bonus_to_use = int(request.POST.get("bonus_to_use", 0))

        product = get_object_or_404(Product, id=product_id)

        with transaction.atomic():
            # 鎖定使用者的錢包，防止重複扣款 (Race Condition 防護)
            wallet = UserPoints.objects.select_for_update().get(user=request.user)

            # 計算花費
            total_price = product.price_in_points

            # 檢查紅利點數是否合法 (不能超過訂單總價，也不能超過擁有的紅利)
            if bonus_to_use > wallet.bonus_points or bonus_to_use > total_price:
                messages.error(request, "紅利點數折抵異常！")
                return redirect("finance:shop")

            deposit_to_use = total_price - bonus_to_use

            # 檢查儲值點數是否足夠
            if deposit_to_use > wallet.deposit_points:
                messages.error(request, "儲值點數餘額不足，請先儲值！")
                return redirect("finance:recharge_store")

            # 1. 扣除庫存
            product.stock -= 1
            product.save()

            # 2. 扣除錢包點數
            wallet.bonus_points -= bonus_to_use
            wallet.deposit_points -= deposit_to_use
            wallet.save()

            # 3. 建立訂單
            shop_order = ShopOrder.objects.create(
                user=request.user, total_price=total_price, deposit_used=deposit_to_use, bonus_used=bonus_to_use
            )

            # 4. 寫入流水帳 (分開紀錄，方便查帳)
            if deposit_to_use > 0:
                PointTransaction.objects.create(
                    user=request.user,
                    transaction_type="PURCHASE",
                    point_type="DEPOSIT",
                    amount=-deposit_to_use,
                    reference_id=f"SHOP-{shop_order.pk}",
                    description=f"購買 {product.name}",
                )
            if bonus_to_use > 0:
                PointTransaction.objects.create(
                    user=request.user,
                    transaction_type="PURCHASE",
                    point_type="BONUS",
                    amount=-bonus_to_use,
                    reference_id=f"SHOP-{shop_order.pk}",
                    description=f"購買 {product.name} (紅利折抵)",
                )

            messages.success(request, f"成功購買 {product.name}！")
            return redirect("finance:shop")
    return HttpResponse("Method Not Allowed", status=405)


@login_required
def checkout_product_ecpay(request, product_id):
    """直接使用綠界購買商品"""
    if request.method == "POST":
        product = get_object_or_404(Product, id=product_id)

        # 1. 建立字首為 SHOP 的綠界訂單編號
        trade_no = f"SHOP{int(time.time())}{request.user.id}"

        # 2. 建立待付款的購物訂單
        ShopOrder.objects.create(
            user=request.user,
            product=product,
            payment_method="ECPAY",
            status="PENDING",
            amount_paid=product.price_ntd,
            ecpay_trade_no=trade_no,
        )

        # 3. 呼叫綠界 SDK 打包參數
        ecpay_payment_sdk = ECPayPaymentSdk(
            MerchantID=settings.MERCHANT_ID, HashKey=settings.HASH_KEY, HashIV=settings.HASH_IV
        )
        return_url = request.build_absolute_uri(reverse("finance:ecpay_return"))
        back_url = request.build_absolute_uri(reverse("finance:shop"))
        order_params = {
            "MerchantTradeNo": trade_no,
            "MerchantTradeDate": localtime(now()).strftime("%Y/%m/%d %H:%M:%S"),
            "TotalAmount": product.price_ntd,
            "TradeDesc": f"購買 {product.name}",
            "ItemName": product.name,
            "ReturnURL": return_url,
            "ClientBackURL": back_url,
            "ChoosePayment": "ALL",
            "EncryptType": 1,
        }

        html_form = ecpay_payment_sdk.gen_html_post_form(
            "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5", ecpay_payment_sdk.create_order(order_params)
        )
        return HttpResponse(html_form)
    return HttpResponse("Method Not Allowed", status=405)


# ⚠️ 必須加上 csrf_exempt，因為這個 POST 是綠界發的，不會有你的 CSRF Token
@csrf_exempt
def ecpay_return(request):
    """處理綠界背景發送的付款結果通知"""
    if request.method == "POST":
        receive_data = request.POST.dict()

        # 初始化 SDK 來驗證簽章
        ecpay_payment_sdk = ECPayPaymentSdk(
            MerchantID=settings.MERCHANT_ID, HashKey=settings.HASH_KEY, HashIV=settings.HASH_IV
        )
        received_mac = receive_data.get("CheckMacValue")
        calculated_mac = ecpay_payment_sdk.generate_check_value(receive_data)
        is_valid = received_mac == calculated_mac

        if is_valid and receive_data.get("RtnCode") == "1":
            trade_no = receive_data.get("MerchantTradeNo")

            # ✅ 路由 1：點數儲值處理
            if trade_no.startswith("REC"):
                order = RechargeOrder.objects.filter(merchant_trade_no=trade_no, status="PENDING").first()
                if order:
                    # 1. 更新訂單狀態
                    order.status = "SUCCESS"
                    order.save()

                    # 2. 找出他當初買的方案 (透過金額反查，實務上建議在 RechargeOrder 加個 package 外鍵更安全)
                    package = PointPackage.objects.filter(price=order.amount).first()

                    if package:
                        # 3. 🛡️ 使用 Transaction 安全地把點數加進錢包
                        with transaction.atomic():
                            wallet, _ = UserPoints.objects.select_for_update().get_or_create(user=order.user)
                            wallet.deposit_points += package.deposit_points
                            wallet.bonus_points += package.bonus_points
                            wallet.save()

                            # 4. 寫入流水帳 (儲值點數)
                            PointTransaction.objects.create(
                                user=order.user,
                                transaction_type="RECHARGE",
                                point_type="DEPOSIT",
                                amount=package.deposit_points,
                                reference_id=trade_no,
                                recharge_order=order,
                                description=f"綠界儲值方案：{package.name}",
                            )
                            # 如果有送紅利，額外記一筆紅利流水帳
                            if package.bonus_points > 0:
                                PointTransaction.objects.create(
                                    user=order.user,
                                    transaction_type="REWARD",
                                    point_type="BONUS",
                                    amount=package.bonus_points,
                                    reference_id=trade_no,
                                    recharge_order=order,
                                    description=f"儲值滿額贈紅利：{package.name}",
                                )

            # ✅ 路由 2：直接刷卡買商品處理 (你保留的擴充功能)
            elif trade_no.startswith("SHOP"):
                order = ShopOrder.objects.filter(ecpay_trade_no=trade_no, status="PENDING").first()
                if order and order.product:
                    order.status = "PAID"
                    order.product.stock -= order.quantity
                    order.product.save()
                    order.save()

            # 必須回傳 1|OK 給綠界，否則綠界會以為你沒收到，一直重複發送！
            return HttpResponse("1|OK")

        return HttpResponse("0|ErrorMessage")
    return HttpResponse("Method Not Allowed", status=405)
