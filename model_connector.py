import requests
import json
import base64
import os

import pet_model_config

# url = "http://127.0.0.1:11434/api/generate"
url = "http://192.168.50.11:11434/api/generate"
# http://192.168.50.11:11434


def get_model_response(model, prompt):
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False 
    }

    response = requests.post(url, json=data)

    if response.status_code == 200:
        result = response.json()
        print(result['response'])
    else:
        print("Error:", response.status_code, response.text)

def encode_image_to_base64(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"找不到圖片: {image_path}")
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def _extract_json_object(text):
    """從文字中擷取第一個完整的 JSON 物件，考慮字串內的括號。"""
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    i = start
    in_str = False
    str_char = None
    escape = False
    while i < len(text):
        c = text[i]
        if escape:
            escape = False
            i += 1
            continue
        if in_str:
            if c == str_char:
                in_str = False
            elif c == "\\":
                escape = True
            i += 1
            continue
        if c in '"\'':
            in_str = True
            str_char = c
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1
    return text[start:]


def _get_image_base64(image_source):
    """將圖片來源轉為 base64。image_source 可為：檔案路徑(str)、bytes、或具 read() 的檔案物件。"""
    if isinstance(image_source, (bytes, bytearray)):
        return base64.b64encode(image_source).decode("utf-8")
    if hasattr(image_source, "read"):
        return base64.b64encode(image_source.read()).decode("utf-8")
    return encode_image_to_base64(image_source)


def get_model_response_by_image(model, image_source, prompt=None):
    """分析圖片，回傳 AI 產生的 JSON。prompt 預設為 product_prompt。"""
    image_base64 = _get_image_base64(image_source)
    prompt = prompt or pet_model_config.product_prompt

    data = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False
    }

    response = requests.post(url, json=data)

    if response.status_code == 200:
        result = response.json()
        raw = result.get("response", "").strip()
        if not raw:
            return {"title": "解析失敗, 模型未回傳內容", "describe": ""}

        to_parse = _extract_json_object(raw)

        try:
            parsed = json.loads(to_parse)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {"title": "解析失敗", "describe": raw}
    return None


def get_diary_response_by_image(model, image_source):
    """分析寵物圖片，使用 image_context_prompt，回傳 describe 與 main_emotion。"""
    prompt = getattr(pet_model_config, "image_context_prompt", None)

    if not prompt:
        prompt = """
Please describe mind and emotions from the image.
Animal include dog, cat or others.
MUST Text count limit is 300 words.
**the output value language is Traditional Chinese**
Return JSON format: {"title": "str", "describe": "str", "main_emotion": "str"}
"""
    return get_model_response_by_image(model, image_source, prompt)

