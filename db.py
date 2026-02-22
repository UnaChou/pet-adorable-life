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


def init_db():
    """建立 products 資料表（若不存在），並確保有 updated_at 欄位。"""
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
            # 相容既有資料表：若缺少 updated_at 則補上
            try:
                cur.execute("""
                    ALTER TABLE products
                    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    AFTER created_at
                """)
            except pymysql.err.OperationalError as e:
                if e.args[0] != 1060:  # 1060 = Duplicate column name
                    raise

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
            try:
                cur.execute("ALTER TABLE pet_diaries ADD COLUMN title VARCHAR(500) AFTER id")
            except pymysql.err.OperationalError as e:
                if e.args[0] != 1060:
                    raise
            try:
                cur.execute("ALTER TABLE pet_diaries ADD COLUMN image_base64 LONGTEXT AFTER memo")
            except pymysql.err.OperationalError as e:
                if e.args[0] != 1060:
                    raise


def get_all_products():
    """取得所有商品，依建立日期新到舊排序，回傳完整資訊。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, summary, created_at, updated_at
                FROM products
                ORDER BY created_at DESC, id DESC
            """)
            rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "summary": r["summary"] or "",
            "created_at": r["created_at"],
            "updated_at": r.get("updated_at"),
        }
        for r in rows
    ]


def add_product(title, summary):
    """新增商品，回傳新商品的 id。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO products (title, summary) VALUES (%s, %s)",
                (title, summary),
            )
            return cur.lastrowid


def get_product(product_id):
    """依 id 取得單一商品，不存在則回傳 None。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, summary, created_at, updated_at FROM products WHERE id = %s",
                (product_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "summary": row["summary"] or "",
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


def update_product(product_id, title, summary):
    """更新商品。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE products SET title = %s, summary = %s WHERE id = %s",
                (title, summary, product_id),
            )


def remove_product(product_id):
    """依 id 刪除商品。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM products WHERE id = %s", (product_id,))


def remove_products(product_ids):
    """批次刪除多個商品。"""
    if not product_ids:
        return
    placeholders = ", ".join(["%s"] * len(product_ids))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM products WHERE id IN ({placeholders})",
                product_ids,
            )


# ========== Pet diary ==========


def get_all_diaries():
    """取得所有日記，依建立日期新到舊。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, describe_text, main_emotion, memo, image_base64, created_at, updated_at
                FROM pet_diaries
                ORDER BY created_at DESC, id DESC
            """)
            rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "title": r.get("title") or "",
            "describe_text": r["describe_text"] or "",
            "main_emotion": r["main_emotion"] or "",
            "memo": r["memo"] or "",
            "image_base64": r.get("image_base64") or "",
            "created_at": r["created_at"],
            "updated_at": r.get("updated_at"),
        }
        for r in rows
    ]


def add_diary(title, describe_text, main_emotion, memo, image_base64=""):
    """新增日記，回傳 id。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pet_diaries (title, describe_text, main_emotion, memo, image_base64) VALUES (%s, %s, %s, %s, %s)",
                (title or "", describe_text or "", main_emotion or "", memo or "", image_base64 or ""),
            )
            return cur.lastrowid


def remove_diaries(diary_ids):
    """批次刪除日記。"""
    if not diary_ids:
        return
    placeholders = ", ".join(["%s"] * len(diary_ids))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM pet_diaries WHERE id IN ({placeholders})",
                diary_ids,
            )
