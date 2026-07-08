import random
from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from django.utils.timezone import now
from .models import Pet, PetStoryUnlock, DailyLoginLog, UserInventory, UserPetProfile, UserAccessory, PetExpedition, TowerProgress
from finance.models import Product


# 劇情文字與插畫對照表 (保持原有精美插圖作回憶)
DRAGON_STORIES = {
    0: {
        "title": "神秘蛋",
        "illustration": "/static/pet_system/images/pet_egg.webp",
        "text": "在一片被濃霧籠罩的古老森林深處，你發現了一顆散發著淡綠色微光的龍蛋。蛋殼上的金色紋路隨著你的呼吸微微起伏，彷彿在渴求著生命的溫暖..."
    },
    1: {
        "title": "破殼而出",
        "illustration": "/static/pet_system/images/baby_dragon.webp",
        "text": "啵的一聲輕響，蛋殼上出現了第一道裂縫！隨後一個毛茸茸的小腦袋擠了出來。牠抖了抖身上的碎殼，用那雙如星辰般明亮的大眼睛好奇地望著你，發出了軟萌的叫聲。你的冒險，就此展開。"
    },
    2: {
        "title": "初試飛羽",
        "illustration": "/static/pet_system/images/growth_dragon.webp",
        "text": "經過你的悉心照料，小幻龍已經長高了許多，可以神氣地用雙腳站立。今天，牠興奮地拍打著剛長出的小翅膀，成功在空中漂浮了三秒鐘！雖然落地時有些搖晃，但牠眼中閃爍著對天際的渴望。"
    },
    3: {
        "title": "風暴之翼",
        "illustration": "/static/pet_system/images/complete_dragon.webp",
        "text": "昔日的小雛龍已蛻變為體態優美的幻獸龍。牠展開了強健的綠色雙翼，能載著你在林間平穩滑翔。每當夜幕降臨，牠溫柔的守護便成了你最安心的港灣。牠已經準備好迎接終極的覺醒..."
    },
    4: {
        "title": "翡翠聖光",
        "illustration": "/static/pet_system/images/evolved_dragon.webp",
        "text": "在一陣耀眼的翡翠色光芒中，元素古樹的精靈為牠冠上聖光。牠張開了環繞著星屑與自然微粒的星光之翼，發出了威嚴而友善的龍吼。作為守護這片土地的翡翠聖龍，牠與你的契約將永世不滅。"
    }
}

PUPPY_STORIES = {
    0: {
        "title": "神秘蛋",
        "illustration": "/static/pet_system/images/pet_egg.webp",
        "text": "在炙熱的火山岩洞深處，你發現了一顆散發著溫熱微光、隱約有著橘紅色火焰紋理的寵物蛋。它頑強地在熱浪中跳動，正等待著勇氣與溫暖將它喚醒..."
    },
    1: {
        "title": "烈火破殼",
        "illustration": "/static/pet_system/images/baby_puppy.webp",
        "text": "咔嚓！蛋殼碎裂，一隻全身橘紅、尾巴帶有小火苗的幼犬滾了出來！牠興奮地繞著你轉圈，一邊發出清脆的汪汪聲，一邊伸出熱呼呼的舌頭舔你的手。烈火幼犬正式加入你的旅程！"
    },
    2: {
        "title": "初展犬威",
        "illustration": "/static/pet_system/images/growth_puppy.webp",
        "text": "烈火幼犬在你的細心培育下，已經長成了體型健壯的烈火犬。牠身上的火焰毛髮燃燒得更為旺盛，奔跑時會留下一道道美麗的紅光殘影。牠已經學會用熱情和叫聲嚇退森林邊緣的小怪獸了！"
    },
    3: {
        "title": "烈火神君",
        "illustration": "/static/pet_system/images/complete_puppy.webp",
        "text": "烈火犬完成了完全體的蛻變，成為了威風凜凜的烈火神犬。牠身上環繞著金紅色的護體火焰，眼神變得堅毅無比。現在的牠，不僅是你忠心耿耿的冒險夥伴，更是足以獨當一面的守護神犬！"
    },
    4: {
        "title": "神話覺醒",
        "illustration": "/static/pet_system/images/pixel_emerald_puppy.webp",
        "text": "小火犬與自然精靈靈魂共鳴，火焰化為了神聖溫和的青綠之火。牠的額頭長出了神獸麒麟般的小角，足踏祥雲。作為祥瑞的麒麟火犬，牠發誓將以溫柔與幸運護佑您的前程。"
    }
}

# 配件清單與價格
ACCESSORY_SHOP = {
    "pixel_straw_hat": {"name": "草帽", "price": 100, "slot": "head"},
    "pixel_crown": {"name": "皇冠", "price": 500, "slot": "head"},
    "pixel_sunglasses": {"name": "墨鏡", "price": 150, "slot": "face"},
    "pixel_devil_horns": {"name": "惡魔角", "price": 200, "slot": "head"},
    "pixel_angel_wings": {"name": "天使翅膀", "price": 400, "slot": "back"},
}


@login_required
def pet_dashboard(request):
    """顯示寵物主畫面"""
    return render(request, "pet_system/dashboard.html")


@login_required
@require_GET
def api_get_dashboard_data(request):
    """取得寵物主畫面所有 JSON 格式數據 (包含 v2.0 金幣、探索與爬塔)"""
    user = request.user
    
    # 確保今日登入日誌存在
    DailyLoginLog.objects.get_or_create(user=user, login_date=now().date())
    total_login_days = DailyLoginLog.objects.filter(user=user).count()
    
    # 取得或建立玩家金幣存摺
    profile, _ = UserPetProfile.objects.get_or_create(user=user)
    
    # 取得或建立爬塔進度
    tower, _ = TowerProgress.objects.get_or_create(user=user)
    
    # 取得出戰中的寵物
    active_pet_obj = Pet.objects.filter(user=user, is_active=True).first()
    
    # 肥嘟嘟守護龍 每日金幣贈送邏輯
    chubby_bonus_claimed = False
    if active_pet_obj and active_pet_obj.stage == 4 and active_pet_obj.personality == "CHUBBY":
        today = now().date()
        if profile.last_daily_claim != today:
            with transaction.atomic():
                profile = UserPetProfile.objects.select_for_update().get(id=profile.id)
                if profile.last_daily_claim != today:
                    profile.pet_gold_coins += 50
                    profile.last_daily_claim = today
                    profile.save()
                    chubby_bonus_claimed = True
    
    active_pet = None
    unclaimed_login_days = 0
    active_pet_expedition = None
    
    if active_pet_obj:
        active_pet = {
            "id": active_pet_obj.id,
            "name": active_pet_obj.name,
            "pet_type": active_pet_obj.pet_type,
            "pet_type_display": active_pet_obj.get_pet_type_display(),
            "stage": active_pet_obj.stage,
            "stage_display": active_pet_obj.get_stage_display(),
            "growth_progress": active_pet_obj.growth_progress,
            "login_days_consumed": active_pet_obj.login_days_consumed,
            "personality": active_pet_obj.personality,
            "personality_display": active_pet_obj.get_personality_display(),
            "equipped_head": active_pet_obj.equipped_head,
            "equipped_face": active_pet_obj.equipped_face,
            "equipped_back": active_pet_obj.equipped_back,
        }
        unclaimed_login_days = max(0, total_login_days - active_pet_obj.login_days_consumed)
        
        # 檢查該出戰寵物目前是否有正在進行的探索派遣
        exp = PetExpedition.objects.filter(pet=active_pet_obj).exclude(status="CLAIMED").first()
        if exp:
            # 自動更新逾期狀態為 COMPLETED
            if exp.status == "ACTIVE" and now() >= exp.end_time:
                exp.status = "COMPLETED"
                exp.save()
            active_pet_expedition = {
                "id": exp.id,
                "duration_hours": exp.duration_hours,
                "end_time": exp.end_time.isoformat(),
                "status": exp.status,
                "seconds_left": max(0, int((exp.end_time - now()).total_seconds())),
            }

    # 取得寵物庫清單
    pets = []
    for p in Pet.objects.filter(user=user).order_by("-is_active", "-created_at"):
        pets.append({
            "id": p.id,
            "name": p.name,
            "pet_type": p.pet_type,
            "pet_type_display": p.get_pet_type_display(),
            "stage": p.stage,
            "stage_display": p.get_stage_display(),
            "growth_progress": p.growth_progress,
            "is_active": p.is_active,
            "personality": p.personality,
            "personality_display": p.get_personality_display(),
            "equipped_head": p.equipped_head,
            "equipped_face": p.equipped_face,
            "equipped_back": p.equipped_back,
        })
        
    # 取得背包道具
    inventory = []
    for inv in UserInventory.objects.filter(user=user, quantity__gt=0).select_related("product"):
        default_img = "/static/pet_system/images/pet_feed.webp"
        if inv.product.name == "奇蹟進化藥水":
            default_img = "/static/pet_system/images/pixel_potion.webp"
        elif inv.product.category == "PET_EGG":
            default_img = "/static/pet_system/images/pet_egg.webp"

        inventory.append({
            "id": inv.id,
            "product_id": inv.product.id,
            "name": inv.product.name,
            "description": inv.product.description,
            "image_url": inv.product.image.url if inv.product.image else default_img,
            "quantity": inv.quantity,
            "category": inv.product.category,
        })

    # 取得玩家已解鎖的所有配件服飾
    unlocked_accessories = []
    for acc in UserAccessory.objects.filter(user=user):
        unlocked_accessories.append(acc.accessory_id)

    # 取得劇情解鎖紀錄
    story_unlocks = {}
    for unlock in PetStoryUnlock.objects.filter(user=user):
        story_unlocks[unlock.pet_type] = unlock.max_stage_reached

    return JsonResponse({
        "status": "success",
        "active_pet": active_pet,
        "active_pet_expedition": active_pet_expedition,
        "pets": pets,
        "inventory": inventory,
        "total_login_days": total_login_days,
        "unclaimed_login_days": unclaimed_login_days,
        "story_unlocks": story_unlocks,
        "pet_gold_coins": profile.pet_gold_coins,
        "tower_floor": tower.current_floor,
        "unlocked_accessories": unlocked_accessories,
        "accessory_shop": ACCESSORY_SHOP,
        "chubby_bonus_claimed": chubby_bonus_claimed,
    })


@login_required
@require_GET
def api_get_active_shimeji(request):
    """取得全站桌寵 Shimeji 渲染所需的寵物資訊 (與 dashboard 資料分離以求輕量快速)"""
    user = request.user
    if not user.is_authenticated:
        return JsonResponse({"status": "error", "message": "未登入"})
        
    active_pet = Pet.objects.filter(user=user, is_active=True).first()
    if not active_pet:
        return JsonResponse({"status": "no_pet"})
        
    # 定義像素化渲染路徑
    pixel_img = "/static/pet_system/images/pet_egg.webp"
    if active_pet.pet_type == "DRAGON":
        if active_pet.stage == 1: pixel_img = "/static/pet_system/images/baby_dragon.webp"
        elif active_pet.stage == 2: pixel_img = "/static/pet_system/images/growth_dragon.webp"
        elif active_pet.stage == 3: pixel_img = "/static/pet_system/images/complete_dragon.webp"
        elif active_pet.stage == 4:
            if active_pet.personality == "CHUBBY":
                pixel_img = "/static/pet_system/images/pixel_chubby_dragon.webp"
            elif active_pet.personality == "BRAVE":
                pixel_img = "/static/pet_system/images/pixel_star_dragon.webp"
            else:
                pixel_img = "/static/pet_system/images/pixel_emerald_dragon.webp"
    else: # PUPPY
        if active_pet.stage == 1: pixel_img = "/static/pet_system/images/baby_puppy.webp"
        elif active_pet.stage == 2: pixel_img = "/static/pet_system/images/growth_puppy.webp"
        elif active_pet.stage == 3: pixel_img = "/static/pet_system/images/complete_puppy.webp"
        elif active_pet.stage == 4:
            if active_pet.personality == "CHUBBY":
                pixel_img = "/static/pet_system/images/pixel_chubby_puppy.webp"
            elif active_pet.personality == "BRAVE":
                pixel_img = "/static/pet_system/images/pixel_star_puppy.webp"
            else:
                pixel_img = "/static/pet_system/images/pixel_emerald_puppy.webp"

    return JsonResponse({
        "status": "success",
        "name": active_pet.name,
        "pet_type": active_pet.pet_type,
        "stage": active_pet.stage,
        "stage_display": active_pet.get_stage_display(),
        "personality": active_pet.personality,
        "pixel_image_url": pixel_img,
        "equipped_head": active_pet.equipped_head,
        "equipped_face": active_pet.equipped_face,
        "equipped_back": active_pet.equipped_back,
    })


@login_required
@require_POST
def api_claim_login_energy(request):
    """提取登入能量"""
    user = request.user
    active_pet = Pet.objects.filter(user=user, is_active=True).first()
    if not active_pet:
        return JsonResponse({"status": "error", "message": "目前沒有出戰的寵物！"})

    total_login_days = DailyLoginLog.objects.filter(user=user).count()
    unclaimed = total_login_days - active_pet.login_days_consumed
    
    if unclaimed <= 0:
        return JsonResponse({"status": "error", "message": "沒有可領取的登入能量！"})

    with transaction.atomic():
        active_pet = Pet.objects.select_for_update().get(id=active_pet.id)
        unclaimed = total_login_days - active_pet.login_days_consumed
        if unclaimed > 0:
            growth_add = unclaimed * 10
            active_pet.growth_progress = min(100, active_pet.growth_progress + growth_add)
            active_pet.login_days_consumed = total_login_days
            # 累計登入成長能量 (用於性格判定)
            active_pet.save()
            
    return JsonResponse({
        "status": "success",
        "message": f"成功吸收 {unclaimed} 天的能量，成長值增加 {unclaimed * 10}！",
        "growth_progress": active_pet.growth_progress
    })


@login_required
@require_POST
def api_hatch_egg(request):
    """孵化神秘寵物蛋"""
    user = request.user
    egg_inv = UserInventory.objects.filter(user=user, product__category="PET_EGG", quantity__gt=0).first()
    if not egg_inv:
        return JsonResponse({"status": "error", "message": "背包中沒有寵物蛋，請先到商城購買！"})
        
    with transaction.atomic():
        egg_inv.quantity -= 1
        egg_inv.save()
        
        # 隨機決定孵化出幻獸綠龍或烈火幼犬
        import random
        pet_type = random.choice(["DRAGON", "PUPPY"])
        
        if pet_type == "DRAGON":
            pet_name = "神秘的龍蛋"
            story_dict = DRAGON_STORIES
        else:
            pet_name = "神秘的火犬蛋"
            story_dict = PUPPY_STORIES

        new_pet = Pet.objects.create(
            user=user,
            name=pet_name,
            pet_type=pet_type,
            stage=0,
            growth_progress=0,
            is_active=True
        )
        
        unlock, _ = PetStoryUnlock.objects.get_or_create(user=user, pet_type=pet_type)
        if unlock.max_stage_reached < 0:
            unlock.max_stage_reached = 0
            unlock.save()

    return JsonResponse({
        "status": "success",
        "message": f"成功孵化了一顆{new_pet.get_pet_type_display()}！",
        "pet_id": new_pet.id,
        "story": story_dict[0]
    })


@login_required
@require_POST
def api_feed_pet(request):
    """餵食道具"""
    user = request.user
    inv_id = request.POST.get("inventory_id")
    pet_id = request.POST.get("pet_id")
    
    inv = get_object_or_404(UserInventory, id=inv_id, user=user, quantity__gt=0)
    pet = get_object_or_404(Pet, id=pet_id, user=user)
    
    if pet.growth_progress >= 100:
        return JsonResponse({"status": "error", "message": "成長度已達 100%，請先點擊進化！"})
        
    growth_add = 0
    is_potion = False
    if inv.product.name == "美味寵物乾糧":
        growth_add = 15
    elif inv.product.name == "奇蹟進化藥水":
        growth_add = 50
        is_potion = True
    else:
        growth_add = 10

    with transaction.atomic():
        inv.quantity -= 1
        inv.save()
        
        pet.growth_progress = min(100, pet.growth_progress + growth_add)
        
        # 累加餵食次數，用於分支性格進化判定
        if is_potion:
            pet.potions_consumed += 1
        else:
            pet.feed_items_consumed += 1
            
        pet.save()

    return JsonResponse({
        "status": "success",
        "message": f"成功餵食 {inv.product.name}，成長值 +{growth_add}！",
        "growth_progress": pet.growth_progress
    })


@login_required
@require_POST
def api_evolve_pet(request):
    """點擊進化 (包含性格分支與守護龍解鎖)"""
    user = request.user
    pet_id = request.POST.get("pet_id")
    pet = get_object_or_404(Pet, id=pet_id, user=user)
    
    if pet.growth_progress < 100:
        return JsonResponse({"status": "error", "message": "成長值尚未達到 100%，無法進化！"})
        
    if pet.stage >= 4:
        return JsonResponse({"status": "error", "message": "寵物已達到最高進化形態！"})

    with transaction.atomic():
        pet.stage += 1
        if pet.stage < 4:
            pet.growth_progress = 0
        else:
            pet.growth_progress = 100
        
        if pet.stage == 1:
            if pet.pet_type == "DRAGON" and pet.name == "神秘的龍蛋":
                pet.name = "綠色雛龍"
            elif pet.pet_type == "PUPPY" and pet.name == "神秘的火犬蛋":
                pet.name = "烈火幼犬"
            
        # 終極形態 (Stage 4) 分支進化判定：
        if pet.stage == 4:
            # 1. 肥嘟嘟分支：如果完全沒有餵食任何道具 (全程靠登入天數)
            if pet.feed_items_consumed == 0 and pet.potions_consumed == 0:
                pet.personality = "CHUBBY"
                if pet.pet_type == "DRAGON":
                    pet.name = "肥嘟嘟守護龍"
                else:
                    pet.name = "肥嘟嘟烈火犬"
            # 2. 勇敢分支：餵食進化藥水大於普通飼料
            elif pet.potions_consumed > pet.feed_items_consumed:
                pet.personality = "BRAVE"
                if pet.pet_type == "DRAGON":
                    pet.name = "烈焰星光龍"
                else:
                    pet.name = "地獄烈焰犬"
            # 3. 普通分支：其他正常餵食情況
            else:
                pet.personality = "NORMAL"
                if pet.pet_type == "DRAGON":
                    pet.name = "自然翡翠龍"
                else:
                    pet.name = "麒麟火犬"
        
        pet.save()
        
        # 更新劇情解鎖紀錄
        unlock, _ = PetStoryUnlock.objects.get_or_create(user=user, pet_type=pet.pet_type)
        if pet.stage > unlock.max_stage_reached:
            unlock.max_stage_reached = pet.stage
            unlock.save()

    # 取得對應階段劇情
    if pet.pet_type == "DRAGON":
        story = DRAGON_STORIES.get(pet.stage, {}).copy()
        if pet.stage == 4:
            if pet.personality == "CHUBBY":
                story["illustration"] = "/static/pet_system/images/pixel_chubby_dragon.webp"
                story["title"] = "肥嘟嘟守護龍 降臨！"
                story["text"] = "你採取了悠閒的佛系培育，小綠龍吃飽睡、睡飽吃，在一陣響亮的飽嗝聲中，牠膨脹成了一顆毛茸茸的圓形大綠球！雖然飛不太動，但牠開心地抱著一袋金幣對你傻笑。作為肥嘟嘟守護龍，牠決定每天為你帶來好運金幣！"
            elif pet.personality == "BRAVE":
                story["illustration"] = "/static/pet_system/images/pixel_star_dragon.webp"
                story["title"] = "烈焰星光龍 覺醒！"
                story["text"] = "在大量魔力藥水的洗禮下，龍蛋殼內部的熾烈核心被激發！牠的身軀燃起了蔚藍星焰，翅膀環繞著燃燒星斗。烈焰星光龍以英勇無比的姿態長嘯，這股強大的攻擊力將助你在塔頂所向批靡！"
    else:
        story = PUPPY_STORIES.get(pet.stage, {}).copy()
        if pet.stage == 4:
            if pet.personality == "CHUBBY":
                story["illustration"] = "/static/pet_system/images/pixel_chubby_puppy.webp"
                story["title"] = "肥嘟嘟烈火犬 降臨！"
                story["text"] = "小火犬在你的寵愛下吃飽就睡，最後竟然胖成了一個燃燒著微弱小火苗的圓滾滾毛球！雖然連跑路都用滾的，但牠非常溫順，每天趴在門口幫你叼著裝滿 50 寵物金幣的袋子。今天也是暖呼呼的一天！"
            elif pet.personality == "BRAVE":
                story["illustration"] = "/static/pet_system/images/pixel_star_puppy.webp"
                story["title"] = "地獄烈焰星犬 覺醒！"
                story["text"] = "在奇蹟進化藥水灌溉下，幼犬體內的遠古地獄之火被徹底點燃！牠的身軀化作黑曜石裝甲，雙眼閃爍著金紅神光，全身噴湧出熔岩般的紅星之焰！地獄烈焰犬將以無敵的英姿為你撕碎冒險塔的所有妖魔！"

    return JsonResponse({
        "status": "success",
        "message": f"恭喜！您的寵物已進化為 {pet.get_stage_display()} ({pet.name})！",
        "new_stage": pet.stage,
        "new_stage_display": pet.get_stage_display(),
        "new_name": pet.name,
        "story": story
    })


@login_required
@require_POST
def api_rename_pet(request):
    """重新命名寵物"""
    user = request.user
    pet_id = request.POST.get("pet_id")
    new_name = request.POST.get("name", "").strip()
    
    if not new_name:
        return JsonResponse({"status": "error", "message": "名字不能為空！"})
    if len(new_name) > 20:
        return JsonResponse({"status": "error", "message": "名字太長了，最多 20 個字！"})

    pet = get_object_or_404(Pet, id=pet_id, user=user)
    pet.name = new_name
    pet.save()
    
    return JsonResponse({"status": "success", "message": "寵物命名成功！", "name": pet.name})


@login_required
@require_POST
def api_switch_active_pet(request):
    """切換出戰寵物"""
    user = request.user
    pet_id = request.POST.get("pet_id")
    pet = get_object_or_404(Pet, id=pet_id, user=user)
    
    with transaction.atomic():
        Pet.objects.filter(user=user).update(is_active=False)
        pet.is_active = True
        pet.save()
    
    return JsonResponse({"status": "success", "message": f"成功召喚 {pet.name} 出戰！", "pet_id": pet.id})


@login_required
@require_GET
def api_get_story(request):
    """重溫回顧劇情"""
    pet_type = request.GET.get("pet_type", "DRAGON")
    stage = int(request.GET.get("stage", 0))
    
    if pet_type == "DRAGON" and stage in DRAGON_STORIES:
        return JsonResponse({"status": "success", "story": DRAGON_STORIES[stage]})
    elif pet_type == "PUPPY" and stage in PUPPY_STORIES:
        return JsonResponse({"status": "success", "story": PUPPY_STORIES[stage]})
    return JsonResponse({"status": "error", "message": "故事章節不存在！"})


# ==========================================
# v2.0 新增：探索派遣 (Expeditions)
# ==========================================

@login_required
@require_POST
def api_start_expedition(request):
    """開始派遣探索 (1, 2, 4, 20 小時)"""
    user = request.user
    pet_id = request.POST.get("pet_id")
    hours = int(request.POST.get("hours", 1))
    
    if hours not in [1, 2, 4, 20]:
        return JsonResponse({"status": "error", "message": "無效的探索時長！"})
        
    pet = get_object_or_404(Pet, id=pet_id, user=user)
    
    # 檢查是否有正在進行的探索
    exists = PetExpedition.objects.filter(pet=pet).exclude(status="CLAIMED").exists()
    if exists:
        return JsonResponse({"status": "error", "message": "該寵物已在探索中，或是等待領取獎勵中！"})
        
    end_time = now() + timedelta(hours=hours)
    
    exp = PetExpedition.objects.create(
        pet=pet,
        duration_hours=hours,
        end_time=end_time,
        status="ACTIVE"
    )
    
    return JsonResponse({
        "status": "success",
        "message": f"召喚 {pet.name} 出發！探索派遣中，預計時長 {hours} 小時。",
        "end_time": end_time.isoformat()
    })


@login_required
@require_POST
def api_claim_expedition_rewards(request):
    """領取探索派遣獎勵"""
    user = request.user
    exp_id = request.POST.get("expedition_id")
    exp = get_object_or_404(PetExpedition, id=exp_id, pet__user=user)
    
    if exp.status == "CLAIMED":
        return JsonResponse({"status": "error", "message": "獎勵已經領取過了！"})
        
    if now() < exp.end_time:
        return JsonResponse({"status": "error", "message": "探索時間還沒到，請耐心等待！"})

    # 計算獎勵額度 (隨小時數提高)
    coins_earned = 0
    won_accessory = None
    won_potion = False
    
    # 隨機池
    accessories_pool = list(ACCESSORY_SHOP.keys())
    
    if exp.duration_hours == 1:
        coins_earned = random.randint(10, 20)
        if random.random() < 0.10: # 10% 配件
            won_accessory = random.choice(accessories_pool)
        if random.random() < 0.001: # 0.1% 進化石(藥水)
            won_potion = True
            
    elif exp.duration_hours == 2:
        coins_earned = random.randint(25, 45)
        if random.random() < 0.20: # 20% 配件
            won_accessory = random.choice(accessories_pool)
        if random.random() < 0.003: # 0.3% 進化石
            won_potion = True
            
    elif exp.duration_hours == 4:
        coins_earned = random.randint(60, 100)
        if random.random() < 0.40: # 40% 配件
            won_accessory = random.choice(accessories_pool)
        if random.random() < 0.01: # 1% 進化石
            won_potion = True
            
    elif exp.duration_hours == 20:
        coins_earned = random.randint(350, 500)
        won_accessory = random.choice(accessories_pool) # 100% 獲得配件
        if random.random() < 0.05: # 5% 進化石
            won_potion = True

    with transaction.atomic():
        # 1. 發送金幣
        profile, _ = UserPetProfile.objects.get_or_create(user=user)
        profile.pet_gold_coins += coins_earned
        profile.save()
        
        # 2. 發送配件 (去重保存，累積數量)
        if won_accessory:
            acc, _ = UserAccessory.objects.get_or_create(user=user, accessory_id=won_accessory)
            acc.quantity += 1
            acc.save()
            
        # 3. 發送進化石 (奇蹟藥水背包數量 +1)
        if won_potion:
            potion_prod = Product.objects.filter(name="奇蹟進化藥水").first()
            if potion_prod:
                inv, _ = UserInventory.objects.get_or_create(user=user, product=potion_prod)
                inv.quantity += 1
                inv.save()
                
        # 4. 更新任務狀態
        exp.status = "CLAIMED"
        exp.save()

    return JsonResponse({
        "status": "success",
        "message": f"領取成功！獲得寵物金幣 x{coins_earned}！",
        "coins_earned": coins_earned,
        "accessory_won": won_accessory,
        "accessory_won_display": ACCESSORY_SHOP.get(won_accessory, {}).get("name", "") if won_accessory else None,
        "potion_won": won_potion,
    })


# ==========================================
# v2.0 新增：服飾裝飾商城與裝備 (Shop & Equip)
# ==========================================

@login_required
@require_POST
def api_buy_accessory(request):
    """使用寵物金幣購買裝飾品"""
    user = request.user
    acc_id = request.POST.get("accessory_id")
    
    if acc_id not in ACCESSORY_SHOP:
        return JsonResponse({"status": "error", "message": "商品不存在！"})
        
    item = ACCESSORY_SHOP[acc_id]
    price = item["price"]
    
    with transaction.atomic():
        profile = UserPetProfile.objects.select_for_update().get(user=user)
        
        # 檢查是否已擁有該飾品 (通常買一個即可，這裡防重複或允許重複購買)
        owned = UserAccessory.objects.filter(user=user, accessory_id=acc_id).exists()
        if owned:
            return JsonResponse({"status": "error", "message": "您已經擁有該裝飾品囉，不須重複購買！"})
            
        if profile.pet_gold_coins < price:
            return JsonResponse({"status": "error", "message": "您的寵物金幣餘額不足，快去探索或爬塔賺取！"})
            
        # 扣款
        profile.pet_gold_coins -= price
        profile.save()
        
        # 發貨
        UserAccessory.objects.create(user=user, accessory_id=acc_id, quantity=1)

    return JsonResponse({
        "status": "success",
        "message": f"成功購買裝飾品：{item['name']}！"
    })


@login_required
@require_POST
def api_equip_accessory(request):
    """穿戴或卸下配件"""
    user = request.user
    pet_id = request.POST.get("pet_id")
    slot = request.POST.get("slot") # head, face, back
    acc_id = request.POST.get("accessory_id") # 可以是空字串，代表脫下
    
    pet = get_object_or_404(Pet, id=pet_id, user=user)
    
    if slot not in ["head", "face", "back"]:
        return JsonResponse({"status": "error", "message": "無效的裝備槽位！"})
        
    if acc_id:
        # 檢查玩家是否擁有此配件
        owned = UserAccessory.objects.filter(user=user, accessory_id=acc_id).exists()
        if not owned:
            return JsonResponse({"status": "error", "message": "您尚未擁有該配件，請先到商城購買！"})
            
        # 檢查槽位是否匹配
        if ACCESSORY_SHOP.get(acc_id, {}).get("slot") != slot:
            return JsonResponse({"status": "error", "message": "裝備槽位與配件類型不相符！"})
            
    # 進行裝備/脫下
    if slot == "head":
        pet.equipped_head = acc_id or None
    elif slot == "face":
        pet.equipped_face = acc_id or None
    elif slot == "back":
        pet.equipped_back = acc_id or None
        
    pet.save()
    
    return JsonResponse({
        "status": "success",
        "message": "裝備更新完畢！"
    })


# ==========================================
# v2.0 新增：爬塔自動回合制戰鬥 (Tower Battle)
# ==========================================

@login_required
@require_POST
def api_tower_battle_result(request):
    """戰鬥結算 API"""
    user = request.user
    pet_id = request.POST.get("pet_id")
    victory = request.POST.get("victory") == "true"
    
    pet = get_object_or_404(Pet, id=pet_id, user=user)
    tower, _ = TowerProgress.objects.get_or_create(user=user)
    
    if not victory:
        return JsonResponse({"status": "success", "message": "戰鬥失敗，繼續努力！"})
        
    # 計算勝利獎勵金幣 = 當前層數 * 10
    coins_reward = tower.current_floor * 10
    
    with transaction.atomic():
        profile, _ = UserPetProfile.objects.get_or_create(user=user)
        profile.pet_gold_coins += coins_reward
        profile.save()
        
        # 關卡層數 + 1
        tower.current_floor += 1
        tower.save()

    return JsonResponse({
        "status": "success",
        "message": f"挑戰成功！闖入第 {tower.current_floor} 層！獲得寵物金幣 x{coins_reward}！",
        "coins_reward": coins_reward,
        "new_floor": tower.current_floor
    })


@login_required
@require_POST
def api_setup_shop_products(request):
    """一鍵建立商城預設寵物商品（限管理員）"""
    if not request.user.is_staff:
        return JsonResponse({"status": "error", "message": "權限不足，必須是管理員！"})
        
    from finance.models import Product
    
    defaults = [
        {
            "name": "神秘寵物蛋",
            "category": "PET_EGG",
            "description": "孵化出像素綠龍幼獸的神秘蛋，能帶給您忠誠的陪伴與神奇的冒險！",
            "price_in_points": 50,
            "stock": 999,
        },
        {
            "name": "美味寵物乾糧",
            "category": "PET_FOOD",
            "description": "像素寵物最愛吃的頂級乾糧，餵食能增加 15 點成長度！",
            "price_in_points": 10,
            "stock": 999,
        },
        {
            "name": "奇蹟進化藥水",
            "category": "PET_FOOD",
            "description": "極其珍貴的魔力藥水，服用能瞬間暴增 50 點成長度，是快速進化不可或缺的秘寶！",
            "price_in_points": 80,
            "stock": 999,
        }
    ]
    
    created_count = 0
    for item in defaults:
        prod, created = Product.objects.get_or_create(
            name=item["name"],
            defaults={
                "category": item["category"],
                "description": item["description"],
                "price_in_points": item["price_in_points"],
                "stock": item["stock"],
                "is_active": True
            }
        )
        if created:
            created_count += 1
            
    return JsonResponse({
        "status": "success",
        "message": f"商城初始化成功！已新建 {created_count} 項商品（神秘寵物蛋、美味寵物乾糧、奇蹟進化藥水）。"
    })
