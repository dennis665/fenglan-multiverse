#! 遊戲中心視圖
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .models import GameProfile, SurvivorLevel, SurvivorMonster


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
