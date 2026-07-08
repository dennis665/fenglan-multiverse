import os
from PIL import Image

def create_pixel_sprite(grid, colors, output_path, scale=4):
    """
    根據網格陣列與色彩映射建立一個放大比例的去背 WebP 像素圖。
    grid: 32x32 的字串列表或字元陣列。
    colors: 字典，對應字元到 (R, G, B, A) 顏色。
    """
    width, height = 32, 32
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    
    for y in range(height):
        for x in range(width):
            if y < len(grid) and x < len(grid[y]):
                char = grid[y][x]
                if char in colors:
                    img.putpixel((x, y), colors[char])
                    
    # 以 Nearest Neighbor 放大，保持像素顆粒感
    img_scaled = img.resize((width * scale, height * scale), Image.NEAREST)
    
    # 確保輸出目錄存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img_scaled.save(output_path, "WEBP", quality=100)

def main():
    # 共同色票
    c = {
        " ": (0, 0, 0, 0),        # 透明
        ".": (0, 0, 0, 255),      # 黑色輪廓
        "w": (255, 255, 255, 255),# 白色
        "g": (46, 204, 113, 255), # 綠色 (主色)
        "d": (39, 174, 96, 255),  # 暗綠色 (陰影)
        "l": (145, 220, 90, 255), # 亮綠色
        "y": (241, 196, 15, 255), # 黃色 (腹部)
        "o": (230, 126, 34, 255), # 橘色 (翅膀)
        "r": (231, 76, 60, 255),  # 紅色
        "b": (52, 152, 219, 255), # 藍色
        "p": (155, 89, 182, 255), # 紫色
        "k": (244, 208, 63, 255), # 金色
        "s": (189, 195, 199, 255),# 灰色
        "f": (212, 172, 13, 255), # 棕黃色 (草帽)
        "e": (108, 52, 131, 255), # 深紫色
        "z": (245, 183, 177, 255),# 粉紅色 (腮紅)
    }

    # 1. 🥚 寵物蛋 (32x32 網格)
    egg = [
        "                                ",
        "             ......             ",
        "           ..gggggg..           ",
        "          .gggglggggg.          ",
        "         .gggllwlggggg.         ",
        "        .ggllw...wlgggg.        ",
        "       .ggllw.yyy.wlgggg.       ",
        "       .glll.yyyyy.lggggg.      ",
        "      .gllll.yyyyy.lgggggg.     ",
        "      .gllll.yyyyy.ldddggg.     ",
        "      .glllll.yyy.ldddddgg.     ",
        "      .gllllll...lddddddgg.     ",
        "      .gllllllllldddddddgg.     ",
        "      .gllllllllldddddddgg.     ",
        "       .glllllllldddddddgg.     ",
        "       .gdddddddldddddddg.      ",
        "        .gdddddddddddddd.       ",
        "         .gdddddddddddd.        ",
        "          ..dddddddd..          ",
        "            ........            ",
    ]
    
    # 2. 🍼 幼年體 (可愛小綠龍)
    baby = [
        "                                ",
        "             ......             ",
        "           ..gggggg..           ",
        "          .gggglggggg.          ",
        "         .ggllwwlwwggg.         ",
        "        .ggllw.wl.wldgg.        ",
        "        .ggllw.wl.wlddd.        ",
        "        .glllwwlwwldddg.        ",
        "         .glllllllllgg.         ",
        "          ..gzzzzzg..           ",
        "          .gggggggggg.          ",
        "         .gg..gggg..gg.         ",
        "        .gg.oo.gg.oo.gg.        ",
        "        .g.ooo.gg.ooo.g.        ",
        "        .g.ooo.gg.ooo.g.        ",
        "         .g.o.gggg.o.g.         ",
        "          .ggggggggg.           ",
        "           .g.g.g.g.            ",
        "           .g.g.g.g.            ",
        "            . . . .             ",
    ]

    # 3. 🦖 成長體 (站立頑皮小龍)
    growth = [
        "                                ",
        "            .......             ",
        "          ..ggggggg..           ",
        "         .ggggllggggg.          ",
        "        .gggllwwlwwggg.         ",
        "        .ggllw.wl.wldgg.        ",
        "        .ggllw.wl.wlddd.        ",
        "        .glllwwlwwldddg.        ",
        "         .glllllllllgg.         ",
        "         .g.gzzzzzg.g.          ",
        "          ..ggggggg..           ",
        "           .gyyyyyg.     ..     ",
        "          .ggyyyyygg.   .oo.    ",
        "         .gggyyyyyggg. .ooo.    ",
        "         .gggyyyyyggg..ooo.     ",
        "         .gggyyyyygg..ooo.      ",
        "          .gdddddddgg...        ",
        "          .gdddddddgg.          ",
        "         .gggg   gggg.          ",
        "         .gg.     .gg.          ",
        "         ..         ..          ",
    ]

    # 4. 🐉 完全體 (大翅膀飛天綠龍)
    complete = [
        "                                ",
        "            .......             ",
        "          ..ggggggg..           ",
        "         .ggggllggggg.          ",
        "        .gggllwwlwwggg.         ",
        "       .gggllw.wl.wldgg.        ",
        "       .gglllw.wl.wlddd.        ",
        "       .gllllwwlwwldddg.        ",
        "      .gglllllllllllggg.        ",
        "      .ggll.gzzzzzg.llgg.       ",
        "       ..ggggggggggg..          ",
        "     ....gyyyyyyyyyg....        ",
        "    .oooo.gyyyyyyyyy.oooo.      ",
        "   .ooooo.ggyyyyyygg.ooooo.     ",
        "   .ooooo.gggyyyyggg.ooooo.     ",
        "    .ooo. gddddddddg .ooo.      ",
        "     ..  .gddddddddg  ..        ",
        "         .gddddddddg            ",
        "         .gggg  gggg.           ",
        "         .ggg.  .ggg.           ",
        "          ..      ..            ",
    ]

    # 5. 👑 進化分支 A：自然翡翠龍 (綠意森林聖龍)
    emerald = [
        "            ..  ..              ",
        "           .gg..gg.             ",
        "            .......             ",
        "          ..ggggggg..           ",
        "         .ggggllggggg.          ",
        "        .gggllwwlwwggg.         ",
        "       .gggllw.wl.wldgg.        ",
        "       .gglllw.wl.wlddd.        ",
        "       .gllllwwlwwldddg.        ",
        "      .gglllllllllllggg.        ",
        "      .ggll.gzzzzzg.llgg.       ",
        "     ..l.ggggggggggg.l..        ",
        "    .llll.gyyyyyyyyy.llll.      ",
        "   .llllll.ggyyyyyygg.llllll.    ",
        "   .llllll.gggyyyyggg.llllll.    ",
        "    .llll. gddddddddg .llll.     ",
        "     ..l. .gddddddddg .l..      ",
        "         .gddddddddg            ",
        "         .gggg  gggg.           ",
        "         .ggg.  .ggg.           ",
        "          ..      ..            ",
    ]

    # 6. 🔥 進化分支 B：烈焰星光龍 (火焰與星斗聖龍)
    star = [
        "            ..  ..              ",
        "           .rr..rr.             ",
        "            .......             ",
        "          ..rrrrrrr..           ",
        "         .rrrrllrrrrr.          ",
        "        .rrryywwlwwyyy.         ",
        "       .rrryyw.wl.wyydg.        ",
        "       .rryyyw.wl.wyddd.        ",
        "       .ryyyywwlwwydddy.        ",
        "      .rryyyyyyyyyyryyy.        ",
        "      .rryy.rzzzzzr.yyrr.       ",
        "     ..o.rrrrrrrrrrr.o..        ",
        "    .oooo.ryyyyyyyyy.oooo.      ",
        "   .oooooo.rryyyyyyrr.oooooo.    ",
        "   .oooooo.rrryyyyrrr.oooooo.    ",
        "    .oooo. rddddddddr .oooo.     ",
        "     ..o. .rddddddddr .o..      ",
        "         .rddddddddr            ",
        "         .rrrr  rrrr.           ",
        "         .rrr.  .rrr.           ",
        "          ..      ..            ",
    ]

    # 7. 🐹 進化分支 C：肥嘟嘟守護龍 (搞笑、圓滾球)
    chubby = [
        "                                ",
        "            ........            ",
        "          ..gggggggg..          ",
        "        ..gggggggggggg..        ",
        "       .ggggggllgggggggg.       ",
        "      .ggggggllwwlwwggggg.      ",
        "     .ggggggllw.wl.wldgggg.     ",
        "     .ggggglllw.wl.wlddddgg.    ",
        "     .ggggllllwwlwwlddddddgg.   ",
        "     .gggllllll...ldddddddgg.   ",
        "     .ggglllllllldddddddddgg.   ",
        "     .ggglllllllldddddddddgg.   ",
        "      .ggl.gzzzzzzzzzg.ldgg.    ",
        "      .gg...ggggggggg...dgg.    ",
        "     ..oo..gyyyyyyyyyg..oo..    ",
        "    .oooo.ggyyyyyyyyygg.oooo.   ",
        "    .oooo.gggyyyyyyyggg.oooo.   ",
        "     .oo. gdddddddddddg .oo.    ",
        "          .gdddddddddd.         ",
        "          .gggg   gggg.         ",
        "           .gg.   .gg.          ",
        "            ..     ..           ",
    ]

    # 8. 🍖 寵物乾糧 (Pixel Food)
    feed = [
        "                                ",
        "                                ",
        "                                ",
        "             .....              ",
        "           ..fffff..            ",
        "          .fffffffff.           ",
        "         .ffff.w.ffff.          ",
        "        .ffff.www.ffff.         ",
        "        .ffff.www.ffff.         ",
        "        .fffff.w.fffff.         ",
        "         .ffff...ffff.          ",
        "          .fffffffff.           ",
        "           ..fffff..            ",
        "             .....              ",
    ]

    # 9. 🎩 配件 A：草帽 (Straw Hat)
    straw_hat = [
        "                                ",
        "             ......             ",
        "           ..ffffff..           ",
        "          .ffffffffff.          ",
        "         .ffffffffffff.         ",
        "        .rrrrrrrrrrrrrr.        ",
        "      ..ffffffffffffffff..      ",
        "     .ffffffffffffffffffff.     ",
        "      ....................      ",
    ]

    # 10. 👑 配件 B：皇冠 (Crown)
    crown = [
        "                                ",
        "          .   .  .   .          ",
        "         .k. .k..k. .k.         ",
        "         .k. .k..k. .k.         ",
        "         .kk.kkkkkk.kk.         ",
        "         .kkkkkkkkkkkk.         ",
        "         .kkrkkbkkrkkk.         ",
        "         .kkkkkkkkkkkk.         ",
        "         ..............         ",
    ]

    # 11. 🕶️ 配件 C：墨鏡 (Sunglasses)
    sunglasses = [
        "                                ",
        "       ..................       ",
        "      .ssssssssssssssssss.      ",
        "      .s................s.      ",
        "      .s.eeeeee..eeeeee.s.      ",
        "      .s.eeeeee..eeeeee.s.      ",
        "       .eeeeee.  .eeeeee.       ",
        "        ......    ......        ",
    ]

    # 12. 👿 配件 D：惡魔角 (Devil Horns)
    devil_horns = [
        "      ..            ..          ",
        "     .rr.          .rr.         ",
        "     .rr.          .rr.         ",
        "    .rrr.          .rrr.        ",
        "    .rr.            .rr.        ",
        "   .rr.              .rr.       ",
        "  .rr.                .rr.      ",
        "  ..                    ..      ",
    ]

    # 13. 👼 配件 E：天使翅膀 (Angel Wings)
    angel_wings = [
        "     ...            ...         ",
        "    .www.          .www.        ",
        "   .wwwww.        .wwwww.       ",
        "   .wwwww.        .wwwww.       ",
        "    .www.          .www.        ",
        "     ...            ...         ",
    ]

    output_dir = "static/pet_system/images"
    media_dir = "media/products"

    # 生成主精靈圖 WebP (包含對應 static 與 media 覆蓋)
    create_pixel_sprite(egg, c, os.path.join(output_dir, "pet_egg.webp"))
    create_pixel_sprite(egg, c, os.path.join(media_dir, "pet_egg.webp"))
    
    create_pixel_sprite(baby, c, os.path.join(output_dir, "baby_dragon.webp"))
    create_pixel_sprite(growth, c, os.path.join(output_dir, "growth_dragon.webp"))
    create_pixel_sprite(complete, c, os.path.join(output_dir, "complete_dragon.webp"))
    
    # 三分進化體
    create_pixel_sprite(emerald, c, os.path.join(output_dir, "evolved_dragon.webp")) # 預設翡翠龍
    create_pixel_sprite(emerald, c, os.path.join(output_dir, "pixel_emerald_dragon.webp"))
    create_pixel_sprite(star, c, os.path.join(output_dir, "pixel_star_dragon.webp"))
    create_pixel_sprite(chubby, c, os.path.join(output_dir, "pixel_chubby_dragon.webp"))
    
    # 乾糧
    create_pixel_sprite(feed, c, os.path.join(output_dir, "pet_feed.webp"))
    create_pixel_sprite(feed, c, os.path.join(media_dir, "pet_feed.webp"))
    
    # 配件
    create_pixel_sprite(straw_hat, c, os.path.join(output_dir, "pixel_straw_hat.webp"))
    create_pixel_sprite(crown, c, os.path.join(output_dir, "pixel_crown.webp"))
    create_pixel_sprite(sunglasses, c, os.path.join(output_dir, "pixel_sunglasses.webp"))
    create_pixel_sprite(devil_horns, c, os.path.join(output_dir, "pixel_devil_horns.webp"))
    create_pixel_sprite(angel_wings, c, os.path.join(output_dir, "pixel_angel_wings.webp"))
    
    print("All pixel assets generated successfully!")

if __name__ == "__main__":
    main()
