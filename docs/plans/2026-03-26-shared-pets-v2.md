# 共同寵物 v2（邀請流程＋權限設定）實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Note:** This plan supersedes `docs/plans/2026-03-26-shared-pets.md`. Implement this plan instead of (or on top of) the v1 plan.

**Goal:** Let a pet owner invite another registered user to co-manage their pet via email, choosing read-only or editor access; the invitee clicks a link in the email to accept or decline.

**Architecture:** Two new tables — `pet_shares` (active grants, with `role` column) and `pet_share_invitations` (pending tokens, similar to `password_reset_tokens`). Owner sends an invite → DB record created + email sent with a signed token link → invitee clicks link, logs in if needed (login preserves `?next=`), sees accept/decline page → on accept, `pet_shares` record is created. `GET /api/pets` and pet edit routes are updated to respect the user's role.

**Tech Stack:** Python Flask, PyMySQL, Flask-Mail, MySQL 8, Vanilla JS, pytest with `mock_db` fixture.

---

## File Map

| File | Change |
|------|--------|
| `db.py` | New: `_init_pet_shares_table`, `_init_pet_share_invitations_table`; update `_apply_relationship_columns`; update `_format_pet`, `get_all_pets`, `get_pet_accessible`; new `get_pet_if_editable`; update `add_pet_share` (add `role`), `get_pet_shares` (return `role`), `remove_pet` (cascade); new invitation CRUD: `create_pet_share_invitation`, `get_pet_share_invitation_by_token`, `accept_pet_share_invitation`, `decline_pet_share_invitation`, `get_pet_invitations_for_pet`, `cancel_pet_share_invitation` |
| `app.py` | Update `_require_login` (add `?next=`); update `login` POST (use `next`); update `login.html` binding (pass `next` in fetch body); update `api_get_pet` (use `get_pet_accessible`); update `api_update_pet` (use `get_pet_if_editable`); new `api_get_pet_shares`, `api_add_pet_share`, `api_remove_pet_share`, `api_get_pet_invitations`, `api_cancel_pet_invitation`, `api_send_pet_invitation`; new `pet_join_page`, `pet_join_action`; helper `_send_pet_invite_email` |
| `templates/login.html` | Add `next` param forwarding in fetch body |
| `templates/pets.html` | Updated share dialog: role selector, invite form, pending invitations list, accepted co-owners list |
| `templates/pet_join.html` | New: accept/decline invitation page |
| `tests/test_api_pet_shares.py` | New: API tests for share list, invite send, cancel |
| `tests/test_api_pet_join.py` | New: API tests for accept/decline |
| `tests/test_db_schema.py` | Append: schema test for new tables |
| `tests/test_db_pet_shares.py` | New: integration tests for DB functions (requires running DB) |

---

## Task 1: DB Schema — Two New Tables + `role` Column

**Files:**
- Modify: `db.py` (add `_init_pet_shares_table`, `_init_pet_share_invitations_table`, update `init_db`, update `_apply_relationship_columns`)

- [ ] **Step 1: Write failing schema test**

Append to `tests/test_db_schema.py`:

```python
def test_init_db_creates_pet_shares_and_invitations_tables():
    from unittest.mock import patch, MagicMock
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur

    with patch("db.get_connection", return_value=mock_conn):
        import db
        db.init_db()

    all_sql = [str(c.args[0]) if c.args else "" for c in mock_cur.execute.call_args_list]
    assert any("CREATE TABLE IF NOT EXISTS pet_shares" in s for s in all_sql)
    assert any("shared_with_user_id" in s for s in all_sql)
    assert any("CREATE TABLE IF NOT EXISTS pet_share_invitations" in s for s in all_sql)
    assert any("token_hash" in s for s in all_sql)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_db_schema.py -k "shares_and_invitations" -v
```
Expected: `FAILED` — AssertionError

- [ ] **Step 3: Add `_init_pet_shares_table` to `db.py`**

Add after `_init_password_reset_tokens_table` (around line 128):

```python
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
```

- [ ] **Step 4: Call both from `init_db`**

In `init_db()`, add after `_apply_relationship_columns(cur)`:

```python
_init_pet_shares_table(cur)
_init_pet_share_invitations_table(cur)
```

- [ ] **Step 5: Run schema test — should pass now**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_db_schema.py -k "shares_and_invitations" -v
```
Expected: `PASSED`

- [ ] **Step 6: Commit**

```bash
git add db.py tests/test_db_schema.py
git commit -m "feat(db): add pet_shares and pet_share_invitations table schemas"
```

---

## Task 2: DB — Pet Access Functions (Owned + Shared + Role-Based Edit)

**Files:**
- Modify: `db.py` (`_format_pet`, `get_all_pets`, new `get_pet_accessible`, new `get_pet_if_editable`, update `add_pet_share`, update `get_pet_shares`, update `remove_pet`)

- [ ] **Step 1: Write failing integration tests**

Create `tests/test_db_pet_shares.py`:

> These are integration tests. Run with `docker exec` while DB is running.

```python
"""
Integration tests for pet share DB functions.
Run: docker exec pet-adorable-life-web python -m pytest tests/test_db_pet_shares.py -v
"""
import pytest
import db


@pytest.fixture
def two_users():
    uid_a = db.create_user("share_ta", "share_ta@test.com", "hashed")
    uid_b = db.create_user("share_tb", "share_tb@test.com", "hashed")
    yield uid_a, uid_b
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pet_share_invitations WHERE inviter_user_id IN (%s,%s) OR invitee_user_id IN (%s,%s)", (uid_a, uid_b, uid_a, uid_b))
            cur.execute("DELETE FROM pet_shares WHERE owner_user_id IN (%s,%s) OR shared_with_user_id IN (%s,%s)", (uid_a, uid_b, uid_a, uid_b))
            cur.execute("DELETE FROM pets WHERE user_id IN (%s,%s)", (uid_a, uid_b))
            cur.execute("DELETE FROM users WHERE id IN (%s,%s)", (uid_a, uid_b))


def test_get_all_pets_includes_shared_pet(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("毛球", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="read_only")

    ids = [p["id"] for p in db.get_all_pets(user_id=uid_b)]
    assert pet_id in ids


def test_shared_pet_has_is_shared_true(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("毛球", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="read_only")

    pets_b = db.get_all_pets(user_id=uid_b)
    shared = next(p for p in pets_b if p["id"] == pet_id)
    assert shared["is_shared"] is True


def test_owned_pet_is_shared_false(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("自己的", user_id=uid_a)

    pets_a = db.get_all_pets(user_id=uid_a)
    owned = next(p for p in pets_a if p["id"] == pet_id)
    assert owned["is_shared"] is False


def test_get_pet_accessible_shared_user_can_read(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("毛球", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="read_only")

    pet = db.get_pet_accessible(pet_id, user_id=uid_b)
    assert pet is not None
    assert pet["is_shared"] is True


def test_get_pet_accessible_stranger_returns_none(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("毛球", user_id=uid_a)

    assert db.get_pet_accessible(pet_id, user_id=uid_b) is None


def test_get_pet_if_editable_editor_can_edit(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("毛球", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="editor")

    assert db.get_pet_if_editable(pet_id, user_id=uid_b) is not None


def test_get_pet_if_editable_read_only_cannot_edit(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("毛球", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="read_only")

    assert db.get_pet_if_editable(pet_id, user_id=uid_b) is None


def test_get_pet_shares_returns_role(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("毛球", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="editor")

    shares = db.get_pet_shares(pet_id, owner_user_id=uid_a)
    assert len(shares) == 1
    assert shares[0]["role"] == "editor"


def test_remove_pet_also_removes_shares(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("毛球", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="read_only")
    db.remove_pet(pet_id, user_id=uid_a)

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM pet_shares WHERE pet_id = %s", (pet_id,))
            assert cur.fetchone()["cnt"] == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_db_pet_shares.py -v
```
Expected: `FAILED` — `AttributeError: module 'db' has no attribute 'get_pet_accessible'`

- [ ] **Step 3: Update `_format_pet` to include `is_shared`**

Replace the existing `_format_pet` (around line 401):

```python
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
```

- [ ] **Step 4: Update `get_all_pets` to UNION owned + shared**

Replace the existing `get_all_pets` function:

```python
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
```

- [ ] **Step 5: Add `get_pet_accessible` after `get_pet`**

Add after the existing `get_pet` function (around line 461):

```python
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
```

- [ ] **Step 6: Update `add_pet_share` to accept `role`**

Replace the existing `add_pet_share` function (or add it — it's new per v1 plan):

```python
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


def remove_pet_share(share_id, owner_user_id):
    """移除共同飼養人，回傳刪除筆數。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM pet_shares WHERE id = %s AND owner_user_id = %s",
                (share_id, owner_user_id),
            )
            return cur.rowcount
```

- [ ] **Step 7: Update `remove_pet` to cascade-delete shares**

In `remove_pet` (around line 484), add `DELETE FROM pet_shares WHERE pet_id = %s` before each `DELETE FROM pets` line in both branches:

```python
def remove_pet(pet_id, user_id=None):
    """刪除寵物，並清除相關商品/日記歸屬及共同飼養記錄。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute("UPDATE products SET pet_id = NULL WHERE pet_id = %s AND user_id = %s", (pet_id, user_id))
                cur.execute("UPDATE pet_diaries SET pet_id = NULL WHERE pet_id = %s AND user_id = %s", (pet_id, user_id))
                cur.execute("DELETE FROM pet_share_invitations WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pet_shares WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pets WHERE id = %s AND user_id = %s", (pet_id, user_id))
            else:
                cur.execute("UPDATE products SET pet_id = NULL WHERE pet_id = %s", (pet_id,))
                cur.execute("UPDATE pet_diaries SET pet_id = NULL WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pet_share_invitations WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pet_shares WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pets WHERE id = %s", (pet_id,))
```

- [ ] **Step 8: Run integration tests — should all pass**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_db_pet_shares.py -v
```
Expected: all 9 tests `PASSED`

- [ ] **Step 9: Run full non-e2e suite (regression check)**

```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v --ignore=tests/e2e
```
Expected: all `PASSED`

- [ ] **Step 10: Commit**

```bash
git add db.py tests/test_db_pet_shares.py
git commit -m "feat(db): pet access with role-based read/edit, cascade share deletion"
```

---

## Task 3: DB — Invitation CRUD Functions

**Files:**
- Modify: `db.py` (add 6 invitation functions after pet shares section); update `get_user_by_username` to return email

- [ ] **Step 1: Write failing integration tests**

Append to `tests/test_db_pet_shares.py`:

```python
import hashlib
from datetime import datetime, timedelta


def test_create_and_get_invitation_by_token(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("邀請毛孩", user_id=uid_a)
    raw_token = "testtoken_abc123"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires = datetime.utcnow() + timedelta(days=7)

    db.create_pet_share_invitation(
        pet_id=pet_id,
        inviter_user_id=uid_a,
        invitee_user_id=uid_b,
        role="editor",
        token_hash=token_hash,
        expires_at=expires,
    )
    inv = db.get_pet_share_invitation_by_token(token_hash)
    assert inv is not None
    assert inv["role"] == "editor"
    assert inv["status"] == "pending"


def test_accept_invitation_creates_share(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("邀請毛孩2", user_id=uid_a)
    raw_token = "testtoken_accept"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires = datetime.utcnow() + timedelta(days=7)

    db.create_pet_share_invitation(pet_id, uid_a, uid_b, "read_only", token_hash, expires)
    inv = db.get_pet_share_invitation_by_token(token_hash)

    result = db.accept_pet_share_invitation(inv["id"], invitee_user_id=uid_b)
    assert result is True

    shares = db.get_pet_shares(pet_id, owner_user_id=uid_a)
    assert any(s["shared_with_user_id"] == uid_b for s in shares)


def test_decline_invitation(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("邀請毛孩3", user_id=uid_a)
    raw_token = "testtoken_decline"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires = datetime.utcnow() + timedelta(days=7)

    db.create_pet_share_invitation(pet_id, uid_a, uid_b, "read_only", token_hash, expires)
    inv = db.get_pet_share_invitation_by_token(token_hash)
    db.decline_pet_share_invitation(inv["id"], invitee_user_id=uid_b)

    updated = db.get_pet_share_invitation_by_token(token_hash)
    assert updated["status"] == "declined"


def test_get_user_by_username_returns_email(two_users):
    uid_a, _ = two_users
    user = db.get_user_by_username("share_ta")
    assert user is not None
    assert "email" in user
    assert user["email"] == "share_ta@test.com"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_db_pet_shares.py -k "invitation or email" -v
```
Expected: `FAILED` — `AttributeError: module 'db' has no attribute 'create_pet_share_invitation'`

- [ ] **Step 3: Update `get_user_by_username` to return `email`**

In `get_user_by_username` (around line 168), change the SELECT:

```python
def get_user_by_username(username):
    """依 username 取得使用者，不存在則回傳 None。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, password_hash, created_at FROM users WHERE username = %s",
                (username,),
            )
            return cur.fetchone()
```

- [ ] **Step 4: Add invitation CRUD functions to `db.py`**

Add after the `# ========== Pet Shares ==========` section:

```python
# ========== Pet Share Invitations ==========


def create_pet_share_invitation(pet_id, inviter_user_id, invitee_user_id, role, token_hash, expires_at):
    """新增邀請記錄，回傳 id。若同一 pet+invitee 已有 pending 邀請，先取消舊的再建新的。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Cancel any existing pending invitation for this pet+invitee pair
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
    """接受邀請：建立 pet_shares 記錄並標記邀請為 accepted。回傳 True 成功。"""
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
            cur.execute(
                "UPDATE pet_share_invitations SET status = 'accepted' WHERE id = %s",
                (invitation_id,),
            )
            return True


def decline_pet_share_invitation(invitation_id, invitee_user_id):
    """婉拒邀請（需為受邀者）。回傳更新筆數。"""
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
                " i.role, i.expires_at, i.created_at"
                " FROM pet_share_invitations i"
                " JOIN users u ON u.id = i.invitee_user_id"
                " WHERE i.pet_id = %s AND i.inviter_user_id = %s AND i.status = 'pending'"
                " ORDER BY i.created_at ASC",
                (pet_id, inviter_user_id),
            )
            return cur.fetchall()


def cancel_pet_share_invitation(invitation_id, inviter_user_id):
    """取消邀請（需為邀請人）。回傳更新筆數。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE pet_share_invitations SET status = 'cancelled'"
                " WHERE id = %s AND inviter_user_id = %s AND status = 'pending'",
                (invitation_id, inviter_user_id),
            )
            return cur.rowcount
```

- [ ] **Step 5: Run invitation tests — should all pass**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_db_pet_shares.py -v
```
Expected: all 13 tests `PASSED`

- [ ] **Step 6: Commit**

```bash
git add db.py tests/test_db_pet_shares.py
git commit -m "feat(db): add invitation CRUD functions and fix get_user_by_username to return email"
```

---

## Task 4: API — Share List, Remove Share, Send Invitation, Cancel Invitation

**Files:**
- Modify: `app.py` (update `api_get_pet`, update `api_update_pet`, add share + invitation API routes, add `_send_pet_invite_email` helper)

- [ ] **Step 1: Write failing API tests**

Create `tests/test_api_pet_shares.py`:

```python
import pytest

_PET_OWNED = {
    "id": 1, "name": "毛球", "breed": "", "birthday": "",
    "photo_base64": "", "user_id": 1, "is_shared": False,
    "created_at": None, "updated_at": None,
}
_PET_SHARED = {**_PET_OWNED, "user_id": 2, "is_shared": True}


# ── GET /api/pets/<id> — accessible by shared user ───────────────────────

def test_get_pet_uses_accessible(authed_client, mock_db):
    mock_db.get_pet_accessible.return_value = _PET_SHARED
    res = authed_client.get("/api/pets/1")
    assert res.status_code == 200
    assert res.get_json()["is_shared"] is True


# ── PUT /api/pets/<id> — editor can update, read-only cannot ─────────────

def test_update_pet_editor_allowed(authed_client, mock_db):
    mock_db.get_pet_if_editable.return_value = _PET_SHARED
    mock_db.get_pet_accessible.return_value = _PET_SHARED
    res = authed_client.put("/api/pets/1", json={"name": "毛球改"})
    assert res.status_code == 200


def test_update_pet_read_only_returns_404(authed_client, mock_db):
    mock_db.get_pet_if_editable.return_value = None
    res = authed_client.put("/api/pets/1", json={"name": "毛球改"})
    assert res.status_code == 404


# ── GET /api/pets/<id>/shares ─────────────────────────────────────────────

def test_get_shares_returns_list(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_pet_shares.return_value = [
        {"id": 10, "shared_with_user_id": 2, "username": "alice", "role": "editor"}
    ]
    res = authed_client.get("/api/pets/1/shares")
    assert res.status_code == 200
    assert res.get_json()["shares"][0]["role"] == "editor"


def test_get_shares_non_owner_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = None
    res = authed_client.get("/api/pets/1/shares")
    assert res.status_code == 404


# ── DELETE /api/pets/<id>/shares/<share_id> ──────────────────────────────

def test_remove_share_success(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.remove_pet_share.return_value = 1
    res = authed_client.delete("/api/pets/1/shares/10")
    assert res.status_code == 204


def test_remove_share_not_found_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.remove_pet_share.return_value = 0
    res = authed_client.delete("/api/pets/1/shares/10")
    assert res.status_code == 404


# ── POST /api/pets/<id>/invitations ──────────────────────────────────────

def test_send_invitation_success(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_user_by_username.return_value = {"id": 2, "username": "alice", "email": "alice@test.com"}
    mock_db.create_pet_share_invitation.return_value = 5
    res = authed_client.post("/api/pets/1/invitations", json={"username": "alice", "role": "read_only"})
    assert res.status_code == 201
    assert res.get_json()["invitee_username"] == "alice"


def test_send_invitation_no_email_returns_400(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_user_by_username.return_value = {"id": 2, "username": "alice", "email": None}
    res = authed_client.post("/api/pets/1/invitations", json={"username": "alice", "role": "read_only"})
    assert res.status_code == 400


def test_send_invitation_invalid_role_returns_400(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_user_by_username.return_value = {"id": 2, "username": "alice", "email": "alice@test.com"}
    res = authed_client.post("/api/pets/1/invitations", json={"username": "alice", "role": "superadmin"})
    assert res.status_code == 400


def test_send_invitation_self_returns_400(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_user_by_username.return_value = {"id": 1, "username": "me", "email": "me@test.com"}
    res = authed_client.post("/api/pets/1/invitations", json={"username": "me", "role": "read_only"})
    assert res.status_code == 400


def test_send_invitation_non_owner_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = None
    res = authed_client.post("/api/pets/1/invitations", json={"username": "alice", "role": "read_only"})
    assert res.status_code == 404


# ── GET /api/pets/<id>/invitations ────────────────────────────────────────

def test_list_invitations(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.get_pet_invitations_for_pet.return_value = [
        {"id": 7, "invitee_username": "alice", "role": "read_only", "expires_at": None, "created_at": None}
    ]
    res = authed_client.get("/api/pets/1/invitations")
    assert res.status_code == 200
    assert len(res.get_json()["invitations"]) == 1


# ── DELETE /api/pets/<id>/invitations/<inv_id> ───────────────────────────

def test_cancel_invitation_success(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.cancel_pet_share_invitation.return_value = 1
    res = authed_client.delete("/api/pets/1/invitations/7")
    assert res.status_code == 204


def test_cancel_invitation_not_found_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_OWNED
    mock_db.cancel_pet_share_invitation.return_value = 0
    res = authed_client.delete("/api/pets/1/invitations/7")
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_api_pet_shares.py -v
```
Expected: many `FAILED` — routes not yet defined, `api_get_pet` still calls `get_pet` not `get_pet_accessible`

- [ ] **Step 3: Update `api_get_pet` to use `get_pet_accessible`**

In `app.py`, find `api_get_pet` (around line 483):

```python
@app.route("/api/pets/<int:pet_id>", methods=["GET"])
def api_get_pet(pet_id):
    """取得單一寵物（擁有者或共同飼養人均可讀取）"""
    pet = db.get_pet_accessible(pet_id, user_id=current_user_id())
    if not pet:
        return jsonify({"error": "找不到寵物"}), 404
    return jsonify(pet)
```

- [ ] **Step 4: Update `api_update_pet` to allow editors**

In `app.py`, find `api_update_pet` (around line 492):

```python
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
        user_id=None,  # access already verified by get_pet_if_editable above
    )
    return jsonify(db.get_pet_accessible(pet_id, user_id=uid))
```

- [ ] **Step 5: Add `_send_pet_invite_email` helper to `app.py`**

Add near the other email helper `_send_password_reset_email` (around line 261):

```python
_ROLE_DISPLAY = {"read_only": "僅能檢視", "editor": "可編輯"}


def _send_pet_invite_email(invitee_email: str, inviter_username: str, pet_name: str,
                           role: str, join_url: str, inviter_user_id: int) -> None:
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
    except Exception:
        logger.warning(
            "Failed to send pet invite email (inviter_user_id=%s).",
            inviter_user_id,
            exc_info=True,
        )
```

- [ ] **Step 6: Add share + invitation API routes to `app.py`**

Add after `pets_page` route (around line 527), before `# ========== Products API ==========`:

```python
# ========== Pet Shares API ==========


@app.route("/api/pets/<int:pet_id>/shares", methods=["GET"])
def api_get_pet_shares(pet_id):
    """列出共同飼養人及其角色（擁有者可查）"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物或無權限"}), 404
    shares = db.get_pet_shares(pet_id, owner_user_id=uid)
    return jsonify({
        "shares": [
            {"id": s["id"], "username": s["username"],
             "shared_with_user_id": s["shared_with_user_id"], "role": s["role"]}
            for s in shares
        ]
    })


@app.route("/api/pets/<int:pet_id>/shares/<int:share_id>", methods=["DELETE"])
def api_remove_pet_share(pet_id, share_id):
    """移除共同飼養人（擁有者操作）"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物或無權限"}), 404
    if not db.remove_pet_share(share_id, owner_user_id=uid):
        return jsonify({"error": "找不到分享記錄"}), 404
    return "", 204


# ========== Pet Invitations API ==========

_VALID_ROLES = {"read_only", "editor"}


@app.route("/api/pets/<int:pet_id>/invitations", methods=["GET"])
def api_get_pet_invitations(pet_id):
    """列出待確認的邀請（擁有者可查）"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物或無權限"}), 404
    invs = db.get_pet_invitations_for_pet(pet_id, inviter_user_id=uid)
    return jsonify({
        "invitations": [
            {"id": i["id"], "invitee_username": i["invitee_username"],
             "role": i["role"], "expires_at": str(i["expires_at"]) if i.get("expires_at") else None}
            for i in invs
        ]
    })


@app.route("/api/pets/<int:pet_id>/invitations", methods=["POST"])
def api_send_pet_invitation(pet_id):
    """發送邀請（擁有者操作）：建立邀請記錄並寄送 Email"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物或無權限"}), 404
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    role = (data.get("role") or "").strip()
    if not username:
        return jsonify({"error": "請輸入帳號"}), 400
    if role not in _VALID_ROLES:
        return jsonify({"error": "無效的角色，請選擇 read_only 或 editor"}), 400
    target = db.get_user_by_username(username)
    if not target:
        return jsonify({"error": "找不到此帳號"}), 404
    if target["id"] == uid:
        return jsonify({"error": "無法邀請自己"}), 400
    if not target.get("email"):
        return jsonify({"error": "此帳號未設定電子信箱，無法發送邀請"}), 400
    inviter = db.get_user_by_id(uid)
    pet = db.get_pet(pet_id, user_id=uid)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = _utcnow_naive() + timedelta(days=7)
    inv_id = db.create_pet_share_invitation(
        pet_id=pet_id,
        inviter_user_id=uid,
        invitee_user_id=target["id"],
        role=role,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    join_url = url_for("pet_join_page", token=raw_token, _external=True)
    _send_pet_invite_email(
        invitee_email=target["email"],
        inviter_username=inviter["username"],
        pet_name=pet["name"],
        role=role,
        join_url=join_url,
        inviter_user_id=uid,
    )
    return jsonify({"id": inv_id, "invitee_username": username, "role": role}), 201


@app.route("/api/pets/<int:pet_id>/invitations/<int:inv_id>", methods=["DELETE"])
def api_cancel_pet_invitation(pet_id, inv_id):
    """取消邀請（擁有者操作）"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物或無權限"}), 404
    if not db.cancel_pet_share_invitation(inv_id, inviter_user_id=uid):
        return jsonify({"error": "找不到邀請記錄"}), 404
    return "", 204
```

- [ ] **Step 7: Run API tests — should all pass**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_api_pet_shares.py -v
```
Expected: all `PASSED`

- [ ] **Step 8: Run full non-e2e suite**

```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v --ignore=tests/e2e
```
Expected: all `PASSED`

- [ ] **Step 9: Commit**

```bash
git add app.py tests/test_api_pet_shares.py
git commit -m "feat(api): pet share list/remove + invitation send/list/cancel, editor can edit pet"
```

---

## Task 5: App — Accept/Decline Invitation Page + Login `next` Redirect

**Files:**
- Modify: `app.py` (`_require_login`, `login` POST handler); `templates/login.html` (pass `next` in fetch body); Create: `templates/pet_join.html`

- [ ] **Step 1: Write failing tests**

Create `tests/test_api_pet_join.py`:

```python
import pytest
import hashlib
from datetime import datetime, timedelta


def _make_inv(status="pending", invitee_id=1):
    return {
        "id": 99,
        "pet_id": 1,
        "inviter_user_id": 2,
        "invitee_user_id": invitee_id,
        "role": "read_only",
        "status": status,
        "expires_at": datetime.utcnow() + timedelta(days=7),
        "inviter_username": "bob",
        "pet_name": "毛球",
    }


def test_join_page_requires_login(client, mock_db):
    mock_db.get_pet_share_invitation_by_token.return_value = _make_inv()
    res = client.get("/pets/join/sometoken")
    # Should redirect to login (not 200 or 404)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_join_page_shows_invitation_when_logged_in(authed_client, mock_db):
    mock_db.get_pet_share_invitation_by_token.return_value = _make_inv(invitee_id=1)
    res = authed_client.get("/pets/join/sometoken")
    assert res.status_code == 200
    assert "毛球" in res.get_data(as_text=True)


def test_join_page_wrong_user_shows_error(authed_client, mock_db):
    # authed_client is user_id=1; invitation is for user_id=99
    mock_db.get_pet_share_invitation_by_token.return_value = _make_inv(invitee_id=99)
    res = authed_client.get("/pets/join/sometoken")
    assert res.status_code == 200
    assert "不屬於您" in res.get_data(as_text=True)


def test_accept_invitation(authed_client, mock_db):
    mock_db.get_pet_share_invitation_by_token.return_value = _make_inv(invitee_id=1)
    mock_db.accept_pet_share_invitation.return_value = True
    res = authed_client.post("/pets/join/sometoken", data={"action": "accept", "csrf_token": "x"})
    # Redirects after accept — we just need not 500
    assert res.status_code in (302, 200)


def test_decline_invitation(authed_client, mock_db):
    mock_db.get_pet_share_invitation_by_token.return_value = _make_inv(invitee_id=1)
    mock_db.decline_pet_share_invitation.return_value = 1
    res = authed_client.post("/pets/join/sometoken", data={"action": "decline", "csrf_token": "x"})
    assert res.status_code in (302, 200)


def test_login_preserves_next_url(client, mock_db):
    """_require_login should append ?next= when redirecting unauthenticated users."""
    res = client.get("/pets/join/sometoken")
    assert res.status_code == 302
    assert "next=" in res.headers["Location"]
```

> **Note on CSRF for join page:** The POST `/pets/join/<token>` uses a standard HTML form with CSRF. The `authed_client` test bypasses this by patching `_validate_csrf_token` via mock_db. To make tests pass without a real CSRF token, patch `app._validate_csrf_token` to return `True` in the test, or skip CSRF validation in TEST mode. Add this to the test file:
>
> ```python
> from unittest.mock import patch
>
> def test_accept_invitation(authed_client, mock_db):
>     mock_db.get_pet_share_invitation_by_token.return_value = _make_inv(invitee_id=1)
>     mock_db.accept_pet_share_invitation.return_value = True
>     with patch("app._validate_csrf_token", return_value=True):
>         res = authed_client.post("/pets/join/sometoken", data={"action": "accept"})
>     assert res.status_code in (302, 200)
>
> def test_decline_invitation(authed_client, mock_db):
>     mock_db.get_pet_share_invitation_by_token.return_value = _make_inv(invitee_id=1)
>     mock_db.decline_pet_share_invitation.return_value = 1
>     with patch("app._validate_csrf_token", return_value=True):
>         res = authed_client.post("/pets/join/sometoken", data={"action": "decline"})
>     assert res.status_code in (302, 200)
> ```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_api_pet_join.py -v
```
Expected: `FAILED` — `404` on `/pets/join/...` routes don't exist yet

- [ ] **Step 3: Update `_require_login` to preserve `next` URL**

In `app.py`, find `_require_login` (around line 135):

```python
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
```

- [ ] **Step 4: Update `login` POST to use `next`**

In `app.py`, find the `login` route POST handler (around line 152). Change the successful-login return block:

```python
# Find the "session["user_id"] = user["id"]" line, then replace the return below it:
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
```

- [ ] **Step 5: Update `login.html` to pass `next` in fetch body**

In `templates/login.html`, find the fetch body inside the submit handler (around line 70):

```javascript
body: JSON.stringify({
    username: loginForm.username.value.trim(),
    password: loginForm.password.value,
    csrf_token: csrfInput.value,
    next: new URLSearchParams(window.location.search).get('next') || '',
}),
```

- [ ] **Step 6: Add pet join routes to `app.py`**

Add after the `# ========== Pet Invitations API ==========` section (before Products API):

```python
# ========== Pet Join (invitation acceptance) ==========

_INVITE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def _get_valid_invitation(token):
    """Validate raw token, return (invitation_record, error_message)."""
    if not _INVITE_TOKEN_RE.fullmatch(token or ""):
        return None, "邀請連結無效"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return db.get_pet_share_invitation_by_token(token_hash), None


@app.route("/pets/join/<token>")
def pet_join_page(token):
    """顯示邀請詳情，讓受邀者選擇接受或婉拒。"""
    inv, err = _get_valid_invitation(token)
    if err or not inv:
        return render_template("pet_join.html", error="邀請連結無效或已過期",
                               csrf_token=_issue_csrf_token("pet_join"))
    uid = current_user_id()
    if inv["invitee_user_id"] != uid:
        return render_template("pet_join.html", error="此邀請不屬於您的帳號",
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
    inv, _ = _get_valid_invitation(token)
    if not inv or inv["invitee_user_id"] != uid or inv["status"] != "pending":
        flash("邀請連結無效或已過期")
        return redirect(url_for("index"))
    action = (request.form.get("action") or "").strip()
    if action == "accept":
        db.accept_pet_share_invitation(inv["id"], invitee_user_id=uid)
        flash(f"已加入「{inv['pet_name']}」的共同飼養人！")
        return redirect(url_for("pets_page"))
    elif action == "decline":
        db.decline_pet_share_invitation(inv["id"], invitee_user_id=uid)
        flash("已婉拒邀請")
        return redirect(url_for("index"))
    return redirect(url_for("pet_join_page", token=token))
```

- [ ] **Step 7: Create `templates/pet_join.html`**

```html
{% extends "base.html" %}

{% block title %}接受共同飼養邀請 - Pet Adorable Life{% endblock %}

{% block content %}
<div class="auth-page">
    <div class="auth-card">
        <h1 class="auth-title">🐾 共同飼養邀請</h1>

        {% with messages = get_flashed_messages() %}
        {% if messages %}
        <ul class="auth-errors">{% for msg in messages %}<li>{{ msg }}</li>{% endfor %}</ul>
        {% endif %}
        {% endwith %}

        {% if error %}
        <p style="color:var(--danger,#e74c3c);text-align:center">{{ error }}</p>
        <p style="text-align:center"><a href="/" class="btn btn-secondary">回首頁</a></p>
        {% elif invitation %}
        <p style="text-align:center;margin:.5rem 0">
            <strong>{{ invitation.inviter_username }}</strong> 邀請您以
            「<strong>{{ role_display }}</strong>」身份共同飼養
            <strong>{{ invitation.pet_name }}</strong>。
        </p>
        <form method="POST" action="/pets/join/{{ token }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
            <div class="form-actions" style="justify-content:center;gap:1rem;margin-top:1.5rem">
                <button type="submit" name="action" value="accept" class="btn btn-primary">接受邀請</button>
                <button type="submit" name="action" value="decline" class="btn btn-secondary">婉拒</button>
            </div>
        </form>
        {% endif %}
    </div>
</div>
{% endblock %}
```

- [ ] **Step 8: Run join page tests — should all pass**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_api_pet_join.py -v
```
Expected: all `PASSED`

- [ ] **Step 9: Run full non-e2e suite**

```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v --ignore=tests/e2e
```
Expected: all `PASSED`

- [ ] **Step 10: Commit**

```bash
git add app.py templates/login.html templates/pet_join.html tests/test_api_pet_join.py
git commit -m "feat: pet join page with accept/decline, login next-URL redirect"
```

---

## Task 6: Frontend — Updated Share Dialog in `pets.html`

**Files:**
- Modify: `templates/pets.html`

No automated tests — manual smoke test steps below.

- [ ] **Step 1: Add share dialog HTML (replace existing edit dialog comment block)**

After the closing `</div>` of the edit dialog (around line 71), add:

```html
<!-- Share dialog -->
<div id="shareDialog" class="hidden modal-overlay">
    <div class="modal-content">
        <h2>👥 共同飼養管理</h2>
        <input type="hidden" id="sharePetId">

        <h3 style="font-size:.9rem;margin:.75rem 0 .25rem">共同飼養人</h3>
        <div id="sharesList"><div class="spinner"></div></div>

        <h3 style="font-size:.9rem;margin:1rem 0 .25rem">待確認邀請</h3>
        <div id="invitesList"><div class="spinner"></div></div>

        <h3 style="font-size:.9rem;margin:1rem 0 .25rem">新增共同飼養人</h3>
        <div class="form-group">
            <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center">
                <input type="text" id="shareUsername" placeholder="帳號名稱" maxlength="100" style="flex:1;min-width:120px">
                <select id="shareRole" style="flex:0 0 auto">
                    <option value="read_only">僅能檢視</option>
                    <option value="editor">可編輯</option>
                </select>
                <button type="button" class="btn btn-primary" id="btnSendInvite">發送邀請</button>
            </div>
            <p id="shareError" class="hidden" style="color:var(--danger,#e74c3c);margin:.25rem 0 0;font-size:.85rem"></p>
            <p id="shareSuccess" class="hidden" style="color:var(--success,#27ae60);margin:.25rem 0 0;font-size:.85rem"></p>
        </div>

        <div class="form-actions" style="margin-top:1rem">
            <button type="button" class="btn btn-secondary" id="btnCloseShare">關閉</button>
        </div>
    </div>
</div>
```

- [ ] **Step 2: Update `renderPets` to add share button and shared badge**

In the JS section, replace the existing `renderPets` function:

```javascript
function renderPets(pets) {
    if (!pets.length) {
        petsList.innerHTML = '<div class="empty-state"><span class="empty-icon">🐾</span><p>尚無寵物，點擊「➕ 新增寵物」建立第一個寵物檔案</p></div>';
        return;
    }
    petsList.innerHTML = '<div class="pets-grid">' +
        pets.map(p => `
        <article class="pet-card" data-id="${escapeHtml(p.id)}">
            <div class="pet-card-actions">
                ${p.is_shared
                    ? `<span class="pet-shared-badge" title="由他人共享">👥 共享</span>`
                    : `<button class="btn-icon btn-share-pet" data-id="${escapeHtml(p.id)}" title="共同飼養管理">👥</button>
                       <button class="btn-icon edit btn-edit-pet" data-id="${escapeHtml(p.id)}" title="編輯">✎</button>
                       <button class="btn-icon remove btn-remove-pet" data-id="${escapeHtml(p.id)}" title="刪除">✕</button>`
                }
            </div>
            <div class="pet-card-avatar">
                ${p.photo_base64
                    ? `<img src="${escapeHtml(p.photo_base64)}" alt="${escapeHtml(p.name)}">`
                    : '🐾'}
            </div>
            <div class="pet-card-info">
                <div class="pet-card-name">${escapeHtml(p.name)}</div>
                ${p.breed ? `<div class="pet-card-meta">${escapeHtml(p.breed)}</div>` : ''}
                ${p.birthday ? `<div class="pet-card-meta">${calcAge(p.birthday)}</div>` : ''}
            </div>
        </article>`).join('') +
    '</div>';

    petsList.querySelectorAll('.btn-edit-pet').forEach(btn => {
        btn.addEventListener('click', () => openEdit(pets.find(p => p.id == btn.dataset.id)));
    });
    petsList.querySelectorAll('.btn-remove-pet').forEach(btn => {
        btn.addEventListener('click', () => deletePet(parseInt(btn.dataset.id)));
    });
    petsList.querySelectorAll('.btn-share-pet').forEach(btn => {
        btn.addEventListener('click', () => openShare(parseInt(btn.dataset.id)));
    });
}
```

- [ ] **Step 3: Add share dialog JS functions**

After the `deletePet` function (around line 235), before `loadPets();`, add:

```javascript
    // ---- Share / Invite dialog ----

    const shareDialog = document.getElementById('shareDialog');
    const sharesList  = document.getElementById('sharesList');
    const invitesList = document.getElementById('invitesList');
    const shareUsername = document.getElementById('shareUsername');
    const shareRole     = document.getElementById('shareRole');
    const shareError    = document.getElementById('shareError');
    const shareSuccess  = document.getElementById('shareSuccess');
    const btnSendInvite = document.getElementById('btnSendInvite');
    const btnCloseShare = document.getElementById('btnCloseShare');

    const ROLE_LABEL = { read_only: '僅能檢視', editor: '可編輯' };

    function showShareMsg(el, msg) {
        shareError.classList.add('hidden');
        shareSuccess.classList.add('hidden');
        el.textContent = msg;
        el.classList.remove('hidden');
    }

    async function openShare(petId) {
        document.getElementById('sharePetId').value = petId;
        shareUsername.value = '';
        shareError.classList.add('hidden');
        shareSuccess.classList.add('hidden');
        shareDialog.classList.remove('hidden');
        await Promise.all([loadShares(petId), loadInvites(petId)]);
    }

    async function loadShares(petId) {
        sharesList.innerHTML = '<div class="spinner"></div>';
        try {
            const res = await fetch(`/api/pets/${petId}/shares`);
            const data = await res.json();
            renderShares(petId, data.shares || []);
        } catch { sharesList.innerHTML = '<p>載入失敗</p>'; }
    }

    function renderShares(petId, shares) {
        if (!shares.length) {
            sharesList.innerHTML = '<p style="color:var(--text-muted,#888);font-size:.85rem">尚無共同飼養人</p>';
            return;
        }
        sharesList.innerHTML = shares.map(s => `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:.2rem 0">
                <span>👤 ${escapeHtml(s.username)} <small style="color:#888">(${escapeHtml(ROLE_LABEL[s.role] || s.role)})</small></span>
                <button class="btn-icon remove btn-rm-share" data-sid="${escapeHtml(s.id)}" data-pid="${escapeHtml(petId)}" title="移除">✕</button>
            </div>`).join('');
        sharesList.querySelectorAll('.btn-rm-share').forEach(btn => {
            btn.addEventListener('click', async () => {
                const r = await fetch(`/api/pets/${btn.dataset.pid}/shares/${btn.dataset.sid}`, { method: 'DELETE' });
                if (r.ok) await loadShares(parseInt(btn.dataset.pid));
                else showShareMsg(shareError, '移除失敗');
            });
        });
    }

    async function loadInvites(petId) {
        invitesList.innerHTML = '<div class="spinner"></div>';
        try {
            const res = await fetch(`/api/pets/${petId}/invitations`);
            const data = await res.json();
            renderInvites(petId, data.invitations || []);
        } catch { invitesList.innerHTML = '<p>載入失敗</p>'; }
    }

    function renderInvites(petId, invitations) {
        if (!invitations.length) {
            invitesList.innerHTML = '<p style="color:var(--text-muted,#888);font-size:.85rem">無待確認邀請</p>';
            return;
        }
        invitesList.innerHTML = invitations.map(i => `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:.2rem 0">
                <span>📧 ${escapeHtml(i.invitee_username)} <small style="color:#888">(${escapeHtml(ROLE_LABEL[i.role] || i.role)}，待確認)</small></span>
                <button class="btn-icon remove btn-cancel-invite" data-iid="${escapeHtml(i.id)}" data-pid="${escapeHtml(petId)}" title="取消">✕</button>
            </div>`).join('');
        invitesList.querySelectorAll('.btn-cancel-invite').forEach(btn => {
            btn.addEventListener('click', async () => {
                const r = await fetch(`/api/pets/${btn.dataset.pid}/invitations/${btn.dataset.iid}`, { method: 'DELETE' });
                if (r.ok) await loadInvites(parseInt(btn.dataset.pid));
                else showShareMsg(shareError, '取消失敗');
            });
        });
    }

    btnSendInvite.addEventListener('click', async () => {
        const petId = parseInt(document.getElementById('sharePetId').value);
        const username = shareUsername.value.trim();
        const role = shareRole.value;
        shareError.classList.add('hidden');
        shareSuccess.classList.add('hidden');
        if (!username) { showShareMsg(shareError, '請輸入帳號名稱'); return; }
        try {
            const res = await fetch(`/api/pets/${petId}/invitations`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, role }),
            });
            const data = await res.json();
            if (res.ok) {
                shareUsername.value = '';
                showShareMsg(shareSuccess, `邀請已發送至 ${data.invitee_username} 的信箱`);
                await loadInvites(petId);
            } else {
                showShareMsg(shareError, data.error || '發送失敗');
            }
        } catch { showShareMsg(shareError, '操作失敗，請稍後再試'); }
    });

    btnCloseShare.addEventListener('click', () => { shareDialog.classList.add('hidden'); });
    shareDialog.addEventListener('click', e => { if (e.target === shareDialog) shareDialog.classList.add('hidden'); });
```

- [ ] **Step 4: Add CSS for share badge**

In `templates/pets.html`, add inside a `<style>` block before `{% endblock %}`:

```html
<style>
.pet-shared-badge {
    font-size: .72rem;
    color: var(--primary, #6b7ae8);
    padding: .1rem .35rem;
    border: 1px solid var(--primary, #6b7ae8);
    border-radius: 999px;
    white-space: nowrap;
}
</style>
```

- [ ] **Step 5: Manual smoke test**

1. Register two accounts: `user_a` (with email set) and `user_b` (with email set)
2. Log in as `user_a`, go to `/pets`, create a pet "毛球"
3. Click 👥 on the pet — dialog opens showing empty lists
4. Enter `user_b`, select "可編輯", click "發送邀請" — success message appears; check email or DB
5. Log out, open the join link (check DB: `SELECT token_hash FROM pet_share_invitations`) → `http://localhost:5001/pets/join/<raw_token>`
6. Should redirect to login with `?next=/pets/join/<token>` — log in as `user_b`
7. Should land on `/pets/join/<token>` showing accept/decline buttons
8. Click "接受邀請" — redirected to `/pets` with flash message; "毛球" appears with "👥 共享" badge
9. Log in as `user_a`, open share dialog for "毛球" — `user_b` listed as co-owner with "(可編輯)"

- [ ] **Step 6: Commit**

```bash
git add templates/pets.html
git commit -m "feat(ui): share dialog with role selector, invite flow, pending invites list"
```

---

## Task 7: Final Regression Check

- [ ] **Step 1: Run all non-e2e tests**

```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v --ignore=tests/e2e
```
Expected: all `PASSED`

- [ ] **Step 2: Commit any fixes**

```bash
git add -p
git commit -m "fix: address regressions from shared pets v2"
```

---

## Summary of New/Changed API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/pets/<id>/shares` | Owner | List active co-owners (with roles) |
| `DELETE` | `/api/pets/<id>/shares/<share_id>` | Owner | Remove co-owner |
| `GET` | `/api/pets/<id>/invitations` | Owner | List pending invitations |
| `POST` | `/api/pets/<id>/invitations` | Owner | Send email invitation (body: `{username, role}`) |
| `DELETE` | `/api/pets/<id>/invitations/<inv_id>` | Owner | Cancel invitation |
| `GET` | `/pets/join/<token>` | Invitee (logged in) | Show accept/decline page |
| `POST` | `/pets/join/<token>` | Invitee (logged in) | Submit accept or decline |

**Updated existing endpoints:**
- `GET /api/pets/<id>` — now accessible by any co-owner (uses `get_pet_accessible`)
- `PUT /api/pets/<id>` — now accessible by owner + editor co-owners (uses `get_pet_if_editable`)
- `GET /login` — now preserves `?next=` URL after successful login

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | ISSUES_OPEN | 3 critical gaps, 5 deferred to TODOS.md |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | ISSUES_FOUND | 8 issues (outside voice, claude subagent) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 2 decisions resolved, 10 test gaps mapped |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |

**CROSS-MODEL:** Outside voice (Claude subagent) found 8 issues the primary CEO review missed: remove_pet orphans co-owner content, registration ?next= broken for new users, INSERT IGNORE misleading return. All captured and confirmed by Eng Review.

**UNRESOLVED:** 0 unresolved decisions

**VERDICT:** CEO + ENG CLEARED — ready to implement. 6 fixes confirmed with implementation approach. 9 test specs written. Run /ship when fixes are done.
