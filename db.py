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


def _guard_alter(cur, sql):
    """執行 ALTER TABLE，忽略 Duplicate column name (1060)。"""
    try:
        cur.execute(sql)
    except pymysql.err.OperationalError as e:
        if e.args[0] != 1060:
            raise


def init_db():
    """建立所有必要的資料表並補齊缺漏欄位。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
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

            # ユーザー管理テーブル
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(100) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            _guard_alter(cur, "ALTER TABLE products ADD COLUMN pet_id INT AFTER summary")
            _guard_alter(cur, "ALTER TABLE pet_diaries ADD COLUMN pet_id INT AFTER main_emotion")

            # user_id 欄位（支援資料隔離）
            _guard_alter(cur, "ALTER TABLE pets ADD COLUMN user_id INT AFTER id")
            _guard_alter(cur, "ALTER TABLE products ADD COLUMN user_id INT AFTER pet_id")
            _guard_alter(cur, "ALTER TABLE pet_diaries ADD COLUMN user_id INT AFTER pet_id")


# ========== Users ==========


def create_user(username, password_hash):
    """新增使用者，回傳 id。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash),
            )
            return cur.lastrowid


def get_user_by_username(username):
    """依 username 取得使用者，不存在則回傳 None。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE username = %s",
                (username,),
            )
            return cur.fetchone()


def get_user_by_id(user_id):
    """依 id 取得使用者，不存在則回傳 None。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            return cur.fetchone()


# ========== Products ==========


def get_all_products(pet_id=None, user_id=None):
    """取得商品清單。pet_id=0 表示未指定寵物；user_id 限定擁有者。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            user_clause = " AND user_id = %s" if user_id is not None else ""
            user_params = (user_id,) if user_id is not None else ()
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
        "created_at": r["created_at"],
        "updated_at": r.get("updated_at"),
    }


def get_all_pets(user_id=None):
    """取得所有寵物，依建立時間升序。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute("""
                    SELECT id, name, breed, birthday, photo_base64, user_id, created_at, updated_at
                    FROM pets WHERE user_id = %s ORDER BY created_at ASC
                """, (user_id,))
            else:
                cur.execute("""
                    SELECT id, name, breed, birthday, photo_base64, user_id, created_at, updated_at
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
    """刪除寵物，並將相關商品與日記的 pet_id 設為 NULL。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute(
                    "UPDATE products SET pet_id = NULL WHERE pet_id = %s AND user_id = %s",
                    (pet_id, user_id),
                )
                cur.execute(
                    "UPDATE pet_diaries SET pet_id = NULL WHERE pet_id = %s AND user_id = %s",
                    (pet_id, user_id),
                )
                cur.execute(
                    "DELETE FROM pets WHERE id = %s AND user_id = %s",
                    (pet_id, user_id),
                )
            else:
                cur.execute("UPDATE products SET pet_id = NULL WHERE pet_id = %s", (pet_id,))
                cur.execute("UPDATE pet_diaries SET pet_id = NULL WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pets WHERE id = %s", (pet_id,))


# ========== Pet diary ==========


def get_all_diaries(pet_id=None, user_id=None):
    """取得日記清單。pet_id=0 表示未指定寵物；user_id 限定擁有者。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            user_clause = " AND user_id = %s" if user_id is not None else ""
            user_params = (user_id,) if user_id is not None else ()
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
