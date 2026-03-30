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
MUST Text count limit is 300 words

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