from django.shortcuts import render


def lucky_draw(request):
    return render(request, "users/lucky_draw.html")