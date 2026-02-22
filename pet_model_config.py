pet_model_name = "qwen3-vl:8b"
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
Please describe  mind and emotions from the image
Animal  include dog, cat or others

Describe requirements 
MUST Text count limit is 300 words

**the output value language is Traditional	Chinese**
Return JSON format:
```
{
"title": "str",
"describe": "str",
"main_emotion": "str"
}
```
"""