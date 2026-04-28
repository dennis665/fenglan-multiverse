import os
import sys

import torch
import torchvision.transforms as T
from django.conf import settings
from PIL import Image, ImageDraw

#! 設定 rtdetrv2_pytorch 的絕對路徑並加入系統環境，避免 module not found
project_root = settings.BASE_DIR
rtdetr_path = os.path.join(
    project_root, "sh_recognition", "rtdetrv2_pytorch"
)  # * 已更新為 sh_recognition 目錄下
if rtdetr_path not in sys.path:
    sys.path.insert(0, rtdetr_path)

from src.core import YAMLConfig  # * 引入模型設定檔  # noqa: E402


def run_image_inference(image_path, model_path, output_dir, threshold=0.5):
    #! 執行圖片辨識流程，並回傳結果圖片路徑、文字結果與是否有辨識到物體

    #! 步驟 1：載入設定與權重檔
    config_path = os.path.join(rtdetr_path, "configs", "custom", "rtdetrv2_m.yml")
    cfg = YAMLConfig(config_path, resume=model_path)

    checkpoint = torch.load(model_path, map_location="cpu")
    if "ema" in checkpoint:
        state = checkpoint["ema"]["module"]
    else:
        state = checkpoint["model"]
    cfg.model.load_state_dict(state)

    #! 步驟 2：初始化模型與後處理，強制使用 CPU
    model = cfg.model.deploy()  # pyright: ignore[reportCallIssue]
    postprocessor = cfg.postprocessor.deploy()  # pyright: ignore[reportCallIssue]
    device = torch.device("cpu")

    model.to(device)
    postprocessor.to(device)
    model.eval()

    #! 步驟 3：圖片前處理 (Transforms)
    transforms = T.Compose(
        [
            T.Resize((640, 640)),
            T.ToTensor(),
        ]
    )

    im_pil = Image.open(image_path).convert("RGB")
    w, h = im_pil.size
    orig_size = torch.tensor([[w, h]]).to(device)
    im_data = transforms(im_pil).unsqueeze(0).to(device)  # pyright: ignore[reportAttributeAccessIssue]

    #! 步驟 4：執行神經網路推論
    with torch.no_grad():
        output = model(im_data)
        labels, boxes, scores = postprocessor(output, orig_size)

    #! 步驟 5：繪製結果 (Bounding Box) 與紀錄偵測狀態
    draw = ImageDraw.Draw(im_pil)
    scr = scores[0]
    lab = labels[0]
    box = boxes[0]

    results_txt = []
    has_object = False  # * 預設為未偵測到物體

    for i in range(len(scr)):
        score = scr[i].item()
        if score >= threshold:  # * 預設信心度門檻
            has_object = True  # * 若有分數大於閥值，則標記為有偵測到
            label = int(lab[i].item())
            b = box[i].tolist()
            draw.rectangle(b, outline="red", width=3)

            text = f"Cls {label}: {score:.2f}"
            draw.text((b[0], b[1]), text, fill="red")

            #! 格式化文字紀錄：類別 xmin ymin xmax ymax
            coords = " ".join([f"{x:.2f}" for x in b])
            results_txt.append(f"{label} {coords}")

    #! 步驟 6：儲存結果圖片到 media 輸出路徑
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(image_path)
    result_image_path = os.path.join(output_dir, f"res_{filename}")
    im_pil.save(result_image_path)

    #! 步驟 7：回傳絕對路徑、文字紀錄與是否偵測到物體
    return result_image_path, "\n".join(results_txt), has_object
