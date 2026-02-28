"""
Pet Adorable Life - 網站主程式
"""
import os
import re

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

import model_connector
import pet_model_config
import db

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB
_secret = os.getenv("SECRET_KEY", "dev-only-insecure-key")
if _secret == "dev-only-insecure-key":
    import warnings
    warnings.warn("SECRET_KEY is not set — using insecure default. Set SECRET_KEY in production.", stacklevel=1)
app.secret_key = _secret

_EXEMPT_ENDPOINTS = {"login", "register", "logout", "static"}


def current_user_id():
    """回傳目前登入使用者的 id，未登入則為 None。"""
    return session.get("user_id")


@app.before_request
def _ensure_db():
    """確保資料表已建立（僅執行一次）。"""
    if not getattr(app, "_db_initialized", False):
        db.init_db()
        app._db_initialized = True


@app.before_request
def _require_login():
    """所有路由都需要登入，例外：login、register、logout、static。"""
    if request.endpoint in _EXEMPT_ENDPOINTS:
        return
    if not current_user_id():
        if request.path.startswith("/api/"):
            return jsonify({"error": "請先登入"}), 401
        return redirect(url_for("login"))


# ========== Auth routes ==========


@app.route("/login", methods=["GET", "POST"])
def login():
    """登入頁面"""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = db.get_user_by_username(username)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("帳號或密碼錯誤")
            return render_template("login.html"), 401
        session["user_id"] = user["id"]
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """註冊頁面"""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not username or len(username) > 100:
            flash("帳號不得為空且長度須在 100 字以內")
            return render_template("register.html"), 400
        if not re.match(r"^\w+$", username):
            flash("帳號只能包含英文字母、數字與底線")
            return render_template("register.html"), 400
        if len(password) < 8:
            flash("密碼長度至少需要 8 個字元")
            return render_template("register.html"), 400
        if password != confirm:
            flash("兩次輸入的密碼不一致")
            return render_template("register.html"), 400
        if db.get_user_by_username(username):
            flash("此帳號已被使用，請選擇其他帳號")
            return render_template("register.html"), 400

        user_id = db.create_user(username, generate_password_hash(password))
        session["user_id"] = user_id
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    """登出"""
    session.pop("user_id", None)
    return redirect(url_for("login"))


# ========== Page routes ==========


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
    return render_template("organize.html")


@app.route("/organize/edit/<int:product_id>")
def organize_edit(product_id):
    """編輯商品頁面"""
    return render_template("organize_edit.html", product_id=product_id)


# ========== Pet diary ==========


@app.route("/diary")
def diary():
    """寵物日記頁面"""
    return render_template("diary.html")


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


# ========== Pets API ==========


@app.route("/api/pets", methods=["GET"])
def api_get_pets():
    """取得所有寵物"""
    return jsonify({"pets": db.get_all_pets(user_id=current_user_id())})


@app.route("/api/pets", methods=["POST"])
def api_add_pet():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "名字不得為空"}), 400
    uid = current_user_id()
    pet_id = db.add_pet(
        name=name,
        breed=(data.get("breed") or "").strip(),
        birthday=data.get("birthday") or None,
        photo_base64=data.get("photo_base64") or "",
        user_id=uid,
    )
    pet = db.get_pet(pet_id, user_id=uid)
    if not pet:
        return jsonify({"error": "寵物建立失敗"}), 500
    return jsonify(pet), 201


@app.route("/api/pets/<int:pet_id>", methods=["GET"])
def api_get_pet(pet_id):
    """取得單一寵物"""
    pet = db.get_pet(pet_id, user_id=current_user_id())
    if not pet:
        return jsonify({"error": "找不到寵物"}), 404
    return jsonify(pet)


@app.route("/api/pets/<int:pet_id>", methods=["PUT"])
def api_update_pet(pet_id):
    """更新寵物資料"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物"}), 404
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "名字不得為空"}), 400
    db.update_pet(
        pet_id=pet_id,
        name=name,
        breed=(data.get("breed") or "").strip(),
        birthday=data.get("birthday") or None,
        photo_base64=data.get("photo_base64"),
        user_id=uid,
    )
    return jsonify(db.get_pet(pet_id, user_id=uid))


@app.route("/api/pets/<int:pet_id>", methods=["DELETE"])
def api_delete_pet(pet_id):
    """刪除寵物"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物"}), 404
    db.remove_pet(pet_id, user_id=uid)
    return "", 204


@app.route("/pets")
def pets_page():
    """寵物管理頁面"""
    return render_template("pets.html")


# ========== Products API ==========


@app.route("/api/products", methods=["GET"])
def api_get_products():
    """取得所有商品"""
    pet_id = request.args.get("pet_id", type=int)
    return jsonify({"products": db.get_all_products(pet_id=pet_id, user_id=current_user_id())})


@app.route("/api/products", methods=["POST"])
def api_add_product():
    """新增商品"""
    uid = current_user_id()
    data = request.get_json() or {}
    title = (data.get("title") or "").strip() or "（未命名）"
    summary = (data.get("summary") or "").strip()
    pet_id = data.get("pet_id") or None
    product_id = db.add_product(title, summary, pet_id=pet_id, user_id=uid)
    product = db.get_product(product_id, user_id=uid)
    if not product:
        return jsonify({"error": "商品建立失敗"}), 500
    return jsonify(product), 201


@app.route("/api/products/<int:product_id>", methods=["GET"])
def api_get_product(product_id):
    """取得單一商品"""
    product = db.get_product(product_id, user_id=current_user_id())
    if not product:
        return jsonify({"error": "找不到商品"}), 404
    return jsonify(product)


@app.route("/api/products/<int:product_id>", methods=["PUT"])
def api_update_product(product_id):
    """更新商品"""
    uid = current_user_id()
    if not db.get_product(product_id, user_id=uid):
        return jsonify({"error": "找不到商品"}), 404
    data = request.get_json() or {}
    title = (data.get("title") or "").strip() or "（未命名）"
    summary = (data.get("summary") or "").strip()
    pet_id = data.get("pet_id") or None
    db.update_product(product_id, title, summary, pet_id=pet_id, user_id=uid)
    return jsonify(db.get_product(product_id, user_id=uid))


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def api_delete_product(product_id):
    """刪除商品"""
    uid = current_user_id()
    if not db.get_product(product_id, user_id=uid):
        return jsonify({"error": "找不到商品"}), 404
    db.remove_product(product_id, user_id=uid)
    return "", 204


@app.route("/api/products", methods=["DELETE"])
def api_delete_products():
    """批次刪除商品"""
    data = request.get_json() or {}
    ids = [int(i) for i in (data.get("ids") or []) if str(i).lstrip("-").isdigit()]
    if ids:
        db.remove_products(ids, user_id=current_user_id())
    return "", 204


# ========== Diaries API ==========


@app.route("/api/diaries", methods=["GET"])
def api_get_diaries():
    """取得所有日記"""
    pet_id = request.args.get("pet_id", type=int)
    return jsonify({"diaries": db.get_all_diaries(pet_id=pet_id, user_id=current_user_id())})


@app.route("/api/diaries", methods=["POST"])
def api_add_diary():
    """新增日記"""
    uid = current_user_id()
    data = request.get_json() or {}
    diary_id = db.add_diary(
        title=(data.get("title") or "").strip(),
        describe_text=(data.get("describe_text") or "").strip(),
        main_emotion=(data.get("main_emotion") or "").strip(),
        memo=(data.get("memo") or "").strip(),
        image_base64=(data.get("image_base64") or ""),
        pet_id=data.get("pet_id") or None,
        user_id=uid,
    )
    diary = db.get_diary(diary_id, user_id=uid)
    if not diary:
        return jsonify({"error": "日記儲存失敗"}), 500
    return jsonify(diary), 201


@app.route("/api/diaries/<int:diary_id>", methods=["DELETE"])
def api_delete_diary(diary_id):
    """刪除單筆日記"""
    uid = current_user_id()
    if not db.get_diary(diary_id, user_id=uid):
        return jsonify({"error": "找不到日記"}), 404
    db.remove_diaries([diary_id], user_id=uid)
    return "", 204


@app.route("/api/diaries", methods=["DELETE"])
def api_delete_diaries():
    """批次刪除日記"""
    data = request.get_json() or {}
    ids = [int(i) for i in (data.get("ids") or []) if str(i).lstrip("-").isdigit()]
    if ids:
        db.remove_diaries(ids, user_id=current_user_id())
    return "", 204


def _get_watch_files():
    """收集需監聽的 .py 與 .html 檔案，變更時觸發重啟。"""
    root = os.path.dirname(os.path.abspath(__file__))
    watch_ext = (".py", ".html")
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        if any(skip in dirpath for skip in ("__pycache__", ".git", "venv", ".venv", "node_modules", ".history")):
            continue
        for name in filenames:
            if name.lower().endswith(watch_ext):
                files.append(os.path.join(dirpath, name))
    return files


if __name__ == "__main__":
    extra_files = _get_watch_files()
    app.run(host="0.0.0.0", debug=True, port=5001, extra_files=extra_files)
