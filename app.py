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

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, make_response
from flask.typing import ResponseReturnValue
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash

import model_connector
import pet_model_config
import db

_LOG_LEVEL = getattr(logging, (os.getenv("LOG_LEVEL") or "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

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
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_USERNAME"),
)
mail = Mail(app)

_EXEMPT_ENDPOINTS = {"login", "register", "logout", "static", "forgot_password", "reset_password"}

_RESET_WINDOW_SECONDS = 300
_RESET_MAX_REQUESTS_PER_IP = 10
_PASSWORD_RESET_ACCEPTED_MESSAGE = (
    "若此信箱已註冊且系統信件設定正常，您將收到重設連結；"
    "若沒有收到，請檢查垃圾郵件或聯絡管理員。"
)
_PASSWORD_RESET_MAIL_CONFIG_MESSAGE = "系統信件設定未完成，暫時無法寄送重設連結，請聯絡管理員。"
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
    if not submitted and request.is_json:
        payload = request.get_json(silent=True) or {}
        submitted = (payload.get("csrf_token") or "").strip()
    expected = session.pop(_form_csrf_key(form_name), None)
    return bool(submitted and expected and secrets.compare_digest(submitted, expected))


def _no_cache_response(html, status_code=200):
    resp = make_response(html, status_code)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


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
    if request.path == "/favicon.ico":
        return
    if not current_user_id():
        if request.path.startswith("/api/"):
            return jsonify({"error": "請先登入"}), 401
        return redirect(url_for("login", next=request.path))


# ========== Auth routes ==========


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not _validate_csrf_token("login"):
            fresh_csrf_token = _issue_csrf_token("login")
            if request.is_json:
                return jsonify({"error": "表單已失效，請再試一次", "csrf_token": fresh_csrf_token}), 400
            flash("表單已失效，請再試一次")
            return _no_cache_response(render_template("login.html", csrf_token=fresh_csrf_token), 400)

        payload = request.get_json(silent=True) if request.is_json else None
        username = ((payload or {}).get("username") or request.form.get("username") or "").strip()
        password = (payload or {}).get("password") or request.form.get("password") or ""
        user = db.get_user_by_username(username)
        if not user or not check_password_hash(user["password_hash"], password):
            fresh_csrf_token = _issue_csrf_token("login")
            if request.is_json:
                return jsonify({"error": "帳號或密碼錯誤", "csrf_token": fresh_csrf_token}), 401
            flash("帳號或密碼錯誤")
            return _no_cache_response(render_template("login.html", csrf_token=fresh_csrf_token), 401)
        session["user_id"] = user["id"]
        next_url = (
            (payload or {}).get("next") or request.form.get("next") or request.args.get("next") or ""
        ).strip()
        # Only allow local paths to prevent open redirect
        if not (next_url.startswith("/") and not next_url.startswith("//")):
            next_url = url_for("index")
        if request.is_json:
            return jsonify({"ok": True, "redirect_to": next_url or url_for("index")})
        return redirect(next_url or url_for("index"))
    return _no_cache_response(render_template("login.html", csrf_token=_issue_csrf_token("login")))


_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
_RESET_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def _is_valid_email(email: str) -> bool:
    return bool(email and _EMAIL_RE.fullmatch(email))


def _mask_email(email: str) -> str:
    local, sep, domain = (email or "").partition("@")
    if not sep:
        return "<invalid>"
    if len(local) <= 1:
        masked_local = "*"
    else:
        masked_local = f"{local[0]}***"
    return f"{masked_local}@{domain}"


def _missing_mail_settings() -> list[str]:
    required = ("MAIL_SERVER", "MAIL_PORT", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_DEFAULT_SENDER")
    return [name for name in required if not str(app.config.get(name) or "").strip()]


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
    if request.method == "POST":
        next_url = (request.form.get("next") or "").strip()
        if not (next_url.startswith("/") and not next_url.startswith("//")):
            next_url = ""

        if not _validate_csrf_token("register"):
            flash("表單已失效，請再試一次")
            return _no_cache_response(render_template("register.html", csrf_token=_issue_csrf_token("register"), next=next_url), 400)

        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        input_error = _validate_register_inputs(username, email, password, confirm)
        if input_error:
            flash(input_error)
            return _no_cache_response(render_template("register.html", csrf_token=_issue_csrf_token("register"), next=next_url), 400)

        uniqueness_error = _validate_register_uniqueness(username, email)
        if uniqueness_error:
            flash(uniqueness_error)
            return _no_cache_response(render_template("register.html", csrf_token=_issue_csrf_token("register"), next=next_url), 400)

        user_id = db.create_user(username, email, generate_password_hash(password))
        session["user_id"] = user_id
        return redirect(next_url or url_for("index"))
    next_url = request.args.get("next", "").strip()
    if not (next_url.startswith("/") and not next_url.startswith("//")):
        next_url = ""
    return _no_cache_response(render_template("register.html", csrf_token=_issue_csrf_token("register"), next=next_url))


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


def _send_password_reset_email(email: str, user_id: int, reset_url: str) -> bool:
    missing_settings = _missing_mail_settings()
    if missing_settings:
        logger.error(
            "Password reset email not sent because mail settings are missing (user_id=%s, recipient=%s, missing=%s).",
            user_id,
            _mask_email(email),
            ",".join(missing_settings),
        )
        return False

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
        logger.info(
            "Password reset email sent (user_id=%s, recipient=%s).",
            user_id,
            _mask_email(email),
        )
        return True
    except Exception:
        logger.exception(
            "Failed to send password reset email (user_id=%s, recipient=%s).",
            user_id,
            _mask_email(email),
        )
        return False


_ROLE_DISPLAY = {"read_only": "僅能檢視", "editor": "可編輯"}


def _send_pet_invite_email(invitee_email: str, inviter_username: str, pet_name: str,
                           role: str, join_url: str, inviter_user_id: int) -> bool:
    role_display = _ROLE_DISPLAY.get(role, role)
    msg = Message(
        f"{inviter_username} 邀請您加入共同飼養 {pet_name}！- Pet Adorable Life",
        recipients=[invitee_email],
    )
    msg.body = (
        f"您好，\n\n{inviter_username} 邀請您以「{role_display}」身份共同飼養 {pet_name}。\n\n"
        f"點擊以下連結加入（連結在 7 天後失效）：\n\n{join_url}\n\n"
        "若非您本人操作，請忽略此信。"
    )
    try:
        mail.send(msg)
        return True
    except Exception:
        logger.warning(
            "Failed to send pet invite email (inviter_user_id=%s).",
            inviter_user_id,
            exc_info=True,
        )
        return False


def _request_password_reset(email: str) -> str:
    user = db.get_user_by_email(email)
    if not user:
        logger.info("Password reset requested for unknown email (recipient=%s).", _mask_email(email))
        return "unknown_email"
    if db.count_recent_reset_requests(user["id"], since_minutes=60) >= 3:
        logger.warning("Password reset request blocked by per-user limit (user_id=%s).", user["id"])
        return "user_rate_limited"
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = _utcnow_naive() + timedelta(hours=1)
    db.create_reset_token(user["id"], token_hash, expires_at)
    reset_url = url_for("reset_password", token=raw_token, _external=True)
    if not _send_password_reset_email(email=email, user_id=user["id"], reset_url=reset_url):
        return "send_failed"
    return "sent"


def _render_reset_password(token: str, error=None, status_code=None):
    response = render_template(
        "reset_password.html",
        token=token,
        error=error,
        csrf_token=_issue_csrf_token("reset_password"),
    )
    if status_code is None:
        return _no_cache_response(response)
    return _no_cache_response(response, status_code)


def _validate_reset_form_passwords(new_password: str, confirm: str):
    if len(new_password) < 8:
        return "密碼長度至少需要 8 個字元"
    if new_password != confirm:
        return "兩次輸入的密碼不一致"
    return None


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        if not _validate_csrf_token("forgot_password"):
            flash("表單已失效，請再試一次", "error")
            return _no_cache_response(render_template(
                "forgot_password.html",
                csrf_token=_issue_csrf_token("forgot_password"),
            ), 400)

        remote_addr = (request.remote_addr or "unknown").strip() or "unknown"
        if _is_forgot_password_rate_limited(remote_addr):
            logger.warning("Password reset request blocked by IP limit (remote_addr=%s).", remote_addr)
            flash("操作過於頻繁，請稍後再試。", "error")
            return redirect(url_for("forgot_password"))

        email = (request.form.get("email") or "").strip().lower()
        if not _is_valid_email(email):
            logger.info("Password reset submitted with invalid email format (remote_addr=%s).", remote_addr)
            flash("請輸入有效的電子信箱。", "error")
            return redirect(url_for("forgot_password"))

        missing_settings = _missing_mail_settings()
        if missing_settings:
            logger.error(
                "Password reset email cannot be sent because mail settings are missing (remote_addr=%s, missing=%s).",
                remote_addr,
                ",".join(missing_settings),
            )
            flash(_PASSWORD_RESET_MAIL_CONFIG_MESSAGE, "error")
            return redirect(url_for("forgot_password"))

        reset_status = _request_password_reset(email)
        if reset_status == "send_failed":
            logger.error("Password reset request accepted but email send failed (recipient=%s).", _mask_email(email))
        else:
            logger.info("Password reset request processed (status=%s, recipient=%s).", reset_status, _mask_email(email))

        flash(_PASSWORD_RESET_ACCEPTED_MESSAGE, "info")
        return redirect(url_for("forgot_password"))
    return _no_cache_response(render_template(
        "forgot_password.html",
        csrf_token=_issue_csrf_token("forgot_password"),
    ))


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
        session.pop("user_id", None)
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


@app.route("/prompt-image")
def prompt_image_page() -> ResponseReturnValue:
    return render_template("prompt_image.html")


@app.route("/api/prompt-image/analyze", methods=["POST"])
def api_prompt_image_analyze() -> ResponseReturnValue:
    if "image" not in request.files:
        return jsonify({"error": "未上傳圖片"}), 400

    prompt = (request.form.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "請輸入 prompt"}), 400

    file = request.files["image"]
    err, status = _validate_image_file(file)
    if err:
        return err, status or 400

    model_name = getattr(pet_model_config, "pet_model_name", "qwen3-vl:4b")
    prompt_text = pet_model_config.build_image_prompt(prompt)
    result = model_connector.get_model_response_by_image(model_name, file, prompt=prompt_text)
    if result is None:
        return jsonify({"error": "分析失敗，請確認 Ollama 服務是否運行"}), 500
    if result.get("error"):
        return jsonify(result), 500

    return jsonify({
        "result": result.get("result", ""),
        "raw": result,
    })


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
            "describe": result.get("description", ""),
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
    """取得單一寵物（擁有者或共同飼養人均可讀取）"""
    pet = db.get_pet_accessible(pet_id, user_id=current_user_id())
    if not pet:
        return jsonify({"error": "找不到寵物"}), 404
    return jsonify(pet)


@app.route("/api/pets/<int:pet_id>", methods=["PUT"])
def api_update_pet(pet_id):
    """更新寵物資料（擁有者或 editor 共同飼養人均可）"""
    uid = current_user_id()
    if not db.get_pet_if_editable(pet_id, user_id=uid):
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
        user_id=None,  # access already verified by get_pet_if_editable
    )
    return jsonify(db.get_pet_accessible(pet_id, user_id=uid))


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


# ========== Pet Shares API ==========

@app.route("/api/pets/<int:pet_id>/shares", methods=["GET"])
def api_get_pet_shares(pet_id):
    """列出寵物的共同飼養人（僅擁有者可查詢）"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物"}), 404
    shares = db.get_pet_shares(pet_id, owner_user_id=uid)
    return jsonify({"shares": shares})


@app.route("/api/pets/<int:pet_id>/shares/<int:share_id>", methods=["DELETE"])
def api_remove_pet_share(pet_id, share_id):
    """移除共同飼養人（僅擁有者可操作）"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物"}), 404
    removed = db.remove_pet_share(share_id, owner_user_id=uid)
    if not removed:
        return jsonify({"error": "找不到共享紀錄"}), 404
    return "", 204


# ========== Pet Invitations API ==========

_VALID_ROLES = {"read_only", "editor"}


@app.route("/api/pets/<int:pet_id>/invitations", methods=["GET"])
def api_get_pet_invitations(pet_id):
    """列出寵物的待處理邀請（僅擁有者可查詢）"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物"}), 404
    invitations = db.get_pet_invitations_for_pet(pet_id, inviter_user_id=uid)
    return jsonify({"invitations": invitations})


@app.route("/api/pets/<int:pet_id>/invitations", methods=["POST"])
def api_send_pet_invitation(pet_id):
    """發送共同飼養邀請（僅擁有者可操作）"""
    uid = current_user_id()
    pet = db.get_pet(pet_id, user_id=uid)
    if not pet:
        return jsonify({"error": "找不到寵物"}), 404
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    role = (data.get("role") or "").strip()
    if role not in _VALID_ROLES:
        return jsonify({"error": "無效的角色"}), 400
    invitee = db.get_user_by_username(username)
    if not invitee:
        return jsonify({"error": "找不到使用者"}), 404
    if invitee["id"] == uid:
        return jsonify({"error": "不能邀請自己"}), 400
    if not invitee.get("email"):
        return jsonify({"error": "該使用者未設定電子郵件"}), 400
    if db.is_pet_co_owner(pet_id, invitee["id"]):
        return jsonify({"error": "該使用者已是共同飼養人"}), 400
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = _utcnow_naive() + timedelta(days=7)
    inv_id = db.create_pet_share_invitation(
        pet_id=pet_id,
        inviter_user_id=uid,
        invitee_user_id=invitee["id"],
        role=role,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    inviter = db.get_user_by_id(uid)
    join_url = url_for("pet_join_page", token=raw_token, _external=True)
    email_sent = _send_pet_invite_email(
        invitee_email=invitee["email"],
        inviter_username=inviter["username"],
        pet_name=pet["name"],
        role=role,
        join_url=join_url,
        inviter_user_id=uid,
    )
    return jsonify({"id": inv_id, "invitee_username": username, "role": role, "email_sent": email_sent}), 201


@app.route("/api/pets/<int:pet_id>/invitations/<int:inv_id>", methods=["DELETE"])
def api_cancel_pet_invitation(pet_id, inv_id):
    """取消邀請（僅擁有者可操作）"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物"}), 404
    cancelled = db.cancel_pet_share_invitation(inv_id, inviter_user_id=uid)
    if not cancelled:
        return jsonify({"error": "找不到邀請"}), 404
    return "", 204


# ========== Pet Join (accept/decline invitation) ==========

_INVITE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def _get_valid_invitation(token):
    """Validate raw token format, return invitation record or None."""
    if not _INVITE_TOKEN_RE.fullmatch(token or ""):
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return db.get_pet_share_invitation_by_token(token_hash)


@app.route("/pets/join/<token>")
def pet_join_page(token):
    """顯示邀請詳情，讓受邀者選擇接受或婉拒。"""
    inv = _get_valid_invitation(token)
    if not inv:
        return render_template("pet_join.html", error="邀請連結無效或已過期",
                               csrf_token=_issue_csrf_token("pet_join"))
    uid = current_user_id()
    if inv["invitee_user_id"] != uid:
        return render_template("pet_join.html", error="邀請連結無效或已過期",
                               csrf_token=_issue_csrf_token("pet_join"))
    if inv["status"] != "pending":
        msg = "此邀請已接受" if inv["status"] == "accepted" else "此邀請已使用或已取消"
        return render_template("pet_join.html", error=msg,
                               csrf_token=_issue_csrf_token("pet_join"))
    if inv["expires_at"] < _utcnow_naive():
        return render_template("pet_join.html", error="邀請已過期，請請求重新發送",
                               csrf_token=_issue_csrf_token("pet_join"))
    role_display = _ROLE_DISPLAY.get(inv["role"], inv["role"])
    return render_template("pet_join.html", invitation=inv, role_display=role_display,
                           token=token, csrf_token=_issue_csrf_token("pet_join"))


@app.route("/pets/join/<token>", methods=["POST"])
def pet_join_action(token):
    """處理接受或婉拒邀請的表單提交。"""
    if not _validate_csrf_token("pet_join"):
        flash("表單已失效，請再試一次")
        return redirect(url_for("pet_join_page", token=token))
    uid = current_user_id()
    inv = _get_valid_invitation(token)
    if not inv or inv["invitee_user_id"] != uid or inv["status"] != "pending":
        flash("邀請連結無效或已過期")
        return redirect(url_for("index"))
    action = (request.form.get("action") or "").strip()
    if action == "accept":
        joined = db.accept_pet_share_invitation(inv["id"], invitee_user_id=uid)
        if joined:
            flash(f"已加入「{inv['pet_name']}」的共同飼養人！")
        else:
            flash(f"您已是「{inv['pet_name']}」的共同飼養人")
        return redirect(url_for("pets_page"))
    elif action == "decline":
        db.decline_pet_share_invitation(inv["id"], invitee_user_id=uid)
        flash("已婉拒邀請")
        return redirect(url_for("index"))
    return redirect(url_for("pet_join_page", token=token))


# ========== Products API ==========


@app.route("/api/products", methods=["GET"])
def api_get_products():
    """取得所有商品"""
    uid = current_user_id()
    pet_id = request.args.get("pet_id", type=int)
    if pet_id and pet_id > 0:
        if not db.get_pet_accessible(pet_id, uid):
            return jsonify({"products": []})
        user_id_filter = None  # show all users' content for shared pets
    else:
        user_id_filter = uid
    return jsonify({"products": db.get_all_products(pet_id=pet_id, user_id=user_id_filter)})


@app.route("/api/products", methods=["POST"])
def api_add_product():
    """新增商品"""
    uid = current_user_id()
    data = request.get_json() or {}
    title = (data.get("title") or "").strip() or "（未命名）"
    summary = (data.get("summary") or "").strip()
    pet_id = data.get("pet_id") or None
    if pet_id and pet_id > 0 and not db.get_pet_if_editable(pet_id, uid):
        return jsonify({"error": "找不到寵物或無編輯權限"}), 404
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
    if not db.get_product_if_editable(product_id, user_id=uid):
        return jsonify({"error": "找不到商品或無編輯權限"}), 404
    data = request.get_json() or {}
    title = (data.get("title") or "").strip() or "（未命名）"
    summary = (data.get("summary") or "").strip()
    pet_id = data.get("pet_id") or None
    if pet_id and pet_id > 0 and not db.get_pet_if_editable(pet_id, uid):
        return jsonify({"error": "找不到寵物或無編輯權限"}), 404
    db.update_product(product_id, title, summary, pet_id=pet_id, user_id=uid)
    return jsonify(db.get_product(product_id, user_id=uid))


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def api_delete_product(product_id):
    """刪除商品"""
    uid = current_user_id()
    if not db.get_product_if_editable(product_id, user_id=uid):
        return jsonify({"error": "找不到商品或無編輯權限"}), 404
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
    uid = current_user_id()
    pet_id = request.args.get("pet_id", type=int)
    if pet_id and pet_id > 0:
        if not db.get_pet_accessible(pet_id, uid):
            return jsonify({"diaries": []})
        user_id_filter = None  # show all users' content for shared pets
    else:
        user_id_filter = uid
    return jsonify({"diaries": db.get_all_diaries(pet_id=pet_id, user_id=user_id_filter)})


@app.route("/api/diaries", methods=["POST"])
def api_add_diary():
    """新增日記"""
    uid = current_user_id()
    data = request.get_json() or {}
    pet_id = data.get("pet_id") or None
    if pet_id and pet_id > 0 and not db.get_pet_if_editable(pet_id, uid):
        return jsonify({"error": "找不到寵物或無編輯權限"}), 404
    diary_id = db.add_diary(
        title=(data.get("title") or "").strip(),
        describe_text=(data.get("describe_text") or "").strip(),
        main_emotion=(data.get("main_emotion") or "").strip(),
        memo=(data.get("memo") or "").strip(),
        image_base64=(data.get("image_base64") or ""),
        pet_id=pet_id,
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
    if not db.get_diary_if_editable(diary_id, user_id=uid):
        return jsonify({"error": "找不到日記或無編輯權限"}), 404
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


@app.route("/api/calendar-items", methods=["GET"])
def api_get_calendar_items():
    """取得指定年月的日曆項目（商品 + 日記），合併後按日期分組回傳。"""
    uid = current_user_id()

    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    if year is None or month is None:
        return jsonify({"error": "year 與 month 為必填參數"}), 400
    if not (1 <= month <= 12) or year < 1:
        return jsonify({"error": "year 或 month 超出有效範圍"}), 400

    products = db.get_all_products(user_id=uid)
    diaries = db.get_all_diaries(user_id=uid)

    items = []

    for p in products:
        created_at = p["created_at"]
        if hasattr(created_at, "year") and created_at.year == year and created_at.month == month:
            items.append(
                {
                    "type": "product",
                    "id": p["id"],
                    "title": p["title"],
                    "date": created_at.date().isoformat(),
                }
            )

    for d in diaries:
        created_at = d["created_at"]
        if hasattr(created_at, "year") and created_at.year == year and created_at.month == month:
            items.append(
                {
                    "type": "diary",
                    "id": d["id"],
                    "title": d["title"],
                    "date": created_at.date().isoformat(),
                }
            )

    return jsonify({"items": items})


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
