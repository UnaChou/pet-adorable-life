"""
Pet Adorable Life - 網站主程式
"""
import os

from flask import Flask, render_template, request, jsonify, redirect, url_for

import model_connector
import pet_model_config
import db

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB
app.secret_key = "pet-adorable-life-secret-key-change-in-production"


@app.before_request
def _ensure_db():
    """確保資料表已建立（僅執行一次）。"""
    if not getattr(app, "_db_initialized", False):
        db.init_db()
        app._db_initialized = True


@app.route("/")
def index():
    """導覽／首頁"""
    return render_template("index.html")


@app.route("/product/analyze")
def product_analyze_page():
    """商品分析頁面"""
    return render_template("product_analyze.html")


@app.route("/api/product/analyze", methods=["POST"])
def api_product_analyze():
    """上傳商品圖片並回傳 AI 分析結果"""
    if "image" not in request.files:
        return jsonify({"error": "未上傳圖片"}), 400
    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "未選擇檔案"}), 400
    allowed = {"png", "jpg", "jpeg", "webp", "gif"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed:
        return jsonify({"error": f"不支援的格式，請使用: {', '.join(allowed)}"}), 400

    model_name = getattr(pet_model_config, "pet_model_name", "qwen3-vl:4b")
    result = model_connector.get_model_response_by_image(model_name, file)
    if result is None:
        return jsonify({"error": "分析失敗，請確認 Ollama 服務是否運行", "_raw": ""}), 500
    if result.get("error"):
        return jsonify(result), 500
    return jsonify(result)


@app.route("/organize")
def organize():
    """資訊整理頁面"""
    products = db.get_all_products()
    diaries = db.get_all_diaries()
    return render_template("organize.html", products=products, diaries=diaries)


@app.route("/organize/add", methods=["POST"])
def organize_add():
    """新增商品到資訊整理"""
    title = (request.form.get("title") or "").strip()
    summary = (request.form.get("summary") or "").strip()
    if title or summary:
        db.add_product(title or "（未命名）", summary)
    return redirect(url_for("organize"))


@app.route("/organize/edit/<int:product_id>")
def organize_edit(product_id):
    """編輯商品頁面"""
    product = db.get_product(product_id)
    if not product:
        return redirect(url_for("organize"))
    return render_template("organize_edit.html", product=product)


@app.route("/organize/update/<int:product_id>", methods=["POST"])
def organize_update(product_id):
    """更新商品並寫入 MySQL"""
    product = db.get_product(product_id)
    if not product:
        return redirect(url_for("organize"))
    title = (request.form.get("title") or "").strip()
    summary = (request.form.get("summary") or "").strip()
    db.update_product(product_id, title or "（未命名）", summary)
    return redirect(url_for("organize"))


@app.route("/organize/remove/<int:product_id>", methods=["POST"])
def organize_remove(product_id):
    """從資訊整理移除單一商品"""
    db.remove_product(product_id)
    return redirect(url_for("organize"))


@app.route("/organize/remove/batch", methods=["POST"])
def organize_remove_batch():
    """批次刪除勾選的商品"""
    ids = request.form.getlist("product_ids", type=int)
    if ids:
        db.remove_products(ids)
    return redirect(url_for("organize"))


# ========== Pet diary ==========


@app.route("/diary")
def diary():
    """寵物日記頁面"""
    diaries = db.get_all_diaries()
    return render_template("diary.html", diaries=diaries)


@app.route("/api/diary/analyze", methods=["POST"])
def api_diary_analyze():
    """上傳圖片並以 image_context_prompt 分析"""
    try:
        if "image" not in request.files:
            return jsonify({"error": "未上傳圖片"}), 400
        file = request.files["image"]
        if file.filename == "":
            return jsonify({"error": "未選擇檔案"}), 400
        allowed = {"png", "jpg", "jpeg", "webp", "gif"}
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in allowed:
            return jsonify({"error": f"不支援的格式，請使用: {', '.join(allowed)}"}), 400

        model_name = getattr(pet_model_config, "pet_model_name", "qwen3-vl:4b")
        result = model_connector.get_diary_response_by_image(model_name, file)
        if result is None:
            return jsonify({"error": "分析失敗，請確認 Ollama 服務是否運行"}), 500
        if result.get("error"):
            return jsonify(result), 500
        return jsonify({
            "title": result.get("title", ""),
            "describe": result.get("describe", ""),
            "main_emotion": result.get("main_emotion", ""),
        })
    except Exception as e:
        return jsonify({"error": f"伺服器錯誤：{str(e)}"}), 500


@app.route("/diary/save", methods=["POST"])
def diary_save():
    """儲存日記到 MySQL"""
    title = (request.form.get("title") or "").strip()
    describe_text = (request.form.get("describe_text") or "").strip()
    main_emotion = (request.form.get("main_emotion") or "").strip()
    memo = (request.form.get("memo") or "").strip()
    image_base64 = (request.form.get("image_base64") or "").strip()
    db.add_diary(title, describe_text, main_emotion, memo, image_base64)
    return redirect(url_for("organize", tab="diaries"))


@app.route("/diary/remove/batch", methods=["POST"])
def diary_remove_batch():
    """批次刪除勾選的日記"""
    ids = request.form.getlist("diary_ids", type=int)
    if ids:
        db.remove_diaries(ids)
    return redirect(url_for("diary"))


def _get_watch_files():
    """收集需監聽的 .py 與 .html 檔案，變更時觸發重啟。"""
    root = os.path.dirname(os.path.abspath(__file__))
    watch_ext = (".py", ".html")
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        # 略過 __pycache__、.git、venv 等目錄
        if any(skip in dirpath for skip in ("__pycache__", ".git", "venv", ".venv", "node_modules", ".history")):
            continue
        for name in filenames:
            if name.lower().endswith(watch_ext):
                files.append(os.path.join(dirpath, name))
    return files


if __name__ == "__main__":
    extra_files = _get_watch_files()
    app.run(host="0.0.0.0", debug=True, port=5001, extra_files=extra_files)
