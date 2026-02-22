import requests
import json
import base64
import os
import re
import time
from typing import Any, Dict, Optional, Union

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import pet_model_config

# url = "http://127.0.0.1:11434/api/generate"
url = "http://192.168.50.11:11434/api/generate"
# http://192.168.50.11:11434

def _call_model_with_retry(data: Dict[str, Any], parse_response: bool = False) -> Optional[Dict[str, Any]]:
    """
    Call the model API with retry logic for handling transient failures.
    Only returns result if status code is 200 and response contains valid JSON.
    
    Args:
        data: The request payload to send to the model API
        parse_response: If True, also parse the 'response' field as JSON (for image analysis)
    """
    @retry(
        stop=stop_after_attempt(0),
        wait=wait_exponential(multiplier=1, min=1, max=2),
        retry=retry_if_exception_type((requests.exceptions.RequestException, ValueError))
    )
    def _make_request():
        response = requests.post(url, json=data)
        if response.status_code != 200:
            raise requests.exceptions.RequestException(
                f"Model API failed with status {response.status_code}: {response.text}"
            )
        
        try:
            json_response = response.json()
            if not isinstance(json_response, dict):
                raise ValueError("Response is not a valid JSON object")
            
            if parse_response:
                raw = json_response.get("response", "").strip()
                if not raw:
                    raise ValueError("Model did not return content in response")
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    to_parse = _extract_json_by_regex(raw)
                    parsed = json.loads(to_parse)
                if isinstance(parsed, dict):
                    return parsed
                raise ValueError("Response is not a valid JSON object")
            
            return json_response
        except Exception as e:
            parsed = response.json()
            if isinstance(parsed, dict):
                raw = parsed.get("response", "").strip()
                if not raw:
                    raise ValueError("Model did not return content in response")
                try:
                    inner_parsed = json.loads(raw)
                except json.JSONDecodeError:
                    to_parse_inner = _extract_json_by_regex(raw)
                    inner_parsed = json.loads(to_parse_inner)
                if isinstance(inner_parsed, dict):
                    return inner_parsed
                raise ValueError("Response is not a valid JSON object")

            raise ValueError("Response is not a valid JSON object")

    try:
        return _make_request()
    except requests.exceptions.RequestException as e:
        print(f"Model API request failed after retries: {e}")
        return None
    except ValueError as e:
        print(f"Model API response parsing failed: {e}")
        return None

def get_model_response(model: str, prompt: str) -> Optional[str]:
    """
    Get text response from the model with retry logic.
    """
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    result = _call_model_with_retry(data)
    if result and 'response' in result:
        print(result['response'])
        return result['response']
    return None


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

def _extract_json_by_regex(text):
    """使用正則表達式從文字中擷取 JSON 物件"""
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def _get_image_base64(image_source):
    """將圖片來源轉為 base64。image_source 可為：檔案路徑(str)、bytes、或具 read() 的檔案物件。"""
    if isinstance(image_source, (bytes, bytearray)):
        return base64.b64encode(image_source).decode("utf-8")
    if hasattr(image_source, "read"):
        return base64.b64encode(image_source.read()).decode("utf-8")
    return encode_image_to_base64(image_source)


def get_model_response_by_image(model: str, image_source: Union[str, bytes, Any], prompt: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    分析圖片，回傳 AI 產生的 JSON。prompt 預設為 product_prompt。
    
    Returns:
        - dict: 解析成功的 JSON 結果
        - None: API 呼叫失敗
        - dict: 包含錯誤資訊的結構化錯誤回應
    """
    image_base64 = _get_image_base64(image_source)
    prompt = prompt or pet_model_config.product_prompt

    data = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False
    }

    result = _call_model_with_retry(data, parse_response=True)
    if not result:
        return None
    
    if isinstance(result, dict):
        return result
    
    return {"title": "解析失敗", "describe": str(result)}


def get_diary_response_by_image(model: str, image_source: Union[str, bytes, Any]) -> Optional[Dict[str, Any]]:
    """
    分析寵物圖片，使用 image_context_prompt，回傳 describe 與 main_emotion。
    """
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

