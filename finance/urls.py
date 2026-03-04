from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    #! 測試儲值
    path("checkout/", views.ecpay_checkout, name="checkout"),
    #! 💰 儲值中心
    path("recharge/", views.recharge_store, name="recharge_store"),
    #! 處理儲值的隱藏路由 (帶入方案 ID)
    path("recharge/<int:package_id>/", views.process_recharge, name="process_recharge"),
    #! 🛍️ 點數商城首頁
    path("shop/", views.point_shop, name="shop"),
    #! 處理點數結帳的隱藏路由
    path("shop/checkout/", views.checkout_cart, name="checkout_cart"),
    #! 💳 綠界金流共用回傳路由
    path("ecpay/return/", views.ecpay_return, name="ecpay_return"),
]
