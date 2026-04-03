pet_model_name = "qwen3.5:9b"
# pet_model_name = "gemma3:27b"

product_prompt = """
請取得商品 title name 和 summary，內容使用繁體中文，如果為圖片擷取的文字，與圖片相同

**summary requirement **
MUST Text count limit is 300 words
Include main description and 5 features point

Format : 
\"\"\"
{{main description}}

- Point1
- Point2 
\"\"\"

**the output value language is Traditional	Chinese**
Return JSON format:
```
{
"title": "str",
"summary": "str"
}
```
"""

image_context_prompt = """
You are a famous novelist,your task is write description which is like a diary, describe animal's mind and emotions from the image.
animal include dog, cat or others.

description requirements 
**MUST Text count limit is 500 words**

**the output value language is Traditional Chinese**
Return JSON format:
```
{
"title": "str",
"description": "str",
"main_emotion": "str"
}
```
"""


def build_image_prompt(user_prompt: str) -> str:
    cleaned_prompt = (user_prompt or "").strip()
    return f"""
你會收到一張圖片與一段使用者指令。
請根據圖片內容，嚴格依照使用者要求回答。

使用者指令：
{cleaned_prompt}

回覆規則：
1. 若使用者沒有指定語言，請使用繁體中文。
2. 只回傳 JSON，不要加入 markdown、註解、前言或額外說明。
3. JSON 格式固定如下：
{{
  "result": "string"
}}
4. result 需為單一字串；若需要條列，請將條列內容放在字串內。
5. 若圖片資訊不足，請根據可見內容誠實回答，不要捏造看不見的細節。
"""
