"""
Integration tests for pet share DB functions.
Run: docker exec pet-adorable-life-web python -m pytest tests/test_db_pet_shares.py -v
"""
import hashlib
from datetime import datetime, timedelta

import pytest
import db


@pytest.fixture
def two_users():
    uid_a = db.create_user("share_ta", "share_ta@test.com", "hashed")
    uid_b = db.create_user("share_tb", "share_tb@test.com", "hashed")
    yield uid_a, uid_b
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM pet_share_invitations WHERE inviter_user_id IN (%s,%s) OR invitee_user_id IN (%s,%s)",
                (uid_a, uid_b, uid_a, uid_b),
            )
            cur.execute(
                "DELETE FROM pet_shares WHERE owner_user_id IN (%s,%s) OR shared_with_user_id IN (%s,%s)",
                (uid_a, uid_b, uid_a, uid_b),
            )
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


# ========== Invitation tests ==========

def test_create_and_get_invitation_by_token(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("邀請毛孩", user_id=uid_a)
    raw_token = "testtoken_abc123_xxxyyy"
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
    raw_token = "testtoken_accept_xxxyyy"
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
    raw_token = "testtoken_decline_xxxyyy"
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


# Regression: ISSUE-B2 — co-owner cannot see shared pet's products in all-tab
# Found by /qa on 2026-03-28
def test_get_all_products_includes_shared_pet_content(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("回歸測試毛孩", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="read_only")
    prod_id = db.add_product("共享寵物商品", "測試摘要", pet_id=pet_id, user_id=uid_a)

    products = db.get_all_products(user_id=uid_b)
    ids = [p["id"] for p in products]
    assert prod_id in ids, "co-owner should see shared pet's products"

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM products WHERE id = %s", (prod_id,))
            cur.execute("DELETE FROM pets WHERE id = %s", (pet_id,))


# Regression: ISSUE-B2 — co-owner cannot see shared pet's diaries in all-tab
# Found by /qa on 2026-03-28
def test_get_all_diaries_includes_shared_pet_content(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("回歸測試毛孩2", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="read_only")
    diary_id = db.add_diary(
        pet_id=pet_id, user_id=uid_a,
        title="共享日記", describe_text="測試", main_emotion="開心",
        image_base64=None, memo=None,
    )

    diaries = db.get_all_diaries(user_id=uid_b)
    ids = [d["id"] for d in diaries]
    assert diary_id in ids, "co-owner should see shared pet's diaries"

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pet_diaries WHERE id = %s", (diary_id,))
            cur.execute("DELETE FROM pets WHERE id = %s", (pet_id,))


# Regression: ISSUE-A — co-owner cannot delete/edit items they created
# Found by /qa on 2026-03-28
def test_co_owner_can_remove_own_product(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("共享測試毛孩A", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="editor")
    prod_id = db.add_product("共享者建立商品", "by co-owner", pet_id=pet_id, user_id=uid_b)

    # Co-owner should be able to remove their own product
    db.remove_product(prod_id, user_id=uid_b)

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE id = %s", (prod_id,))
            assert cur.fetchone()["cnt"] == 0, "co-owner should be able to delete own product"
            cur.execute("DELETE FROM pets WHERE id = %s", (pet_id,))


# Regression: ISSUE-B — owner cannot delete/edit items created by co-owner
# Found by /qa on 2026-03-28
def test_owner_can_remove_coowner_product(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("共享測試毛孩B", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="editor")
    prod_id = db.add_product("共享者建立商品2", "by co-owner", pet_id=pet_id, user_id=uid_b)

    # Owner should be able to remove co-owner's product for their own pet
    db.remove_product(prod_id, user_id=uid_a)

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE id = %s", (prod_id,))
            assert cur.fetchone()["cnt"] == 0, "owner should be able to delete co-owner's product"
            cur.execute("DELETE FROM pets WHERE id = %s", (pet_id,))


# Regression: ISSUE-B — owner cannot see co-owner's items in all-tab
# Found by /qa on 2026-03-28
def test_get_all_products_owner_sees_coowner_items(two_users):
    uid_a, uid_b = two_users
    pet_id = db.add_pet("共享測試毛孩C", user_id=uid_a)
    db.add_pet_share(pet_id, owner_user_id=uid_a, shared_with_user_id=uid_b, role="editor")
    prod_id = db.add_product("共享者建立商品3", "by co-owner", pet_id=pet_id, user_id=uid_b)

    products = db.get_all_products(user_id=uid_a)
    ids = [p["id"] for p in products]
    assert prod_id in ids, "owner should see co-owner's products in all-tab"

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM products WHERE id = %s", (prod_id,))
            cur.execute("DELETE FROM pets WHERE id = %s", (pet_id,))
