from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Stock, Transaction


class TransactionForm(forms.ModelForm):
    #! 讓股票選單支援搜尋，並限制只能選已啟用的標的
    stock = forms.ModelChoiceField(
        queryset=Stock.objects.filter(is_active=True).order_by("symbol"),
        widget=forms.Select(attrs={"class": "form-select select2"}),
        label=_("交易標的"),
    )
    trade_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label=_("交易日期"),
    )

    class Meta:
        model = Transaction
        fields = ["stock", "transaction_type", "shares", "price_per_share", "fee", "trade_date"]
        widgets = {
            "transaction_type": forms.Select(attrs={"class": "form-select"}),
            "shares": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "price_per_share": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "fee": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        }


class AIRoboAdvisorForm(forms.Form):
    #! 下拉選單的選項也能翻譯
    RISK_CHOICES = [
        ("LOW", _("保守型 (追求穩定，無法承受本金大幅波動)")),
        ("MEDIUM", _("穩健型 (平衡風險與報酬，可接受 10%-20% 回檔)")),
        ("HIGH", _("積極型 (追求高成長，能承受 30% 以上的市場波動)")),
    ]

    current_age = forms.IntegerField(
        label=_("目前年齡"),
        min_value=18,
        max_value=100,
        initial=30,  # * 預設值調整
        #! Placeholder 也可以直接包進翻譯裡
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": _("例如: 30")}),
    )

    monthly_investment = forms.IntegerField(
        label=_("每月可定期定額投入 (NT$)"),
        min_value=1000,
        initial=10000,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1000"}),
    )

    target_monthly_income = forms.IntegerField(
        label=_("目標每月被動收入 (NT$)"),
        min_value=1000,
        initial=30000,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1000"}),
    )

    target_years = forms.IntegerField(
        label=_("預計多少年後達成目標？"),
        min_value=1,
        max_value=50,
        initial=15,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": _("例如: 15")}),
    )

    risk_tolerance = forms.ChoiceField(
        label=_("風險承受度"),
        choices=RISK_CHOICES,
        initial="MEDIUM",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
