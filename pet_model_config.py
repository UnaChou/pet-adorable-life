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


medical_record_prompt = """
你會收到一張寵物醫療相關的圖片（如處方箋、診斷報告、傷口照片、藥品照片等）。
請從圖片中擷取重要的醫療資訊，用繁體中文回答。

回覆規則：
1. 只回傳 JSON，不要加入 markdown、註解、前言或額外說明。
2. JSON 格式固定如下：
{
  "title": "簡短標題（如：感冒就診、皮膚治療）",
  "description": "詳細描述醫療內容（包含診斷、用藥、注意事項等可見資訊）"
}
3. 若圖片資訊不足，請根據可見內容誠實回答，不要捏造看不見的細節。
4. description 字數限制 300 字以內。
"""


medical_summary_prompt = """
你是一位寵物醫療紀錄整理助手。
請根據以下寵物醫療紀錄列表，統整出一份摘要大綱。

輸入格式為多筆紀錄，每筆包含 title、description、occurred_date。

回覆規則：
1. 使用繁體中文。
2. 按時間由近到遠排序（最近的在最前面）。
3. 每筆紀錄以標題 + 日期為小標，下方簡述重點。
4. 在最開頭加上一段整體摘要（100字以內），說明這段時間的醫療概況。
5. 只回傳純文字，不要 JSON、不要 markdown。
6. 格式範例：

整體摘要：近期寵物因皮膚問題就診兩次，目前已穩定治療中。

【2024/03/15 皮膚回診】
- 皮膚紅腫已明顯改善
- 繼續使用外用藥膏一週

【2024/03/01 皮膚初診】
- 左前腳出現紅腫脫毛
- 開立抗過敏藥物與外用藥膏
"""
