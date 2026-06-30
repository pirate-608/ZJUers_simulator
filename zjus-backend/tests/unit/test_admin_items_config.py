import copy
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import admin as admin_module
from app.admin import setup_admin
from app.core.config import settings
from app.game.items import ItemCatalog
from app.models.admin import AdminAuditLog
from app.services.item_admin import (
    ItemConfigError,
    build_config_from_form,
    build_item_effect_fields,
    config_to_form_data,
    latest_items_update_snapshot,
    normalize_items_config,
    publish_items_config,
    write_items_config_atomic,
)


@pytest.fixture
def items_config():
    path = Path(__file__).resolve().parents[2] / "world" / "items.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_valid_form_publishes_file_and_reloads(tmp_path, items_config):
    form = config_to_form_data(items_config)
    form["economy__initial_gold"] = "166"
    form["item__0__price"] = "188"
    next_config = build_config_from_form(items_config, form)

    config_path = tmp_path / "items.json"
    config_path.write_text(
        json.dumps(items_config, ensure_ascii=False),
        encoding="utf-8",
    )
    catalog = ItemCatalog()
    catalog.load(config_path)

    publish_items_config(config_path, next_config, catalog.reload)

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["economy"]["initial_gold"] == 166
    assert saved["items"][0]["price"] == 188
    assert catalog.initial_gold == 166
    assert catalog.get_item(saved["items"][0]["id"])["price"] == 188


def test_unsupported_effect_field_is_rejected(items_config):
    config = copy.deepcopy(items_config)
    config["items"][0]["effects"]["gold"] = 1

    with pytest.raises(ItemConfigError, match="不支持道具加成字段"):
        normalize_items_config(config)


def test_duplicate_new_item_id_is_rejected(items_config):
    form = config_to_form_data(items_config)
    effect_field = build_item_effect_fields()[0]
    first_item = items_config["items"][0]
    form.update(
        {
            "new__id": first_item["id"],
            "new__name": "重复道具",
            "new__category": "测试",
            "new__description": "用于验证重复 ID 被拒绝。",
            "new__price": "50",
            "new__sell_price": "25",
            "new__tags": "测试",
            f"new__effect__{effect_field.id}": "1",
        }
    )

    with pytest.raises(ItemConfigError, match="道具 ID 重复"):
        build_config_from_form(items_config, form)


def test_atomic_write_failure_keeps_original_file(tmp_path, items_config):
    config_path = tmp_path / "items.json"
    original_text = json.dumps(items_config, ensure_ascii=False)
    config_path.write_text(original_text, encoding="utf-8")

    next_config = copy.deepcopy(items_config)
    next_config["version"] = "atomic-test"

    def fail_replace(src, dst):
        raise RuntimeError("replace failed")

    with pytest.raises(RuntimeError, match="replace failed"):
        write_items_config_atomic(config_path, next_config, replace_func=fail_replace)

    assert config_path.read_text(encoding="utf-8") == original_text
    assert not (tmp_path / ".items.json.tmp").exists()


def test_latest_items_update_snapshot_can_restore(tmp_path, items_config):
    engine = create_engine("sqlite:///:memory:")
    AdminAuditLog.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)

    previous_config = copy.deepcopy(items_config)
    previous_config["version"] = "before-change"
    current_config = copy.deepcopy(items_config)
    current_config["version"] = "after-change"

    with SessionLocal() as session:
        session.add(
            AdminAuditLog(
                admin_username="admin",
                action="items_update",
                target_type="items",
                target_id="world/items.json",
                details={"old_config": previous_config},
            )
        )
        session.commit()
        snapshot = latest_items_update_snapshot(session)

    assert snapshot is not None
    assert snapshot.old_config["version"] == "before-change"

    config_path = tmp_path / "items.json"
    config_path.write_text(
        json.dumps(current_config, ensure_ascii=False),
        encoding="utf-8",
    )
    catalog = ItemCatalog()
    catalog.load(config_path)

    publish_items_config(config_path, snapshot.old_config, catalog.reload)

    assert catalog.version == "before-change"
    restored = json.loads(config_path.read_text(encoding="utf-8"))
    assert restored["version"] == "before-change"


def test_admin_items_page_renders_with_admin_session(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    AdminAuditLog.__table__.create(engine)
    monkeypatch.setattr(admin_module, "_build_sync_engine", lambda: engine)

    app = FastAPI()
    setup_admin(app)
    client = TestClient(app)

    login_response = client.post(
        "/admin/login",
        data={
            "username": settings.ADMIN_USERNAME,
            "password": settings.ADMIN_PASSWORD,
        },
        follow_redirects=False,
    )
    assert login_response.status_code == 302

    response = client.get("/admin/items")

    assert response.status_code == 200
    assert "道具配置" in response.text
    assert "items.json" in response.text
    assert 'action="/admin/items/restore-latest"' in response.text
    assert 'action="/admin/items"' in response.text

    index_response = client.get("/admin/")
    assert index_response.status_code == 200
    assert 'href="http://testserver/admin/items"' in index_response.text
    assert "/admin/items/restore-latest" not in index_response.text

    restore_get_response = client.get(
        "/admin/items/restore-latest",
        follow_redirects=False,
    )
    assert restore_get_response.status_code == 303
    assert restore_get_response.headers["location"] == "/admin/items"
