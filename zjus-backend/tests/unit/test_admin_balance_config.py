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
from app.game.balance import GameBalance
from app.models.admin import AdminAuditLog
from app.services.balance_admin import (
    BalanceConfigError,
    build_config_from_form,
    config_to_form_data,
    latest_balance_update_snapshot,
    publish_balance_config,
    write_balance_config_atomic,
)


@pytest.fixture(autouse=True)
def reset_balance_singleton():
    GameBalance._instance = None
    GameBalance._config = {}
    GameBalance._config_path = None
    yield
    GameBalance._instance = None
    GameBalance._config = {}
    GameBalance._config_path = None


@pytest.fixture
def balance_config():
    path = Path(__file__).resolve().parents[2] / "world" / "game_balance.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_valid_form_publishes_file_and_reloads(tmp_path, balance_config):
    form = config_to_form_data(balance_config)
    form["tick__interval_seconds"] = "7"
    next_config = build_config_from_form(balance_config, form)

    config_path = tmp_path / "game_balance.json"
    config_path.write_text(
        json.dumps(balance_config, ensure_ascii=False),
        encoding="utf-8",
    )
    game_balance = GameBalance()
    game_balance.load(config_path)

    publish_balance_config(config_path, next_config, game_balance.reload)

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["tick"]["interval_seconds"] == 7
    assert game_balance.tick_interval == 7


def test_invalid_probability_does_not_build_or_write(tmp_path, balance_config):
    config_path = tmp_path / "game_balance.json"
    original_text = json.dumps(balance_config, ensure_ascii=False)
    config_path.write_text(original_text, encoding="utf-8")

    form = config_to_form_data(balance_config)
    form["events__random_event__trigger_probability"] = "1.2"

    with pytest.raises(BalanceConfigError):
        build_config_from_form(balance_config, form)

    assert config_path.read_text(encoding="utf-8") == original_text


def test_missing_form_field_is_rejected(balance_config):
    form = config_to_form_data(balance_config)
    del form["tick__interval_seconds"]

    with pytest.raises(BalanceConfigError, match="缺少字段"):
        build_config_from_form(balance_config, form)


def test_atomic_write_failure_keeps_original_file(tmp_path, balance_config):
    config_path = tmp_path / "game_balance.json"
    original_text = json.dumps(balance_config, ensure_ascii=False)
    config_path.write_text(original_text, encoding="utf-8")

    next_config = copy.deepcopy(balance_config)
    next_config["version"] = "atomic-test"

    def fail_replace(src, dst):
        raise RuntimeError("replace failed")

    with pytest.raises(RuntimeError, match="replace failed"):
        write_balance_config_atomic(config_path, next_config, replace_func=fail_replace)

    assert config_path.read_text(encoding="utf-8") == original_text
    assert not (tmp_path / ".game_balance.json.tmp").exists()


def test_latest_balance_update_snapshot_can_restore(tmp_path, balance_config):
    engine = create_engine("sqlite:///:memory:")
    AdminAuditLog.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)

    previous_config = copy.deepcopy(balance_config)
    previous_config["version"] = "before-change"
    current_config = copy.deepcopy(balance_config)
    current_config["version"] = "after-change"

    with SessionLocal() as session:
        session.add(
            AdminAuditLog(
                admin_username="admin",
                action="balance_update",
                target_type="game_balance",
                target_id="world/game_balance.json",
                details={"old_config": previous_config},
            )
        )
        session.commit()
        snapshot = latest_balance_update_snapshot(session)

    assert snapshot is not None
    assert snapshot.old_config["version"] == "before-change"

    config_path = tmp_path / "game_balance.json"
    config_path.write_text(
        json.dumps(current_config, ensure_ascii=False),
        encoding="utf-8",
    )
    game_balance = GameBalance()
    game_balance.load(config_path)

    publish_balance_config(config_path, snapshot.old_config, game_balance.reload)

    assert game_balance.version == "before-change"
    restored = json.loads(config_path.read_text(encoding="utf-8"))
    assert restored["version"] == "before-change"


def test_admin_balance_page_renders_with_admin_session(monkeypatch):
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

    response = client.get("/admin/balance")

    assert response.status_code == 200
    assert "数值平衡" in response.text
    assert "game_balance.json" in response.text
