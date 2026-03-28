"""
MySQL 資料庫連線與商品 CRUD 操作
"""
import os
import pymysql
from contextlib import contextmanager
from pymysql.cursors import DictCursor


def _get_db_config():
    """從環境變數讀取資料庫設定。"""
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "pet_user"),
        "password": os.getenv("MYSQL_PASSWORD", "pet_password"),
        "database": os.getenv("MYSQL_DATABASE", "pet_adorable_life"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
    }


@contextmanager
def get_connection():
    """取得資料庫連線的 context manager。"""
    conn = pymysql.connect(**_get_db_config())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _guard_alter(cur, sql, ignore_codes=(1060,)):
    """執行 ALTER TABLE / CREATE INDEX，忽略指定 MySQL 錯誤碼。"""
    try:
        cur.execute(sql)
    except pymysql.err.OperationalError as e:
        if e.args[0] not in ignore_codes:
            raise


def _init_products_table(cur):
    """建立 products 表及補齊缺漏欄位。"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    _guard_alter(cur, """
        ALTER TABLE products
        ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        AFTER created_at
    """)


def _init_pet_diaries_table(cur):
    """建立 pet_diaries 表及補齊缺漏欄位。"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pet_diaries (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(500),
            describe_text TEXT,
            main_emotion VARCHAR(200),
            memo TEXT,
            image_base64 LONGTEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    _guard_alter(cur, "ALTER TABLE pet_diaries ADD COLUMN title VARCHAR(500) AFTER id")
    _guard_alter(cur, "ALTER TABLE pet_diaries ADD COLUMN image_base64 LONGTEXT AFTER memo")


def _init_pets_table(cur):
    """建立 pets 表。"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            breed VARCHAR(200),
            birthday DATE,
            photo_base64 LONGTEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)


def _init_users_table(cur):
    """建立 users 表及補齊缺漏欄位。"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _guard_alter(cur, "ALTER TABLE users ADD COLUMN email VARCHAR(255) AFTER username")
    _guard_alter(
        cur,
        "ALTER TABLE users ADD UNIQUE INDEX idx_users_email (email)",
        ignore_codes=(1060, 1061),
    )


def _init_password_reset_tokens_table(cur):
    """建立 password_reset_tokens 表。"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            token_hash VARCHAR(255) NOT NULL UNIQUE,
            expires_at DATETIME NOT NULL,
            used_at DATETIME DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_token_hash (token_hash),
            INDEX idx_user_id (user_id)
        )
    """)


def _apply_relationship_columns(cur):
    """補齊關聯欄位（pet_id 與 user_id）。"""
    _guard_alter(cur, "ALTER TABLE products ADD COLUMN pet_id INT AFTER summary")
    _guard_alter(cur, "ALTER TABLE pet_diaries ADD COLUMN pet_id INT AFTER main_emotion")
    _guard_alter(cur, "ALTER TABLE pets ADD COLUMN user_id INT AFTER id")
    _guard_alter(cur, "ALTER TABLE products ADD COLUMN user_id INT AFTER pet_id")
    _guard_alter(cur, "ALTER TABLE pet_diaries ADD COLUMN user_id INT AFTER pet_id")


def _init_pet_shares_table(cur):
    """建立 pet_shares 表（已接受的共同飼養人）。"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pet_shares (
            id INT AUTO_INCREMENT PRIMARY KEY,
            pet_id INT NOT NULL,
            owner_user_id INT NOT NULL,
            shared_with_user_id INT NOT NULL,
            role ENUM('read_only', 'editor') NOT NULL DEFAULT 'read_only',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_pet_shared (pet_id, shared_with_user_id),
            INDEX idx_shared_with (shared_with_user_id)
        )
    """)
    _guard_alter(cur, "ALTER TABLE pet_shares ADD COLUMN role ENUM('read_only', 'editor') NOT NULL DEFAULT 'read_only' AFTER shared_with_user_id", ignore_codes=(1060,))


def _init_pet_share_invitations_table(cur):
    """建立 pet_share_invitations 表（待回應的邀請）。"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pet_share_invitations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            pet_id INT NOT NULL,
            inviter_user_id INT NOT NULL,
            invitee_user_id INT NOT NULL,
            role ENUM('read_only', 'editor') NOT NULL DEFAULT 'read_only',
            token_hash VARCHAR(255) NOT NULL UNIQUE,
            status ENUM('pending', 'accepted', 'declined', 'cancelled') NOT NULL DEFAULT 'pending',
            expires_at DATETIME NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_token_hash (token_hash),
            INDEX idx_invitee_pending (invitee_user_id, status)
        )
    """)


def init_db():
    """建立所有必要的資料表並補齊缺漏欄位。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            _init_products_table(cur)
            _init_pet_diaries_table(cur)
            _init_pets_table(cur)
            _init_users_table(cur)
            _init_password_reset_tokens_table(cur)
            _apply_relationship_columns(cur)
            _init_pet_shares_table(cur)
            _init_pet_share_invitations_table(cur)


# ========== Users ==========


def create_user(username, email, password_hash):
    """新增使用者，回傳 id。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (username, email or None, password_hash),
            )
            return cur.lastrowid


def get_user_by_username(username):
    """依 username 取得使用者，不存在則回傳 None。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, password_hash, created_at FROM users WHERE username = %s",
                (username,),
            )
            return cur.fetchone()


def get_user_by_id(user_id):
    """依 id 取得使用者，不存在則回傳 None。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, email, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            return cur.fetchone()


def get_user_by_email(email):
    """依 email 取得使用者，不存在則回傳 None。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, email, created_at FROM users WHERE email = %s",
                (email,),
            )
            return cur.fetchone()


def update_user_password(user_id, password_hash):
    """更新使用者密碼。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (password_hash, user_id),
            )


def create_reset_token(user_id, token_hash, expires_at):
    """新增密碼重設 token。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
                (user_id, token_hash, expires_at),
            )


def get_reset_token(token_hash):
    """依 token_hash 查詢重設 token 記錄。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, expires_at, used_at FROM password_reset_tokens WHERE token_hash = %s",
                (token_hash,),
            )
            return cur.fetchone()


def mark_reset_token_used(token_id):
    """將 token 標記為已使用。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE password_reset_tokens SET used_at = NOW() WHERE id = %s",
                (token_id,),
            )


def invalidate_user_reset_tokens(user_id):
    """作廢使用者所有未使用的重設 token。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE password_reset_tokens SET used_at = NOW() WHERE user_id = %s AND used_at IS NULL",
                (user_id,),
            )


def count_recent_reset_requests(user_id, since_minutes=60):
    """計算指定時間內的重設請求次數（Rate limiting 用）。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM password_reset_tokens"
                " WHERE user_id = %s AND created_at > NOW() - INTERVAL %s MINUTE",
                (user_id, since_minutes),
            )
            row = cur.fetchone()
            return row["cnt"] if row else 0


# ========== Products ==========


def get_all_products(pet_id=None, user_id=None):
    """取得商品清單。pet_id=0 表示未指定寵物；user_id 限定擁有者（含共享寵物）。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                user_clause = (
                    " AND (user_id = %s"
                    " OR pet_id IN (SELECT pet_id FROM pet_shares WHERE shared_with_user_id = %s))"
                )
                user_params = (user_id, user_id)
            else:
                user_clause = ""
                user_params = ()
            if pet_id == 0:
                cur.execute(
                    f"SELECT id, title, summary, pet_id, user_id, created_at, updated_at"
                    f" FROM products WHERE pet_id IS NULL{user_clause}"
                    f" ORDER BY created_at DESC, id DESC",
                    user_params,
                )
            elif pet_id:
                cur.execute(
                    f"SELECT id, title, summary, pet_id, user_id, created_at, updated_at"
                    f" FROM products WHERE pet_id = %s{user_clause}"
                    f" ORDER BY created_at DESC, id DESC",
                    (pet_id,) + user_params,
                )
            else:
                cur.execute(
                    f"SELECT id, title, summary, pet_id, user_id, created_at, updated_at"
                    f" FROM products WHERE 1=1{user_clause}"
                    f" ORDER BY created_at DESC, id DESC",
                    user_params,
                )
            rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "summary": r["summary"] or "",
            "pet_id": r.get("pet_id"),
            "user_id": r.get("user_id"),
            "created_at": r["created_at"],
            "updated_at": r.get("updated_at"),
        }
        for r in rows
    ]


def add_product(title, summary, pet_id=None, user_id=None):
    """新增商品，回傳新商品的 id。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO products (title, summary, pet_id, user_id) VALUES (%s, %s, %s, %s)",
                (title, summary, pet_id or None, user_id),
            )
            return cur.lastrowid


def get_product(product_id, user_id=None):
    """依 id 取得單一商品，不存在或不屬於 user 則回傳 None。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    "SELECT id, title, summary, pet_id, user_id, created_at, updated_at"
                    " FROM products WHERE id = %s AND user_id = %s",
                    (product_id, user_id),
                )
            else:
                cur.execute(
                    "SELECT id, title, summary, pet_id, user_id, created_at, updated_at"
                    " FROM products WHERE id = %s",
                    (product_id,),
                )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "summary": row["summary"] or "",
        "pet_id": row.get("pet_id"),
        "user_id": row.get("user_id"),
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


def update_product(product_id, title, summary, pet_id=None, user_id=None):
    """更新商品。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    "UPDATE products SET title = %s, summary = %s, pet_id = %s"
                    " WHERE id = %s AND user_id = %s",
                    (title, summary, pet_id or None, product_id, user_id),
                )
            else:
                cur.execute(
                    "UPDATE products SET title = %s, summary = %s, pet_id = %s WHERE id = %s",
                    (title, summary, pet_id or None, product_id),
                )


def remove_product(product_id, user_id=None):
    """依 id 刪除商品。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    "DELETE FROM products WHERE id = %s AND user_id = %s",
                    (product_id, user_id),
                )
            else:
                cur.execute("DELETE FROM products WHERE id = %s", (product_id,))


def remove_products(product_ids, user_id=None):
    """批次刪除多個商品。"""
    if not product_ids:
        return
    placeholders = ", ".join(["%s"] * len(product_ids))
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    f"DELETE FROM products WHERE id IN ({placeholders}) AND user_id = %s",
                    list(product_ids) + [user_id],
                )
            else:
                cur.execute(
                    f"DELETE FROM products WHERE id IN ({placeholders})",
                    product_ids,
                )


# ========== Pets ==========


def _format_pet(r):
    return {
        "id": r["id"],
        "name": r["name"],
        "breed": r.get("breed") or "",
        "birthday": str(r["birthday"]) if r.get("birthday") else "",
        "photo_base64": r.get("photo_base64") or "",
        "user_id": r.get("user_id"),
        "is_shared": bool(r.get("is_shared", 0)),
        "created_at": r["created_at"],
        "updated_at": r.get("updated_at"),
    }


def get_all_pets(user_id=None):
    """取得所有寵物，依建立時間升序；user_id 時包含共享寵物。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute("""
                    SELECT id, name, breed, birthday, photo_base64, user_id,
                           created_at, updated_at, 0 AS is_shared
                    FROM pets WHERE user_id = %s
                    UNION ALL
                    SELECT p.id, p.name, p.breed, p.birthday, p.photo_base64, p.user_id,
                           p.created_at, p.updated_at, 1 AS is_shared
                    FROM pets p
                    INNER JOIN pet_shares s ON s.pet_id = p.id
                    WHERE s.shared_with_user_id = %s
                    ORDER BY created_at ASC
                """, (user_id, user_id))
            else:
                cur.execute("""
                    SELECT id, name, breed, birthday, photo_base64, user_id,
                           created_at, updated_at, 0 AS is_shared
                    FROM pets ORDER BY created_at ASC
                """)
            rows = cur.fetchall()
    return [_format_pet(r) for r in rows]


def add_pet(name, breed="", birthday=None, photo_base64="", user_id=None):
    """新增寵物，回傳 id。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pets (name, breed, birthday, photo_base64, user_id)"
                " VALUES (%s, %s, %s, %s, %s)",
                (name, breed or None, birthday or None, photo_base64 or None, user_id),
            )
            return cur.lastrowid


def get_pet(pet_id, user_id=None):
    """依 id 取得單一寵物，不存在或不屬於 user 則回傳 None。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    "SELECT id, name, breed, birthday, photo_base64, user_id, created_at, updated_at"
                    " FROM pets WHERE id = %s AND user_id = %s",
                    (pet_id, user_id),
                )
            else:
                cur.execute(
                    "SELECT id, name, breed, birthday, photo_base64, user_id, created_at, updated_at"
                    " FROM pets WHERE id = %s",
                    (pet_id,),
                )
            row = cur.fetchone()
    return _format_pet(row) if row else None


def get_pet_accessible(pet_id, user_id):
    """取得寵物（擁有者或任何共同飼養人均可讀取）。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.id, p.name, p.breed, p.birthday, p.photo_base64, p.user_id,"
                " p.created_at, p.updated_at,"
                " CASE WHEN p.user_id != %s THEN 1 ELSE 0 END AS is_shared"
                " FROM pets p"
                " WHERE p.id = %s AND ("
                "   p.user_id = %s"
                "   OR EXISTS ("
                "     SELECT 1 FROM pet_shares"
                "     WHERE pet_id = p.id AND shared_with_user_id = %s"
                "   )"
                " )",
                (user_id, pet_id, user_id, user_id),
            )
            row = cur.fetchone()
    return _format_pet(row) if row else None


def get_pet_if_editable(pet_id, user_id):
    """取得寵物（擁有者或 editor 共同飼養人可修改）。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.id, p.name, p.breed, p.birthday, p.photo_base64, p.user_id,"
                " p.created_at, p.updated_at,"
                " CASE WHEN p.user_id != %s THEN 1 ELSE 0 END AS is_shared"
                " FROM pets p"
                " WHERE p.id = %s AND ("
                "   p.user_id = %s"
                "   OR EXISTS ("
                "     SELECT 1 FROM pet_shares"
                "     WHERE pet_id = p.id AND shared_with_user_id = %s AND role = 'editor'"
                "   )"
                " )",
                (user_id, pet_id, user_id, user_id),
            )
            row = cur.fetchone()
    return _format_pet(row) if row else None


def update_pet(pet_id, name, breed="", birthday=None, photo_base64=None, user_id=None):
    """更新寵物。photo_base64=None 表示不更新照片。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            uid_clause = " AND user_id = %s" if user_id is not None else ""
            uid_param = (user_id,) if user_id is not None else ()
            if photo_base64 is not None:
                cur.execute(
                    f"UPDATE pets SET name=%s, breed=%s, birthday=%s, photo_base64=%s"
                    f" WHERE id=%s{uid_clause}",
                    (name, breed or None, birthday or None, photo_base64 or None, pet_id) + uid_param,
                )
            else:
                cur.execute(
                    f"UPDATE pets SET name=%s, breed=%s, birthday=%s"
                    f" WHERE id=%s{uid_clause}",
                    (name, breed or None, birthday or None, pet_id) + uid_param,
                )


def remove_pet(pet_id, user_id=None):
    """刪除寵物，並清除相關商品/日記歸屬及共同飼養記錄。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    "UPDATE products SET pet_id = NULL WHERE pet_id = %s",
                    (pet_id,),
                )
                cur.execute(
                    "UPDATE pet_diaries SET pet_id = NULL WHERE pet_id = %s",
                    (pet_id,),
                )
                cur.execute("DELETE FROM pet_share_invitations WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pet_shares WHERE pet_id = %s", (pet_id,))
                cur.execute(
                    "DELETE FROM pets WHERE id = %s AND user_id = %s",
                    (pet_id, user_id),
                )
            else:
                cur.execute("UPDATE products SET pet_id = NULL WHERE pet_id = %s", (pet_id,))
                cur.execute("UPDATE pet_diaries SET pet_id = NULL WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pet_share_invitations WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pet_shares WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pets WHERE id = %s", (pet_id,))


# ========== Pet Shares ==========


def add_pet_share(pet_id, owner_user_id, shared_with_user_id, role="read_only"):
    """新增共同飼養人記錄，回傳 share id。重複時拋出 IntegrityError。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pet_shares (pet_id, owner_user_id, shared_with_user_id, role)"
                " VALUES (%s, %s, %s, %s)",
                (pet_id, owner_user_id, shared_with_user_id, role),
            )
            return cur.lastrowid


def get_pet_shares(pet_id, owner_user_id):
    """列出某寵物的共同飼養人（含 role）。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.id, s.shared_with_user_id, u.username, s.role"
                " FROM pet_shares s JOIN users u ON u.id = s.shared_with_user_id"
                " WHERE s.pet_id = %s AND s.owner_user_id = %s"
                " ORDER BY s.created_at ASC",
                (pet_id, owner_user_id),
            )
            return cur.fetchall()


def is_pet_co_owner(pet_id, user_id):
    """回傳 True 如果 user_id 是該寵物的共同飼養人。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pet_shares WHERE pet_id = %s AND shared_with_user_id = %s LIMIT 1",
                (pet_id, user_id),
            )
            return cur.fetchone() is not None


def remove_pet_share(share_id, owner_user_id):
    """移除共同飼養人，回傳刪除筆數。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM pet_shares WHERE id = %s AND owner_user_id = %s",
                (share_id, owner_user_id),
            )
            return cur.rowcount


# ========== Pet Share Invitations ==========


def create_pet_share_invitation(pet_id, inviter_user_id, invitee_user_id, role, token_hash, expires_at):
    """新增邀請記錄。若同一 pet+invitee 已有 pending 邀請，先取消舊的再建新的。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE pet_share_invitations SET status = 'cancelled'"
                " WHERE pet_id = %s AND invitee_user_id = %s AND status = 'pending'",
                (pet_id, invitee_user_id),
            )
            cur.execute(
                "INSERT INTO pet_share_invitations"
                " (pet_id, inviter_user_id, invitee_user_id, role, token_hash, expires_at)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (pet_id, inviter_user_id, invitee_user_id, role, token_hash, expires_at),
            )
            return cur.lastrowid


def get_pet_share_invitation_by_token(token_hash):
    """依 token_hash 查詢邀請，JOIN 邀請人名稱和寵物名稱。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT i.id, i.pet_id, i.inviter_user_id, i.invitee_user_id, i.role,"
                " i.status, i.expires_at,"
                " u.username AS inviter_username, p.name AS pet_name"
                " FROM pet_share_invitations i"
                " JOIN users u ON u.id = i.inviter_user_id"
                " JOIN pets p ON p.id = i.pet_id"
                " WHERE i.token_hash = %s",
                (token_hash,),
            )
            return cur.fetchone()


def accept_pet_share_invitation(invitation_id, invitee_user_id):
    """接受邀請：建立 pet_shares 記錄並標記邀請為 accepted（原子操作）。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, pet_id, inviter_user_id, role"
                " FROM pet_share_invitations"
                " WHERE id = %s AND invitee_user_id = %s AND status = 'pending'"
                " AND expires_at > NOW()",
                (invitation_id, invitee_user_id),
            )
            inv = cur.fetchone()
            if not inv:
                return False
            cur.execute(
                "INSERT IGNORE INTO pet_shares (pet_id, owner_user_id, shared_with_user_id, role)"
                " VALUES (%s, %s, %s, %s)",
                (inv["pet_id"], inv["inviter_user_id"], invitee_user_id, inv["role"]),
            )
            inserted = cur.rowcount > 0
            cur.execute(
                "UPDATE pet_share_invitations SET status = 'accepted' WHERE id = %s",
                (invitation_id,),
            )
            return inserted


def decline_pet_share_invitation(invitation_id, invitee_user_id):
    """婉拒邀請，回傳更新筆數。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE pet_share_invitations SET status = 'declined'"
                " WHERE id = %s AND invitee_user_id = %s AND status = 'pending'",
                (invitation_id, invitee_user_id),
            )
            return cur.rowcount


def get_pet_invitations_for_pet(pet_id, inviter_user_id):
    """列出某寵物的待確認邀請（擁有者視角）。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT i.id, i.invitee_user_id, u.username AS invitee_username,"
                " i.role, i.status, i.expires_at, i.created_at"
                " FROM pet_share_invitations i"
                " JOIN users u ON u.id = i.invitee_user_id"
                " WHERE i.pet_id = %s AND i.inviter_user_id = %s AND i.status = 'pending'"
                " ORDER BY i.created_at ASC",
                (pet_id, inviter_user_id),
            )
            return cur.fetchall()


def cancel_pet_share_invitation(invitation_id, inviter_user_id):
    """取消邀請，回傳更新筆數。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE pet_share_invitations SET status = 'cancelled'"
                " WHERE id = %s AND inviter_user_id = %s AND status = 'pending'",
                (invitation_id, inviter_user_id),
            )
            return cur.rowcount


# ========== Pet diary ==========


def get_all_diaries(pet_id=None, user_id=None):
    """取得日記清單。pet_id=0 表示未指定寵物；user_id 限定擁有者（含共享寵物）。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                user_clause = (
                    " AND (user_id = %s"
                    " OR pet_id IN (SELECT pet_id FROM pet_shares WHERE shared_with_user_id = %s))"
                )
                user_params = (user_id, user_id)
            else:
                user_clause = ""
                user_params = ()
            if pet_id == 0:
                cur.execute(
                    f"SELECT id, title, describe_text, main_emotion, memo, image_base64,"
                    f" pet_id, user_id, created_at, updated_at"
                    f" FROM pet_diaries WHERE pet_id IS NULL{user_clause}"
                    f" ORDER BY created_at DESC, id DESC",
                    user_params,
                )
            elif pet_id:
                cur.execute(
                    f"SELECT id, title, describe_text, main_emotion, memo, image_base64,"
                    f" pet_id, user_id, created_at, updated_at"
                    f" FROM pet_diaries WHERE pet_id = %s{user_clause}"
                    f" ORDER BY created_at DESC, id DESC",
                    (pet_id,) + user_params,
                )
            else:
                cur.execute(
                    f"SELECT id, title, describe_text, main_emotion, memo, image_base64,"
                    f" pet_id, user_id, created_at, updated_at"
                    f" FROM pet_diaries WHERE 1=1{user_clause}"
                    f" ORDER BY created_at DESC, id DESC",
                    user_params,
                )
            rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "title": r.get("title") or "",
            "describe_text": r["describe_text"] or "",
            "main_emotion": r["main_emotion"] or "",
            "memo": r["memo"] or "",
            "image_base64": r.get("image_base64") or "",
            "pet_id": r.get("pet_id"),
            "user_id": r.get("user_id"),
            "created_at": r["created_at"],
            "updated_at": r.get("updated_at"),
        }
        for r in rows
    ]


def add_diary(title, describe_text, main_emotion, memo, image_base64="", pet_id=None, user_id=None):
    """新增日記，回傳 id。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pet_diaries"
                " (title, describe_text, main_emotion, memo, image_base64, pet_id, user_id)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    title or "",
                    describe_text or "",
                    main_emotion or "",
                    memo or "",
                    image_base64 or "",
                    pet_id or None,
                    user_id,
                ),
            )
            return cur.lastrowid


def get_diary(diary_id, user_id=None):
    """依 id 取得單一日記，不存在或不屬於 user 則回傳 None。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    "SELECT id, title, describe_text, main_emotion, memo, image_base64,"
                    " pet_id, user_id, created_at, updated_at"
                    " FROM pet_diaries WHERE id = %s AND user_id = %s",
                    (diary_id, user_id),
                )
            else:
                cur.execute(
                    "SELECT id, title, describe_text, main_emotion, memo, image_base64,"
                    " pet_id, user_id, created_at, updated_at"
                    " FROM pet_diaries WHERE id = %s",
                    (diary_id,),
                )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "title": row.get("title") or "",
        "describe_text": row["describe_text"] or "",
        "main_emotion": row["main_emotion"] or "",
        "memo": row["memo"] or "",
        "image_base64": row.get("image_base64") or "",
        "pet_id": row.get("pet_id"),
        "user_id": row.get("user_id"),
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


def remove_diaries(diary_ids, user_id=None):
    """批次刪除日記。"""
    if not diary_ids:
        return
    placeholders = ", ".join(["%s"] * len(diary_ids))
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    f"DELETE FROM pet_diaries WHERE id IN ({placeholders}) AND user_id = %s",
                    list(diary_ids) + [user_id],
                )
            else:
                cur.execute(
                    f"DELETE FROM pet_diaries WHERE id IN ({placeholders})",
                    diary_ids,
                )
