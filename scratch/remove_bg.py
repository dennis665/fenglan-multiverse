import os
from PIL import Image, ImageChops

def remove_background_and_save_webp(input_path, output_path, tolerance=15):
    # 讀取圖片並轉為 RGBA
    img = Image.open(input_path).convert("RGBA")
    width, height = img.size
    
    # 建立一個與圖片同大小的背景遮罩，預設為 255 (保留)
    mask = Image.new("L", (width, height), 255)
    
    # 使用 PIL 的 floodfill 技術從四個角落進行漫延填充
    # 將與角落顏色相近的背景填為 0 (透明)
    corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    for start_point in corners:
        # 取得起點顏色 (RGB)
        target_color = img.getpixel(start_point)[:3]
        
        # 漫延填充：在 mask 上將相近顏色的區域填為 0
        # 我們自訂漫延填充演算法來處理帶有容差 (tolerance) 的情況
        visited = set()
        queue = [start_point]
        visited.add(start_point)
        
        while queue:
            x, y = queue.pop(0)
            # 檢查目前像素顏色與起點顏色的差異
            curr_color = img.getpixel((x, y))[:3]
            diff = sum(abs(curr_color[i] - target_color[i]) for i in range(3))
            
            if diff <= tolerance * 3:
                mask.putpixel((x, y), 0)
                # 擴展到四鄰域
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append((nx, ny))
                        
    # 將遮罩套用回圖片的 alpha 通道
    r, g, b, a = img.split()
    # 取遮罩與原本 alpha 的最小值
    new_alpha = ImageChops.darker(a, mask)
    final_img = Image.merge("RGBA", (r, g, b, new_alpha))
    
    # 自動裁剪掉周圍的多餘透明邊緣，使寵物主體最大化
    bbox = final_img.getbbox()
    if bbox:
        final_img = final_img.crop(bbox)
        
    # 儲存為 WebP，並使用高品質與失真壓縮以節省流量
    final_img.save(output_path, "WEBP", quality=90)
    print(f"Converted: {os.path.basename(input_path)} -> {os.path.basename(output_path)} (Transparent WebP)")

def main():
    static_img_dir = "static/pet_system/images"
    media_img_dir = "media/products"
    
    # 處理 static 目錄下的圖片
    if os.path.exists(static_img_dir):
        for f in os.listdir(static_img_dir):
            if f.endswith(".jpg") or f.endswith(".jpeg"):
                in_path = os.path.join(static_img_dir, f)
                out_path = os.path.join(static_img_dir, f.rsplit(".", 1)[0] + ".webp")
                remove_background_and_save_webp(in_path, out_path)
                
    # 處理 media 目錄下的圖片
    if os.path.exists(media_img_dir):
        for f in os.listdir(media_img_dir):
            if f.endswith(".jpg") or f.endswith(".jpeg"):
                in_path = os.path.join(media_img_dir, f)
                out_path = os.path.join(media_img_dir, f.rsplit(".", 1)[0] + ".webp")
                remove_background_and_save_webp(in_path, out_path)

if __name__ == "__main__":
    main()
