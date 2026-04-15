#! 遊戲中心視圖
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .models import GameProfile, SurvivorLevel, SurvivorMonster, VirtualLifeEvent


@login_required
def lobby_index(request):
    """進入綜合遊戲大廳"""
    profile, _ = GameProfile.objects.get_or_create(user=request.user)

    #! 取得玩家大頭貼
    avatar_url = ""
    if hasattr(request.user, "profile") and request.user.profile.avatar:
        avatar_url = request.user.profile.avatar.url
    elif request.user.socialaccount_set.filter(provider="google").exists():
        avatar_url = request.user.socialaccount_set.get(provider="google").extra_data.get(
            "picture", ""
        )

    context = {
        "profile": profile,
        "leve": profile.vl_cleared_boards - 1 if profile.vl_cleared_boards else 0,
        "avatar_url": avatar_url,
    }
    return render(request, "games/lobby.html", context)


@login_required
def survivor_index(request):
    """進入倖存者生存遊戲大廳"""
    profile, _ = GameProfile.objects.get_or_create(user=request.user)

    #! 抓取關卡與怪物資料
    levels = list(SurvivorLevel.objects.values("id", "name", "time_limit", "spawn_rate_mult", "stat_mult", "win_bonus"))
    monsters = []
    for m in SurvivorMonster.objects.all():
        monsters.append(
            {
                "id": m.pk,
                "name": m.name,
                "hp": m.base_hp,
                "atk": m.base_atk,
                "speed": m.base_speed,
                "size": m.base_size,
                "img_url": m.image.url if m.image else "",
            }
        )

    #! 如果資料庫沒建關卡，給一個預設值
    if not levels:
        levels = [
            {"id": 0, "name": "預設草原", "time_limit": 60, "spawn_rate_mult": 1.0, "stat_mult": 1.0, "win_bonus": 50}
        ]

    #! 取得玩家大頭貼 (相容 Google 登入或本地上傳)
    avatar_url = ""
    if hasattr(request.user, "profile") and request.user.profile.avatar:
        avatar_url = request.user.profile.avatar.url
    elif request.user.socialaccount_set.filter(provider="google").exists():
        avatar_url = request.user.socialaccount_set.get(provider="google").extra_data.get("picture", "")

    context = {
        "profile": profile,
        "levels_json": json.dumps(levels),
        "monsters_json": json.dumps(monsters),
        "avatar_url": avatar_url,
    }
    return render(request, "games/survivor.html", context)


@login_required
def survivor_save_api(request):
    """結算遊戲資料 (支援破關獎勵)"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            kills = int(data.get("kills", 0))
            time_sec = int(data.get("time", 0))
            is_win = data.get("is_win", False)
            win_bonus = int(data.get("win_bonus", 0))

            profile = request.user.game_profile
            is_new_record = False

            if time_sec > profile.survivor_max_time:
                profile.survivor_max_time = time_sec
                is_new_record = True
            if kills > profile.survivor_max_kills:
                profile.survivor_max_kills = kills

            #! 基本金幣 (擊殺/5) + 破關獎勵
            earned_coins = (kills // 5) + (win_bonus if is_win else 0)
            profile.total_coins += earned_coins
            profile.save()

            return JsonResponse(
                {
                    "status": "success",
                    "earned_coins": earned_coins,
                    "total_coins": profile.total_coins,
                    "is_new_record": is_new_record,
                }
            )
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    return JsonResponse({"status": "invalid request"}, status=405)


@login_required
def buy_upgrade_api(request):
    """處理玩家購買局外永久能力"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            upgrade_type = data.get("upgrade_type")  # 'hp', 'atk', 或 'speed'
            profile = request.user.game_profile

            #! 根據模型欄位名稱組合屬性字串 (survivor_hp_lv)
            field_name = f"survivor_{upgrade_type}_lv"
            current_level = getattr(profile, field_name)

            cost = (current_level + 1) * 50

            if profile.total_coins >= cost:
                profile.total_coins -= cost
                setattr(profile, field_name, current_level + 1)
                profile.save()

                return JsonResponse(
                    {"status": "success", "new_level": current_level + 1, "remaining_coins": profile.total_coins}
                )
            else:
                return JsonResponse({"status": "insufficient_funds", "message": "金幣不足"}, status=400)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    return JsonResponse({"status": "invalid request"}, status=405)


@login_required
def virtual_life_index(request):
    """進入虛擬人生遊戲大廳與盤面"""
    profile, _ = GameProfile.objects.get_or_create(user=request.user)

    #! 檢查是否需要初始化預設事件
    if not VirtualLifeEvent.objects.exists():
        events = [
            VirtualLifeEvent(
                name="成功建立被動收入",
                event_type="money_up",
                effect_value=30000,
                description="你的理財計畫大成功！每月被動收入達標，獲得大量金錢。",
            ),
            VirtualLifeEvent(
                name="Steam 遊戲特賣",
                event_type="money_down",
                effect_value=-1500,
                description="遇到 Steam 冬季特賣，忍不住買了幾款超讚的視覺小說遊戲。",
            ),
            VirtualLifeEvent(
                name="升級電腦硬體",
                event_type="stat_up",
                effect_value=10,
                description="將電腦處理器升級至 i5-14400F 搭配新主機板，工作與遊戲效率大增！全屬性提升。",
            ),
            VirtualLifeEvent(
                name="孝親費支出",
                event_type="money_down",
                effect_value=-5000,
                description="每個月固定給家裡的孝親費，雖然荷包失血但心情很踏實。",
            ),
        ]
        VirtualLifeEvent.objects.bulk_create(events)  # * 批次寫入資料庫

    context = {"profile": profile}
    return render(request, "games/virtual_life.html", context)


@login_required
def vl_save_api(request):
    #! 處理虛擬人生 RPG 版本的遊戲結算
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            is_win = data.get("is_win", False)
            current_level = int(data.get("level", 1))
            kill_coins = int(data.get("kill_coins", 0))  # * 取得局內累積的擊殺金幣

            profile = request.user.game_profile

            #! 基礎獲得金幣為擊殺數量
            earned_coins = kill_coins

            if is_win:
                #! 破關額外獎勵：通關層數 * 50
                win_bonus = current_level * 50
                earned_coins += win_bonus

                #! 更新最高通關層數
                if current_level >= profile.vl_cleared_boards:
                    profile.vl_cleared_boards = current_level + 1

            #! 將本次獲得的總金幣存入玩家帳戶
            profile.total_coins += earned_coins
            profile.save()

            return JsonResponse(
                {
                    "status": "success",
                    "earned_coins": earned_coins,
                    "total_coins": profile.total_coins,
                    "next_level": profile.vl_cleared_boards if is_win else current_level,
                }
            )

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    return JsonResponse({"status": "invalid request"}, status=405)
