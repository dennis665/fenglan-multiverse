#! 遊戲中心視圖
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .models import (
    GameProfile,
    MagicTowerMonster,
    MagicTowerSave,
    MagicTowerTile,
    SurvivorLevel,
    SurvivorMonster,
    VirtualLifeEvent,
)


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

            #! 根據傳入的類型判斷前綴，組合出正確的模型欄位名稱
            if upgrade_type.startswith("mt_"):
                # * 魔塔專用欄位 (例如：mt_hp_lv)
                field_name = f"{upgrade_type}_lv"
            else:
                # * 倖存者專用欄位 (例如：survivor_hp_lv)
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


@login_required
def mt_index(request):
    """進入魔塔遊戲大廳與畫面"""
    profile, _ = GameProfile.objects.get_or_create(user=request.user)

    #! 1. 初始化預設怪物與物件資料庫 (若為空)
    if not MagicTowerMonster.objects.exists():
        monsters = [
            MagicTowerMonster(
                tile_id=30, name="綠色史萊姆", hp=50, atk=20, def_stat=1, exp=1, gold=1
            ),
            MagicTowerMonster(
                tile_id=31, name="紅色蝙蝠", hp=100, atk=45, def_stat=5, exp=3, gold=2
            ),
            MagicTowerMonster(
                tile_id=32, name="骷髏怪", hp=150, atk=65, def_stat=15, exp=5, gold=3
            ),
            MagicTowerMonster(
                tile_id=33, name="魔法師", hp=200, atk=90, def_stat=25, exp=8, gold=5
            ),
            MagicTowerMonster(
                tile_id=34, name="石像", hp=400, atk=120, def_stat=50, exp=15, gold=8
            ),
            MagicTowerMonster(
                tile_id=35, name="迪亞布羅", hp=2000, atk=250, def_stat=100, exp=100, gold=50
            ),
        ]
        MagicTowerMonster.objects.bulk_create(monsters)

    #! 2. 將怪物與物件資源轉為 JSON 供 JS 使用
    resource_urls = {}
    for t in MagicTowerTile.objects.all():
        if t.image:
            resource_urls[t.tile_id] = t.image.url

    monster_data = {}
    for m in MagicTowerMonster.objects.all():
        monster_data[m.tile_id] = {
            "name": m.name,
            "hp": m.hp,
            "atk": m.atk,
            "def": m.def_stat,
            "exp": m.exp,
            "gold": m.gold,
            "img": m.image.url if m.image else "",
        }

    #! 3. 定義前五層地圖 (10x15)
    # * 0:空 1:牆 2:起點 3:上樓 4:下樓 10:黃鑰 11:黃門 12:藍鑰 13:藍門 20:血瓶 21:紅寶 22:藍寶 30-35:怪
    floors_data = {
        "1": [
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 21, 20, 1, 10, 10, 0, 0, 3, 1],  # * 樓梯在上 (8, 1)
            [1, 0, 30, 1, 0, 0, 0, 30, 0, 1],
            [1, 0, 0, 11, 0, 1, 1, 1, 0, 1],
            [1, 1, 1, 1, 0, 1, 20, 22, 10, 1],
            [1, 10, 0, 1, 0, 1, 1, 1, 11, 1],
            [1, 0, 0, 1, 0, 0, 0, 30, 0, 1],
            [1, 0, 11, 1, 0, 1, 1, 1, 0, 1],
            [1, 0, 0, 0, 0, 30, 0, 0, 0, 1],
            [1, 0, 1, 1, 1, 1, 1, 1, 0, 1],
            [1, 0, 1, 20, 10, 1, 10, 20, 0, 1],
            [1, 0, 11, 0, 0, 1, 0, 0, 0, 1],
            [1, 0, 1, 1, 1, 1, 0, 30, 0, 1],
            [1, 2, 0, 0, 0, 0, 0, 0, 0, 1],  # * 起點在下 (1, 13)
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        ],
        "2": [
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 1, 21, 20, 10, 4, 1],  # * 下樓梯對應 (8, 1)
            [1, 0, 31, 0, 1, 1, 1, 1, 0, 1],
            [1, 0, 0, 0, 13, 0, 0, 1, 0, 1],
            [1, 1, 1, 1, 1, 0, 31, 1, 0, 1],
            [1, 20, 22, 1, 0, 0, 0, 1, 0, 1],
            [1, 10, 12, 1, 0, 1, 1, 1, 11, 1],
            [1, 1, 11, 1, 0, 1, 10, 10, 0, 1],
            [1, 0, 0, 0, 0, 1, 20, 20, 0, 1],
            [1, 0, 31, 1, 1, 1, 1, 1, 0, 1],
            [1, 0, 0, 1, 12, 10, 10, 21, 0, 1],
            [1, 1, 11, 1, 1, 1, 1, 11, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 3, 0, 31, 0, 0, 0, 30, 0, 1],  # * 上樓梯對應 (1, 13)
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        ],
        "3": [
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 20, 20, 1, 10, 10, 10, 0, 3, 1],  # * 上樓梯對應 (8, 1)
            [1, 0, 32, 1, 0, 31, 0, 0, 0, 1],
            [1, 0, 0, 1, 0, 1, 1, 1, 11, 1],
            [1, 1, 11, 1, 0, 1, 21, 22, 0, 1],
            [1, 0, 0, 0, 0, 1, 1, 1, 0, 1],
            [1, 0, 31, 1, 1, 1, 20, 20, 12, 1],
            [1, 0, 0, 1, 0, 0, 0, 32, 0, 1],
            [1, 1, 1, 1, 0, 1, 1, 1, 13, 1],
            [1, 21, 22, 1, 0, 1, 0, 0, 0, 1],
            [1, 10, 10, 1, 0, 1, 0, 31, 0, 1],
            [1, 0, 11, 1, 0, 1, 1, 1, 0, 1],
            [1, 0, 0, 0, 12, 0, 0, 0, 0, 1],
            [1, 4, 0, 32, 0, 0, 0, 31, 0, 1],  # * 下樓梯對應 (1, 13)
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        ],
        "4": [
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 21, 20, 1, 10, 10, 12, 0, 4, 1],  # * 下樓梯對應 (8, 1)
            [1, 0, 33, 1, 1, 1, 1, 0, 33, 1],
            [1, 0, 0, 11, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 0, 34, 1, 1, 1, 1],
            [1, 10, 10, 1, 0, 0, 1, 20, 22, 1],
            [1, 0, 0, 1, 1, 13, 1, 0, 0, 1],
            [1, 0, 33, 1, 0, 0, 1, 0, 34, 1],
            [1, 1, 11, 1, 0, 33, 1, 1, 11, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 34, 1, 1, 1, 1, 1, 0, 1],
            [1, 0, 0, 1, 21, 22, 21, 1, 0, 1],
            [1, 0, 13, 1, 0, 34, 0, 1, 0, 1],
            [1, 3, 0, 0, 0, 0, 0, 1, 0, 1],  # * 上樓梯對應 (1, 13)
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        ],
        "5": [
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 20, 20, 20, 20, 20, 20, 0, 1],  # * 魔王通關豪華大禮包
            [1, 0, 21, 21, 21, 21, 21, 21, 0, 1],
            [1, 0, 22, 22, 22, 22, 22, 22, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 13, 1, 1, 1, 1, 1],  # * 寶藏被藍門鎖住
            [1, 1, 1, 1, 0, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 35, 1, 1, 1, 1, 1],  # * 魔王迪亞布羅 (必須擊敗才能前進)
            [1, 1, 1, 1, 0, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 11, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 12, 34, 0, 34, 10, 10, 0, 1],  # * 下方提供開門鑰匙，但有石像怪防守
            [1, 4, 0, 0, 0, 0, 0, 0, 0, 1],  # * 下樓梯對應 (1, 13)
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        ],
    }

    #! 4. 讀取存檔
    save_data = None
    if hasattr(request.user, "mt_save"):
        s = request.user.mt_save
        save_data = {
            "class_type": s.class_type,
            "level": s.level,
            "hp": s.hp,
            "atk": s.atk,
            "def": s.def_stat,
            "exp": s.exp,
            "yellow_keys": s.yellow_keys,
            "blue_keys": s.blue_keys,
            "current_floor": s.current_floor,
            "map_states": s.map_states,
            "cleared_floors": s.cleared_floors,
        }

    context = {
        "profile": profile,
        "floors_json": json.dumps(floors_data),
        "monsters_json": json.dumps(monster_data),
        "resources_json": json.dumps(resource_urls),
        "save_json": json.dumps(save_data) if save_data else "null",
    }
    return render(request, "games/magic_tower.html", context)


@login_required
def mt_save_api(request):
    """手動儲存進度 API"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            s, _ = MagicTowerSave.objects.get_or_create(user=request.user)
            s.class_type = data.get("class_type")
            s.level = data.get("level")
            s.hp = data.get("hp")
            s.atk = data.get("atk")
            s.def_stat = data.get("def")
            s.exp = data.get("exp")
            s.yellow_keys = data.get("yellow_keys")
            s.blue_keys = data.get("blue_keys")
            s.current_floor = data.get("current_floor")
            s.map_states = data.get("map_states", {})
            s.cleared_floors = data.get("cleared_floors", [])
            s.save()
            return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    return JsonResponse({"status": "error", "message": ""}, status=400)


@login_required
def mt_reward_api(request):
    """通關樓層發放局外金幣 API"""
    if request.method == "POST":
        data = json.loads(request.body)
        floor = int(data.get("floor", 0))
        is_boss = data.get("is_boss", False)

        profile = request.user.game_profile
        if floor > profile.mt_max_floor:
            reward = floor * 50 if is_boss else floor * 10
            profile.total_coins += reward
            profile.mt_max_floor = floor
            profile.save()
            return JsonResponse(
                {"status": "success", "reward": reward, "total_coins": profile.total_coins}
            )
        return JsonResponse({"status": "already_cleared"})
    return JsonResponse({"status": "error", "message": ""}, status=400)


@login_required
def mt_reset_api(request):
    """重置魔塔進度 API"""
    if request.method == "POST":
        MagicTowerSave.objects.filter(user=request.user).delete()
        profile = request.user.game_profile
        profile.mt_max_floor = 0  # * 允許重新領取獎勵
        profile.save()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error", "message": ""}, status=400)
