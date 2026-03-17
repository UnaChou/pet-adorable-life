"""
Pet Adorable Life - 網站主程式
"""
import hashlib
import logging
import os
import re
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash

import model_connector
import pet_model_config
import db

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB
logger = logging.getLogger(__name__)


def _env_truthy(name: str, default: str = "false") -> bool:
    return (os.getenv(name, default) or "").strip().lower() in ("1", "true", "yes", "on")


_DEBUG_MODE = _env_truthy("FLASK_DEBUG", "false")

_secret = (os.getenv("SECRET_KEY") or "").strip()

if (not _secret) or (_secret == "dev-only-insecure-key"):
    import warnings
    warnings.warn(
        "SECRET_KEY is not set — using insecure default. Set SECRET_KEY in production.",
        stacklevel=1,
    )
    if not _DEBUG_MODE:
        raise RuntimeError(
            "SECRET_KEY is required when FLASK_DEBUG is false (production mode)."
        )
    _secret = "dev-only-insecure-key"

app.secret_key = _secret

app.config.update(
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
    MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "true").lower() == "true",
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER"),
)
mail = Mail(app)

_EXEMPT_ENDPOINTS = {"login", "register", "logout", "static", "forgot_password", "reset_password"}

_RESET_WINDOW_SECONDS = 300
_RESET_MAX_REQUESTS_PER_IP = 10
_reset_attempts_by_ip = defaultdict(deque)
_reset_attempts_lock = Lock()


def _utcnow_naive() -> datetime:
    """回傳 UTC 現在時間（naive，與 MySQL DATETIME 對齊）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _form_csrf_key(form_name: str) -> str:
    return f"csrf_{form_name}"


def _issue_csrf_token(form_name: str) -> str:
    token = secrets.token_urlsafe(32)
    session[_form_csrf_key(form_name)] = token
    return token


def _validate_csrf_token(form_name: str) -> bool:
    submitted = (request.form.get("csrf_token") or "").strip()
    expected = session.pop(_form_csrf_key(form_name), None)
    return bool(submitted and expected and secrets.compare_digest(submitted, expected))


def _is_forgot_password_rate_limited(remote_addr: str) -> bool:
    now_ts = _utcnow_naive().timestamp()
    with _reset_attempts_lock:
        bucket = _reset_attempts_by_ip[remote_addr]
        while bucket and now_ts - bucket[0] > _RESET_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= _RESET_MAX_REQUESTS_PER_IP:
            return True
        bucket.append(now_ts)
        return False


def current_user_id():
    """回傳目前登入使用者的 id，未登入則為 None。"""
    return session.get("user_id")

_ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "gif"}


def _validate_image_file(file):
    """回傳 (None, None) 表示驗證通過；否則回傳 (error_response, status_code)。"""
    if file.filename == "":
        return jsonify({"error": "未選擇檔案"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in _ALLOWED_IMAGE_EXTS:
        return jsonify({"error": f"不支援的格式，請使用: {', '.join(_ALLOWED_IMAGE_EXTS)}"}), 400
    return None, None


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
        if not _validate_csrf_token("login"):
            flash("表單已失效，請再試一次")
            return render_template("login.html", csrf_token=_issue_csrf_token("login")), 400

        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = db.get_user_by_username(username)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("帳號或密碼錯誤")
            return render_template("login.html", csrf_token=_issue_csrf_token("login")), 401
        session["user_id"] = user["id"]
        return redirect(url_for("index"))
    return render_template("login.html", csrf_token=_issue_csrf_token("login"))


_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
_RESET_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def _is_valid_email(email: str) -> bool:
    return bool(email and _EMAIL_RE.fullmatch(email))


def _validate_register_inputs(username: str, email: str, password: str, confirm: str):
    if not username or len(username) > 100:
        return "帳號不得為空且長度須在 100 字以內"
    if not re.match(r"^\w+$", username):
        return "帳號只能包含英文字母、數字與底線"
    if not _is_valid_email(email):
        return "請輸入有效的電子信箱"
    if len(password) < 8:
        return "密碼長度至少需要 8 個字元"
    if password != confirm:
        return "兩次輸入的密碼不一致"
    return None


def _validate_register_uniqueness(username: str, email: str):
    if db.get_user_by_username(username):
        return "此帳號已被使用，請選擇其他帳號"
    if db.get_user_by_email(email):
        return "此電子信箱已被使用"
    return None


@app.route("/register", methods=["GET", "POST"])
def register():
    """註冊頁面"""
    if request.method == "POST":
        if not _validate_csrf_token("register"):
            flash("表單已失效，請再試一次")
            return render_template("register.html", csrf_token=_issue_csrf_token("register")), 400

        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        input_error = _validate_register_inputs(username, email, password, confirm)
        if input_error:
            flash(input_error)
            return render_template("register.html", csrf_token=_issue_csrf_token("register")), 400

        uniqueness_error = _validate_register_uniqueness(username, email)
        if uniqueness_error:
            flash(uniqueness_error)
            return render_template("register.html", csrf_token=_issue_csrf_token("register")), 400

        user_id = db.create_user(username, email, generate_password_hash(password))
        session["user_id"] = user_id
        return redirect(url_for("index"))
    return render_template("register.html", csrf_token=_issue_csrf_token("register"))


@app.route("/logout")
def logout():
    """登出"""
    session.pop("user_id", None)
    return redirect(url_for("login"))


# ========== Password reset ==========


def _validate_reset_token(token):
    """驗證重設 token，回傳 (record, error_msg)。record 為 None 表示無效。"""
    if not _RESET_TOKEN_RE.fullmatch(token or ""):
        return None, "連結無效或已過期"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    record = db.get_reset_token(token_hash)
    if not record:
        return None, "連結無效或已過期"
    if record["used_at"] is not None:
        return None, "此連結已使用，請重新申請"
    if record["expires_at"] < _utcnow_naive():
        return None, "連結已過期，請重新申請"
    return record, None


def _send_password_reset_email(email: str, user_id: int, reset_url: str) -> None:
    msg = Message(
        "重設您的密碼 - Pet Adorable Life",
        recipients=[email],
    )
    msg.body = (
        f"您好，\n\n請點擊以下連結重設密碼（1小時內有效）：\n\n{reset_url}\n\n"
        "若非您本人操作，請忽略此信。"
    )
    try:
        mail.send(msg)
    except Exception:
        logger.warning(
            "Failed to send password reset email (user_id=%s).",
            user_id,
            exc_info=True,
        )


def _request_password_reset(email: str) -> None:
    user = db.get_user_by_email(email)
    if not user:
        return
    if db.count_recent_reset_requests(user["id"], since_minutes=60) >= 3:
        return
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = _utcnow_naive() + timedelta(hours=1)
    db.create_reset_token(user["id"], token_hash, expires_at)
    reset_url = url_for("reset_password", token=raw_token, _external=True)
    _send_password_reset_email(email=email, user_id=user["id"], reset_url=reset_url)


def _render_reset_password(token: str, error=None, status_code=None):
    response = render_template(
        "reset_password.html",
        token=token,
        error=error,
        csrf_token=_issue_csrf_token("reset_password"),
    )
    if status_code is None:
        return response
    return response, status_code


def _validate_reset_form_passwords(new_password: str, confirm: str):
    if len(new_password) < 8:
        return "密碼長度至少需要 8 個字元"
    if new_password != confirm:
        return "兩次輸入的密碼不一致"
    return None


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """忘記密碼頁面：輸入 email 申請重設連結"""
    if request.method == "POST":
        if not _validate_csrf_token("forgot_password"):
            flash("表單已失效，請再試一次")
            return render_template(
                "forgot_password.html",
                csrf_token=_issue_csrf_token("forgot_password"),
            ), 400

        remote_addr = (request.remote_addr or "unknown").strip() or "unknown"
        if _is_forgot_password_rate_limited(remote_addr):
            flash("操作過於頻繁，請稍後再試。")
            return redirect(url_for("forgot_password"))

        email = (request.form.get("email") or "").strip().lower()
        if _is_valid_email(email):
            _request_password_reset(email)
        flash("若此信箱已註冊，您將收到重設連結，請檢查您的信箱。")
        return redirect(url_for("forgot_password"))
    return render_template(
        "forgot_password.html",
        csrf_token=_issue_csrf_token("forgot_password"),
    )


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """密碼重設頁面：憑 token 設定新密碼"""
    record, error = _validate_reset_token(token)
    if request.method == "POST":
        if not _validate_csrf_token("reset_password"):
            flash("表單已失效，請再試一次")
            return _render_reset_password(token=token, error=error, status_code=400)

        if error:
            flash(error)
            return _render_reset_password(token=token, error=error, status_code=400)

        if record is None:
            flash("連結無效或已過期")
            return _render_reset_password(token=token, error="連結無效或已過期", status_code=400)

        new_password = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        form_error = _validate_reset_form_passwords(new_password, confirm)
        if form_error:
            flash(form_error)
            return _render_reset_password(token=token, status_code=400)

        db.invalidate_user_reset_tokens(record["user_id"])
        db.mark_reset_token_used(record["id"])
        db.update_user_password(record["user_id"], generate_password_hash(new_password))
        session.clear()
        flash("密碼已重設，請用新密碼登入。")
        return redirect(url_for("login"))
    return _render_reset_password(token=token, error=error)


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
    err, status = _validate_image_file(file)
    if err:
        return err, status

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
        err, status = _validate_image_file(file)
        if err:
            return err, status

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
    app.run(host="0.0.0.0", debug=_DEBUG_MODE, port=5001, extra_files=extra_files)
