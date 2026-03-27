# 共同寵物 (Shared Pets) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow a pet owner to share their pet with another registered user by username; the shared user sees the pet in their own pet list (read-only).

**Architecture:** A new `pet_shares` join table records (pet_id, owner_user_id, shared_with_user_id). `get_all_pets` is updated to UNION owned + shared pets. A new `get_pet_accessible` function allows read access by owner or sharer. Three new REST endpoints manage shares. The pets page gains a share dialog (👥 button per owned pet card).

**Tech Stack:** Python Flask, PyMySQL, MySQL 8, Vanilla JS (no build step), pytest with `mock_db` fixture.

---

## File Map

| File | Change |
|------|--------|
| `db.py` | Add `_init_pet_shares_table`, `add_pet_share`, `get_pet_shares`, `remove_pet_share`, `get_pet_accessible`; update `get_all_pets`, `_format_pet`, `remove_pet`, `init_db` |
| `app.py` | Add `api_get_pet_shares`, `api_add_pet_share`, `api_remove_pet_share`; update `api_get_pet` to use `get_pet_accessible` |
| `templates/pets.html` | Add share button on owned pet cards, share badge on shared pet cards, share management dialog + JS |
| `tests/test_api_pet_shares.py` | New file: API-level tests using `authed_client` + `mock_db` |

---

## Task 1: DB — `pet_shares` table + basic CRUD

**Files:**
- Modify: `db.py` (functions: `_init_pet_shares_table`, `add_pet_share`, `get_pet_shares`, `remove_pet_share`, `init_db`)

- [ ] **Step 1: Write failing DB schema test**

In `tests/test_db_schema.py` (already exists — add to the bottom), using the same mock pattern as `test_init_db_creates_pets_table`:

```python
def test_init_db_creates_pet_shares_table():
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
    assert any("CREATE TABLE IF NOT EXISTS pet_shares" in sql for sql in all_sql), \
        "Expected CREATE TABLE IF NOT EXISTS pet_shares in SQL calls"
    assert any("shared_with_user_id" in sql for sql in all_sql), \
        "Expected shared_with_user_id column in SQL calls"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_db_schema.py -k "pet_shares" -v
```
Expected: `FAILED` — AssertionError `Expected CREATE TABLE IF NOT EXISTS pet_shares`

- [ ] **Step 3: Add `_init_pet_shares_table` to `db.py`**

Add after `_init_password_reset_tokens_table` (around line 128):

```python
def _init_pet_shares_table(cur):
    """建立 pet_shares 表（共同飼養人）。"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pet_shares (
            id INT AUTO_INCREMENT PRIMARY KEY,
            pet_id INT NOT NULL,
            owner_user_id INT NOT NULL,
            shared_with_user_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_pet_shared (pet_id, shared_with_user_id),
            INDEX idx_shared_with (shared_with_user_id)
        )
    """)
```

- [ ] **Step 4: Call it from `init_db`**

In `init_db()` (around line 140), add after `_apply_relationship_columns(cur)`:

```python
_init_pet_shares_table(cur)
```

- [ ] **Step 5: Add share CRUD functions to `db.py`**

Add at the bottom of the `# ========== Pets ==========` section (after `remove_pet`):

```python
# ========== Pet Shares ==========


def add_pet_share(pet_id, owner_user_id, shared_with_user_id):
    """新增共同飼養人記錄，回傳 share id。重複時拋出 IntegrityError。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pet_shares (pet_id, owner_user_id, shared_with_user_id)"
                " VALUES (%s, %s, %s)",
                (pet_id, owner_user_id, shared_with_user_id),
            )
            return cur.lastrowid


def get_pet_shares(pet_id, owner_user_id):
    """列出某寵物的所有共同飼養人（僅擁有者可查）。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.id, s.shared_with_user_id, u.username"
                " FROM pet_shares s JOIN users u ON u.id = s.shared_with_user_id"
                " WHERE s.pet_id = %s AND s.owner_user_id = %s"
                " ORDER BY s.created_at ASC",
                (pet_id, owner_user_id),
            )
            return cur.fetchall()


def remove_pet_share(share_id, owner_user_id):
    """移除共同飼養人記錄，回傳刪除筆數（0 表示不存在或無權限）。"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM pet_shares WHERE id = %s AND owner_user_id = %s",
                (share_id, owner_user_id),
            )
            return cur.rowcount
```

- [ ] **Step 6: Run the schema test — should pass now**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_db_schema.py -k "pet_shares" -v
```
Expected: `PASSED`

- [ ] **Step 7: Commit**

```bash
git add db.py tests/test_db_schema.py
git commit -m "feat(db): add pet_shares table and share CRUD functions"
```

---

## Task 2: DB — Update `get_all_pets` and add `get_pet_accessible`

**Files:**
- Modify: `db.py` (functions: `_format_pet`, `get_all_pets`, `remove_pet`, new: `get_pet_accessible`)

- [ ] **Step 1: Write failing tests**

Create `tests/test_db_pet_shares.py`:

> **Note:** These are integration tests that require the Docker container running with a real DB. Run with `docker exec`.

```python
"""
Integration tests for pet share DB functions.
Requires: docker-compose up -d mysql && docker exec pet-adorable-life-web python -m pytest tests/test_db_pet_shares.py -v
"""
import pytest
import db


@pytest.fixture(autouse=True)
def clean_db():
    """每個測試前後清除測試資料。"""
    # Create two test users
    uid_a = db.create_user("share_test_a", "share_a@test.com", "hashed_pw_a")
    uid_b = db.create_user("share_test_b", "share_b@test.com", "hashed_pw_b")
    yield uid_a, uid_b
    # Cleanup
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pet_shares WHERE owner_user_id IN (%s, %s)", (uid_a, uid_b))
            cur.execute("DELETE FROM pets WHERE user_id IN (%s, %s)", (uid_a, uid_b))
            cur.execute("DELETE FROM users WHERE id IN (%s, %s)", (uid_a, uid_b))


def test_get_all_pets_includes_shared(clean_db):
    uid_a, uid_b = clean_db
    pet_id = db.add_pet("共享毛孩", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b)

    pets_b = db.get_all_pets(user_id=uid_b)
    ids = [p["id"] for p in pets_b]
    assert pet_id in ids


def test_shared_pet_has_is_shared_flag(clean_db):
    uid_a, uid_b = clean_db
    pet_id = db.add_pet("共享毛孩", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b)

    pets_b = db.get_all_pets(user_id=uid_b)
    shared = next(p for p in pets_b if p["id"] == pet_id)
    assert shared["is_shared"] is True


def test_owned_pet_is_not_marked_shared(clean_db):
    uid_a, uid_b = clean_db
    pet_id = db.add_pet("自己的毛孩", user_id=uid_a)

    pets_a = db.get_all_pets(user_id=uid_a)
    owned = next(p for p in pets_a if p["id"] == pet_id)
    assert owned["is_shared"] is False


def test_get_pet_accessible_by_shared_user(clean_db):
    uid_a, uid_b = clean_db
    pet_id = db.add_pet("共享毛孩", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b)

    pet = db.get_pet_accessible(pet_id, user_id=uid_b)
    assert pet is not None
    assert pet["id"] == pet_id
    assert pet["is_shared"] is True


def test_get_pet_accessible_returns_none_for_stranger(clean_db):
    uid_a, uid_b = clean_db
    pet_id = db.add_pet("私有毛孩", user_id=uid_a)

    pet = db.get_pet_accessible(pet_id, user_id=uid_b)
    assert pet is None


def test_remove_pet_also_removes_shares(clean_db):
    uid_a, uid_b = clean_db
    pet_id = db.add_pet("要刪除的毛孩", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b)

    db.remove_pet(pet_id, user_id=uid_a)

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM pet_shares WHERE pet_id = %s", (pet_id,))
            row = cur.fetchone()
    assert row["cnt"] == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_db_pet_shares.py -v
```
Expected: `FAILED` — `AttributeError: module 'db' has no attribute 'get_pet_accessible'`

- [ ] **Step 3: Update `_format_pet` to include `is_shared`**

Replace the existing `_format_pet` in `db.py` (around line 401):

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

Replace the `if user_id is not None:` branch in `get_all_pets` (around line 418):

```python
def get_all_pets(user_id=None):
    """取得所有寵物，依建立時間升序。user_id 時包含共享寵物。"""
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

- [ ] **Step 5: Add `get_pet_accessible` to `db.py`**

Add after `get_pet` (around line 461):

```python
def get_pet_accessible(pet_id, user_id):
    """取得寵物（擁有者或共同飼養人均可讀取）。"""
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
```

- [ ] **Step 6: Update `remove_pet` to also delete shares**

In `remove_pet` (around line 484), add a `DELETE FROM pet_shares` before deleting the pet row. Both `user_id is not None` and `else` branches need it:

```python
def remove_pet(pet_id, user_id=None):
    """刪除寵物，並將相關商品與日記的 pet_id 設為 NULL，移除共同飼養記錄。"""
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
                cur.execute("DELETE FROM pet_shares WHERE pet_id = %s", (pet_id,))
                cur.execute(
                    "DELETE FROM pets WHERE id = %s AND user_id = %s",
                    (pet_id, user_id),
                )
            else:
                cur.execute("UPDATE products SET pet_id = NULL WHERE pet_id = %s", (pet_id,))
                cur.execute("UPDATE pet_diaries SET pet_id = NULL WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pet_shares WHERE pet_id = %s", (pet_id,))
                cur.execute("DELETE FROM pets WHERE id = %s", (pet_id,))
```

- [ ] **Step 7: Run integration tests — should all pass**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_db_pet_shares.py -v
```
Expected: all 6 tests `PASSED`

- [ ] **Step 8: Run full test suite to check for regressions**

```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v --ignore=tests/e2e
```
Expected: all existing tests still `PASSED`

- [ ] **Step 9: Commit**

```bash
git add db.py tests/test_db_pet_shares.py
git commit -m "feat(db): update get_all_pets/get_pet_accessible to include shared pets"
```

---

## Task 3: API — Share Management Endpoints

**Files:**
- Modify: `app.py` (update `api_get_pet`, add `api_get_pet_shares`, `api_add_pet_share`, `api_remove_pet_share`)

- [ ] **Step 1: Write failing API tests**

Create `tests/test_api_pet_shares.py`:

```python
import pytest


# Helper: full pet dict used by mocks that return JSON (must match _format_pet output)
_PET_1 = {
    "id": 1, "name": "小黑", "breed": "柴犬", "birthday": "",
    "photo_base64": "", "user_id": 1, "is_shared": False,
    "created_at": None, "updated_at": None,
}

# ── GET /api/pets/<id>/shares ──────────────────────────────────────────────

def test_get_shares_returns_list(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_1
    mock_db.get_pet_shares.return_value = [
        {"id": 10, "shared_with_user_id": 2, "username": "alice"}
    ]
    res = authed_client.get("/api/pets/1/shares")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["shares"]) == 1
    assert data["shares"][0]["username"] == "alice"


def test_get_shares_not_owner_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = None  # ownership check fails
    res = authed_client.get("/api/pets/1/shares")
    assert res.status_code == 404


# ── POST /api/pets/<id>/shares ─────────────────────────────────────────────

def test_add_share_success(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_1
    mock_db.get_user_by_username.return_value = {"id": 2, "username": "alice"}
    mock_db.add_pet_share.return_value = 10
    res = authed_client.post("/api/pets/1/shares", json={"username": "alice"})
    assert res.status_code == 201
    assert res.get_json()["username"] == "alice"


def test_add_share_missing_username_returns_400(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_1
    res = authed_client.post("/api/pets/1/shares", json={})
    assert res.status_code == 400


def test_add_share_unknown_user_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_1
    mock_db.get_user_by_username.return_value = None
    res = authed_client.post("/api/pets/1/shares", json={"username": "nobody"})
    assert res.status_code == 404


def test_add_share_self_returns_400(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_1
    # authed_client has user_id=1; target user also id=1
    mock_db.get_user_by_username.return_value = {"id": 1, "username": "myself"}
    res = authed_client.post("/api/pets/1/shares", json={"username": "myself"})
    assert res.status_code == 400


def test_add_share_duplicate_returns_409(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_1
    mock_db.get_user_by_username.return_value = {"id": 2, "username": "alice"}
    mock_db.add_pet_share.side_effect = Exception("Duplicate entry")
    res = authed_client.post("/api/pets/1/shares", json={"username": "alice"})
    assert res.status_code == 409


# ── DELETE /api/pets/<id>/shares/<share_id> ────────────────────────────────

def test_remove_share_success(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_1
    mock_db.remove_pet_share.return_value = 1  # 1 row deleted
    res = authed_client.delete("/api/pets/1/shares/10")
    assert res.status_code == 204


def test_remove_share_not_found_returns_404(authed_client, mock_db):
    mock_db.get_pet.return_value = _PET_1
    mock_db.remove_pet_share.return_value = 0  # nothing deleted
    res = authed_client.delete("/api/pets/1/shares/10")
    assert res.status_code == 404


# ── GET /api/pets/<id> — shared user access ────────────────────────────────

def test_get_pet_accessible_by_shared_user(authed_client, mock_db):
    """api_get_pet should use get_pet_accessible, not get_pet."""
    mock_db.get_pet_accessible.return_value = {
        "id": 1, "name": "小黑", "is_shared": True,
        "breed": "", "birthday": "", "photo_base64": "",
        "user_id": 2, "created_at": None, "updated_at": None,
    }
    res = authed_client.get("/api/pets/1")
    assert res.status_code == 200
    assert res.get_json()["is_shared"] is True
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_api_pet_shares.py -v
```
Expected: `FAILED` — `404` or `AttributeError` because routes don't exist yet

- [ ] **Step 3: Update `api_get_pet` in `app.py` to use `get_pet_accessible`**

Find `api_get_pet` (around line 483) and change one line:

> **Note on CSRF:** The new share endpoints (`/api/pets/<id>/shares`) do NOT need CSRF tokens. Looking at `app.py`, only the HTML form-based routes (login, register, forgot_password, reset_password) call `_validate_csrf_token`. All JSON API routes are CSRF-exempt and rely on session-based auth only. No CSRF changes needed.

```python
@app.route("/api/pets/<int:pet_id>", methods=["GET"])
def api_get_pet(pet_id):
    """取得單一寵物（擁有者或共同飼養人均可讀取）"""
    pet = db.get_pet_accessible(pet_id, user_id=current_user_id())
    if not pet:
        return jsonify({"error": "找不到寵物"}), 404
    return jsonify(pet)
```

- [ ] **Step 4: Add three share API endpoints to `app.py`**

Add after the `pets_page` route (around line 527), before `# ========== Products API ==========`:

```python
# ========== Pet Shares API ==========


@app.route("/api/pets/<int:pet_id>/shares", methods=["GET"])
def api_get_pet_shares(pet_id):
    """列出共同飼養人（僅擁有者可查）"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物或無權限"}), 404
    shares = db.get_pet_shares(pet_id, owner_user_id=uid)
    return jsonify({
        "shares": [
            {"id": s["id"], "username": s["username"], "shared_with_user_id": s["shared_with_user_id"]}
            for s in shares
        ]
    })


@app.route("/api/pets/<int:pet_id>/shares", methods=["POST"])
def api_add_pet_share(pet_id):
    """新增共同飼養人（需擁有此寵物）"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物或無權限"}), 404
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "請輸入帳號"}), 400
    target = db.get_user_by_username(username)
    if not target:
        return jsonify({"error": "找不到此帳號"}), 404
    if target["id"] == uid:
        return jsonify({"error": "無法分享給自己"}), 400
    try:
        share_id = db.add_pet_share(pet_id, owner_user_id=uid, shared_with_user_id=target["id"])
    except Exception:
        return jsonify({"error": "此帳號已是共同飼養人"}), 409
    return jsonify({"id": share_id, "username": username, "shared_with_user_id": target["id"]}), 201


@app.route("/api/pets/<int:pet_id>/shares/<int:share_id>", methods=["DELETE"])
def api_remove_pet_share(pet_id, share_id):
    """移除共同飼養人（需擁有此寵物）"""
    uid = current_user_id()
    if not db.get_pet(pet_id, user_id=uid):
        return jsonify({"error": "找不到寵物或無權限"}), 404
    removed = db.remove_pet_share(share_id, owner_user_id=uid)
    if not removed:
        return jsonify({"error": "找不到分享記錄"}), 404
    return "", 204
```

- [ ] **Step 5: Run API tests — should all pass**

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_api_pet_shares.py -v
```
Expected: all 9 tests `PASSED`

- [ ] **Step 6: Run full test suite (no regressions)**

```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v --ignore=tests/e2e
```
Expected: all `PASSED`

- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_api_pet_shares.py
git commit -m "feat(api): add pet share endpoints GET/POST/DELETE /api/pets/<id>/shares"
```

---

## Task 4: Frontend — Sharing UI in `pets.html`

**Files:**
- Modify: `templates/pets.html`

No automated tests for the frontend — manual smoke test steps are at the end.

- [ ] **Step 1: Add share dialog HTML**

In `pets.html`, after the closing `</div>` of the `editDialog` div (around line 71), add:

```html
<!-- Share dialog -->
<div id="shareDialog" class="hidden modal-overlay">
    <div class="modal-content">
        <h2>👥 共同飼養人</h2>
        <input type="hidden" id="sharePetId">
        <div id="sharesList"><div class="spinner"></div></div>
        <div class="form-group" style="margin-top:1rem">
            <label for="shareUsername">新增帳號</label>
            <div style="display:flex;gap:.5rem;align-items:center">
                <input type="text" id="shareUsername" placeholder="輸入帳號名稱" maxlength="100" style="flex:1">
                <button type="button" class="btn btn-primary" id="btnAddShare">新增</button>
            </div>
            <p id="shareError" class="hidden" style="color:var(--danger,#e74c3c);margin:.25rem 0 0"></p>
        </div>
        <div class="form-actions">
            <button type="button" class="btn btn-secondary" id="btnCloseShare">關閉</button>
        </div>
    </div>
</div>
```

- [ ] **Step 2: Add share badge + share button to `renderPets`**

In the JS section, replace the `renderPets` function (around line 130). The key changes: add `is_shared` badge on shared pet cards; replace the actions block for owned vs shared:

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
                    : `<button class="btn-icon btn-share-pet" data-id="${escapeHtml(p.id)}" title="共同飼養人">👥</button>
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

In the JS section, after the `deletePet` function (find it near the bottom), add:

```javascript
    // ---- Share dialog ----

    const shareDialog = document.getElementById('shareDialog');
    const sharesList = document.getElementById('sharesList');
    const shareUsername = document.getElementById('shareUsername');
    const shareError = document.getElementById('shareError');
    const btnAddShare = document.getElementById('btnAddShare');
    const btnCloseShare = document.getElementById('btnCloseShare');

    function showShareError(msg) {
        shareError.textContent = msg;
        shareError.classList.remove('hidden');
    }

    function clearShareError() {
        shareError.textContent = '';
        shareError.classList.add('hidden');
    }

    async function openShare(petId) {
        document.getElementById('sharePetId').value = petId;
        shareUsername.value = '';
        clearShareError();
        shareDialog.classList.remove('hidden');
        await loadShares(petId);
    }

    async function loadShares(petId) {
        sharesList.innerHTML = '<div class="spinner"></div>';
        try {
            const res = await fetch(`/api/pets/${petId}/shares`);
            if (!res.ok) throw new Error();
            const data = await res.json();
            renderShares(petId, data.shares || []);
        } catch {
            sharesList.innerHTML = '<p>載入失敗</p>';
        }
    }

    function renderShares(petId, shares) {
        if (!shares.length) {
            sharesList.innerHTML = '<p style="color:var(--text-muted,#888)">尚未設定共同飼養人</p>';
            return;
        }
        sharesList.innerHTML = shares.map(s => `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:.25rem 0">
                <span>👤 ${escapeHtml(s.username)}</span>
                <button class="btn-icon remove btn-remove-share" data-share-id="${escapeHtml(s.id)}" data-pet-id="${escapeHtml(petId)}" title="移除">✕</button>
            </div>
        `).join('');
        sharesList.querySelectorAll('.btn-remove-share').forEach(btn => {
            btn.addEventListener('click', () => removeShare(parseInt(btn.dataset.petId), parseInt(btn.dataset.shareId)));
        });
    }

    async function removeShare(petId, shareId) {
        try {
            const res = await fetch(`/api/pets/${petId}/shares/${shareId}`, { method: 'DELETE' });
            if (res.ok) {
                await loadShares(petId);
            } else {
                const err = await res.json();
                showShareError(err.error || '移除失敗');
            }
        } catch {
            showShareError('操作失敗，請稍後再試');
        }
    }

    btnAddShare.addEventListener('click', async () => {
        const petId = parseInt(document.getElementById('sharePetId').value);
        const username = shareUsername.value.trim();
        clearShareError();
        if (!username) { showShareError('請輸入帳號名稱'); return; }
        try {
            const res = await fetch(`/api/pets/${petId}/shares`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username }),
            });
            if (res.ok) {
                shareUsername.value = '';
                await loadShares(petId);
            } else {
                const err = await res.json();
                showShareError(err.error || '新增失敗');
            }
        } catch {
            showShareError('操作失敗，請稍後再試');
        }
    });

    btnCloseShare.addEventListener('click', () => { shareDialog.classList.add('hidden'); });
    shareDialog.addEventListener('click', (e) => {
        if (e.target === shareDialog) shareDialog.classList.add('hidden');
    });
```

- [ ] **Step 4: Add basic CSS for share badge**

In `templates/pets.html`, inside the `<style>` block (or add one before `</head>` in `base.html` if preferred), add:

```css
.pet-shared-badge {
    font-size: .75rem;
    color: var(--primary, #6b7ae8);
    padding: .1rem .4rem;
    border: 1px solid var(--primary, #6b7ae8);
    border-radius: 999px;
    white-space: nowrap;
}
```

- [ ] **Step 5: Manual smoke test**

Start the app (`docker-compose up -d` or `python app.py`), open `http://localhost:5001`:

1. Register two accounts: `user_a` and `user_b`
2. Log in as `user_a`, go to `/pets`, create a pet "小黑"
3. Click the 👥 button on "小黑" — share dialog should open showing "尚未設定共同飼養人"
4. Enter `user_b` in the input and click "新增" — should appear in the list
5. Log out, log in as `user_b`, go to `/pets` — "小黑" should appear with a "👥 共享" badge and no edit/delete buttons
6. Log back in as `user_a`, open share dialog, remove `user_b` — list should become empty
7. Log in as `user_b` — "小黑" should be gone from the list

- [ ] **Step 6: Commit**

```bash
git add templates/pets.html
git commit -m "feat(ui): add pet share dialog with co-owner management"
```

---

## Task 5: Final regression check

- [ ] **Step 1: Run all non-e2e tests**

```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v --ignore=tests/e2e
```
Expected: all `PASSED`

- [ ] **Step 2: Commit if anything was fixed**

```bash
git add -p
git commit -m "fix: address regressions from shared pets feature"
```

---

## Summary of New API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/pets/<id>/shares` | Owner only | List co-owners |
| `POST` | `/api/pets/<id>/shares` | Owner only | Add co-owner by username |
| `DELETE` | `/api/pets/<id>/shares/<share_id>` | Owner only | Remove co-owner |

Shared users can read pets via `GET /api/pets` and `GET /api/pets/<id>` (already existing routes, now updated).
