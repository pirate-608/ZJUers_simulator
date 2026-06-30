"""SQLAdmin integration and operational admin pages.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
This module wires database models into the `/admin` UI and hosts the
world-data editors that publish `game_balance.json` and `items.json`.
"""

import copy
import json
import secrets
from typing import Any
from urllib.parse import urlencode

from sqladmin import Admin, BaseView, ModelView, expose
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.core.config import settings
from app.game.balance import balance
from app.game.items import items
from app.models.admin import AdminAuditLog, UserBlacklist, UserRestriction
from app.models.game_save import GameSave
from app.models.user import User
from app.services.balance_admin import (
    BalanceConfigError,
    build_balance_sections,
    build_config_from_form,
    config_to_form_data,
    diff_balance_configs,
    latest_balance_update_snapshot,
    publish_balance_config,
    summarize_balance_config,
)
from app.services.item_admin import (
    ItemConfigError,
    build_item_effect_fields,
    build_item_rows,
    diff_item_configs,
    latest_items_update_snapshot,
    load_items_config,
    publish_items_config,
    summarize_items_config,
)
from app.services.item_admin import (
    build_config_from_form as build_items_config_from_form,
)
from app.services.item_admin import (
    config_to_form_data as items_config_to_form_data,
)


class AdminAuth(AuthenticationBackend):
    """Session-cookie authentication backend for SQLAdmin."""

    async def login(self, request: Request) -> bool:
        """Validate admin credentials from the login form."""
        form = await request.form()
        username_value = form.get("username")
        password_value = form.get("password")
        if not isinstance(username_value, str) or not isinstance(password_value, str):
            return False

        username = username_value
        password = password_value
        if not secrets.compare_digest(username, settings.ADMIN_USERNAME):
            return False
        if not secrets.compare_digest(password, settings.ADMIN_PASSWORD):
            return False

        request.session["admin"] = "1"
        request.session["admin_user"] = username
        return True

    async def logout(self, request: Request) -> bool:
        """Clear the admin session."""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Return whether the current request has an admin session."""
        return request.session.get("admin") == "1"


class UserAdmin(ModelView, model=User):
    """Read-oriented admin view for player accounts."""

    column_list = [
        User.id,
        User.username,
        User.token,
        User.highest_gpa,
        User.created_at,
    ]
    column_searchable_list = [User.username]
    column_sortable_list = [User.id, User.created_at, User.highest_gpa]


class GameSaveAdmin(ModelView, model=GameSave):
    """Admin view for inspecting persisted save slots."""

    column_list = [
        GameSave.id,
        GameSave.user_id,
        GameSave.save_slot,
        GameSave.semester_index,
        GameSave.saved_at,
    ]
    column_sortable_list = [GameSave.id, GameSave.user_id, GameSave.saved_at]


class UserRestrictionAdmin(ModelView, model=UserRestriction):
    """Admin view for user restrictions with audit logging."""

    column_list = [
        UserRestriction.id,
        UserRestriction.user_id,
        UserRestriction.restriction_type,
        UserRestriction.is_active,
        UserRestriction.expires_at,
        UserRestriction.created_at,
    ]
    column_searchable_list = [UserRestriction.user_id]
    column_sortable_list = [UserRestriction.id, UserRestriction.created_at]

    async def on_model_change(self, data, model, is_created, request: Request):
        """Record restriction creates and updates in the admin audit log."""
        _log_admin_action(
            request,
            "restriction_upsert",
            "user_restrictions",
            str(model.id) if model.id else None,
            {
                "user_id": model.user_id,
                "restriction_type": model.restriction_type,
                "is_active": model.is_active,
            },
        )

    async def on_model_delete(self, model, request: Request):
        """Record restriction deletion in the admin audit log."""
        _log_admin_action(
            request,
            "restriction_delete",
            "user_restrictions",
            str(model.id) if model.id else None,
            {"user_id": model.user_id, "restriction_type": model.restriction_type},
        )


class UserBlacklistAdmin(ModelView, model=UserBlacklist):
    """Admin view for blacklist entries with audit logging."""

    column_list = [
        UserBlacklist.id,
        UserBlacklist.identifier,
        UserBlacklist.identifier_type,
        UserBlacklist.is_active,
        UserBlacklist.created_at,
    ]
    column_searchable_list = [UserBlacklist.identifier]
    column_sortable_list = [UserBlacklist.id, UserBlacklist.created_at]

    async def on_model_change(self, data, model, is_created, request: Request):
        """Record blacklist creates and updates in the admin audit log."""
        _log_admin_action(
            request,
            "blacklist_upsert",
            "user_blacklist",
            str(model.id) if model.id else None,
            {
                "identifier": model.identifier,
                "identifier_type": model.identifier_type,
                "is_active": model.is_active,
            },
        )

    async def on_model_delete(self, model, request: Request):
        """Record blacklist deletion in the admin audit log."""
        _log_admin_action(
            request,
            "blacklist_delete",
            "user_blacklist",
            str(model.id) if model.id else None,
            {"identifier": model.identifier, "identifier_type": model.identifier_type},
        )


class AdminAuditLogAdmin(ModelView, model=AdminAuditLog):
    """Read-only audit-log view for operational changes."""

    column_list = [
        AdminAuditLog.id,
        AdminAuditLog.admin_username,
        AdminAuditLog.action,
        AdminAuditLog.target_type,
        AdminAuditLog.target_id,
        AdminAuditLog.created_at,
    ]
    column_sortable_list = [AdminAuditLog.id, AdminAuditLog.created_at]


class BalanceConfigAdmin(BaseView):
    """SQLAdmin page for editing `world/game_balance.json`."""

    name = "数值平衡"
    icon = "fa-solid fa-sliders"
    category = "运营"
    category_icon = "fa-solid fa-toolbox"

    @expose(
        "/balance/restore-latest",
        methods=["GET", "POST"],
        identity="balance_restore_latest",
        include_in_schema=False,
    )
    async def restore_latest(self, request: Request):
        """Restore the previous balance config captured in audit logs."""
        if request.method == "GET":
            return _balance_redirect(request)

        try:
            snapshot = _get_latest_balance_snapshot()
            if snapshot is None:
                return _balance_redirect(request, status="no_restore")

            old_config = copy.deepcopy(balance.raw)
            restored_config = snapshot.old_config
            publish_balance_config(balance.config_path, restored_config, balance.reload)
            _log_admin_action(
                request,
                "balance_restore",
                "game_balance",
                str(snapshot.log_id),
                {
                    "old_version": old_config.get("version"),
                    "new_version": restored_config.get("version"),
                    "old_summary": summarize_balance_config(old_config),
                    "new_summary": summarize_balance_config(restored_config),
                    "old_config": old_config,
                    "new_config": restored_config,
                    "restored_from_log_id": snapshot.log_id,
                    "changed_fields": diff_balance_configs(
                        old_config, restored_config
                    ),
                },
            )
            return _balance_redirect(request, status="restored")
        except Exception as exc:
            return _balance_redirect(request, status="restore_error", error=str(exc))

    @expose(
        "/balance",
        methods=["GET", "POST"],
        identity="balance",
        include_in_schema=False,
    )
    async def balance_page(self, request: Request):
        """Render and process the balance editor form."""
        current_config = copy.deepcopy(balance.raw)
        form_values = config_to_form_data(current_config)
        error = request.query_params.get("error")
        status = request.query_params.get("status")

        if request.method == "POST":
            submitted_form = await request.form()
            form_values.update(
                {key: str(value) for key, value in submitted_form.items()}
            )
            try:
                new_config = build_config_from_form(current_config, submitted_form)
                changed_fields = diff_balance_configs(current_config, new_config)
                if not changed_fields:
                    return _balance_redirect(request, status="unchanged")

                publish_balance_config(balance.config_path, new_config, balance.reload)
                _log_admin_action(
                    request,
                    "balance_update",
                    "game_balance",
                    str(balance.config_path),
                    {
                        "old_version": current_config.get("version"),
                        "new_version": new_config.get("version"),
                        "old_summary": summarize_balance_config(current_config),
                        "new_summary": summarize_balance_config(new_config),
                        "old_config": current_config,
                        "new_config": new_config,
                        "changed_fields": changed_fields,
                    },
                )
                return _balance_redirect(request, status="saved")
            except BalanceConfigError as exc:
                error = str(exc)
            except Exception as exc:
                error = f"保存失败：{exc}"

        sections = build_balance_sections(current_config)
        context = {
            "title": "数值平衡",
            "subtitle": "编辑 world/game_balance.json 并热重载",
            "sections": sections,
            "values": form_values,
            "error": error,
            "status": status,
            "balance_path": str(balance.config_path),
            "balance_form_action": _admin_path(request, "/balance"),
            "balance_restore_action": _admin_path(
                request, "/balance/restore-latest"
            ),
            "raw_json": json.dumps(current_config, ensure_ascii=False, indent=2),
            "recent_logs": _get_recent_balance_logs(),
        }
        return await self.templates.TemplateResponse(
            request, "admin/balance.html", context
        )


class ItemsConfigAdmin(BaseView):
    """SQLAdmin page for editing `world/items.json`."""

    name = "道具配置"
    icon = "fa-solid fa-bag-shopping"
    category = "运营"
    category_icon = "fa-solid fa-toolbox"

    @expose(
        "/items/restore-latest",
        methods=["GET", "POST"],
        identity="items_restore_latest",
        include_in_schema=False,
    )
    async def restore_latest(self, request: Request):
        """Restore the previous item config captured in audit logs."""
        if request.method == "GET":
            return _items_redirect(request)

        try:
            snapshot = _get_latest_items_snapshot()
            if snapshot is None:
                return _items_redirect(request, status="no_restore")

            old_config = load_items_config(items.config_path)
            restored_config = snapshot.old_config
            publish_items_config(items.config_path, restored_config, items.reload)
            _log_admin_action(
                request,
                "items_restore",
                "items",
                str(snapshot.log_id),
                {
                    "old_version": old_config.get("version"),
                    "new_version": restored_config.get("version"),
                    "old_summary": summarize_items_config(old_config),
                    "new_summary": summarize_items_config(restored_config),
                    "old_config": old_config,
                    "new_config": restored_config,
                    "restored_from_log_id": snapshot.log_id,
                    "changed_fields": diff_item_configs(old_config, restored_config),
                },
            )
            return _items_redirect(request, status="restored")
        except Exception as exc:
            return _items_redirect(request, status="restore_error", error=str(exc))

    @expose(
        "/items",
        methods=["GET", "POST"],
        identity="items",
        include_in_schema=False,
    )
    async def items_page(self, request: Request):
        """Render and process the item-catalog editor form."""
        current_config = load_items_config(items.config_path)
        form_values = items_config_to_form_data(current_config)
        error = request.query_params.get("error")
        status = request.query_params.get("status")

        if request.method == "POST":
            submitted_form = await request.form()
            form_values.update(
                {key: str(value) for key, value in submitted_form.items()}
            )
            try:
                new_config = build_items_config_from_form(
                    current_config,
                    submitted_form,
                )
                changed_fields = diff_item_configs(current_config, new_config)
                if not changed_fields:
                    return _items_redirect(request, status="unchanged")

                publish_items_config(items.config_path, new_config, items.reload)
                _log_admin_action(
                    request,
                    "items_update",
                    "items",
                    str(items.config_path),
                    {
                        "old_version": current_config.get("version"),
                        "new_version": new_config.get("version"),
                        "old_summary": summarize_items_config(current_config),
                        "new_summary": summarize_items_config(new_config),
                        "old_config": current_config,
                        "new_config": new_config,
                        "changed_fields": changed_fields,
                    },
                )
                return _items_redirect(request, status="saved")
            except ItemConfigError as exc:
                error = str(exc)
            except Exception as exc:
                error = f"保存失败：{exc}"

        context = {
            "title": "道具配置",
            "subtitle": "编辑 world/items.json 并热重载",
            "items_path": str(items.config_path),
            "items_form_action": _admin_path(request, "/items"),
            "items_restore_action": _admin_path(request, "/items/restore-latest"),
            "values": form_values,
            "item_rows": build_item_rows(current_config),
            "effect_fields": build_item_effect_fields(),
            "error": error,
            "status": status,
            "raw_json": json.dumps(current_config, ensure_ascii=False, indent=2),
            "recent_logs": _get_recent_items_logs(),
        }
        return await self.templates.TemplateResponse(
            request,
            "admin/items.html",
            context,
        )


def _build_sync_engine():
    url = make_url(settings.DATABASE_URL)
    if "+asyncpg" in url.drivername:
        url = url.set(drivername="postgresql+psycopg2")
    return create_engine(url)


def _balance_redirect(request: Request, **params: str):
    url = _admin_path(request, "/balance")
    if params:
        url = f"{url}?{urlencode(params)}"
    return RedirectResponse(url, status_code=303)


def _items_redirect(request: Request, **params: str):
    url = _admin_path(request, "/items")
    if params:
        url = f"{url}?{urlencode(params)}"
    return RedirectResponse(url, status_code=303)


def _admin_path(request: Request, path: str) -> str:
    root_path = str(request.scope.get("root_path") or "").rstrip("/")
    if root_path.endswith("/admin"):
        base_path = root_path
    else:
        base_path = f"{root_path}/admin"
    return f"{base_path}{path}"


def _log_admin_action(
    request: Request,
    action: str,
    target_type: str,
    target_id: str | None,
    details: dict[str, Any],
):
    """Persist one synchronous admin audit record."""
    engine = _build_sync_engine()
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        session.add(
            AdminAuditLog(
                admin_username=str(request.session.get("admin_user") or "admin"),
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
            )
        )
        session.commit()


def _get_latest_balance_snapshot():
    engine = _build_sync_engine()
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        return latest_balance_update_snapshot(session)


def _get_latest_items_snapshot():
    engine = _build_sync_engine()
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        return latest_items_update_snapshot(session)


def _get_recent_balance_logs(limit: int = 5) -> list[dict[str, Any]]:
    engine = _build_sync_engine()
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        rows = (
            session.query(AdminAuditLog)
            .filter(
                AdminAuditLog.target_type == "game_balance",
                AdminAuditLog.action.in_(["balance_update", "balance_restore"]),
            )
            .order_by(AdminAuditLog.id.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": row.id,
                "admin_username": row.admin_username,
                "action": row.action,
                "created_at": row.created_at,
                "old_version": (row.details or {}).get("old_version"),
                "new_version": (row.details or {}).get("new_version"),
                "changed_fields": (row.details or {}).get("changed_fields", []),
            }
            for row in rows
        ]


def _get_recent_items_logs(limit: int = 5) -> list[dict[str, Any]]:
    engine = _build_sync_engine()
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        rows = (
            session.query(AdminAuditLog)
            .filter(
                AdminAuditLog.target_type == "items",
                AdminAuditLog.action.in_(["items_update", "items_restore"]),
            )
            .order_by(AdminAuditLog.id.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": row.id,
                "admin_username": row.admin_username,
                "action": row.action,
                "created_at": row.created_at,
                "old_version": (row.details or {}).get("old_version"),
                "new_version": (row.details or {}).get("new_version"),
                "changed_fields": (row.details or {}).get("changed_fields", []),
            }
            for row in rows
        ]


def setup_admin(app):
    """Register SQLAdmin views and authentication on the FastAPI app."""
    auth_backend = AdminAuth(secret_key=settings.ADMIN_SESSION_SECRET)
    admin = Admin(app, _build_sync_engine(), authentication_backend=auth_backend)

    admin.add_view(UserAdmin)
    admin.add_view(GameSaveAdmin)
    admin.add_view(UserRestrictionAdmin)
    admin.add_view(UserBlacklistAdmin)
    admin.add_view(BalanceConfigAdmin)
    BalanceConfigAdmin.identity = "balance"
    admin.add_view(ItemsConfigAdmin)
    ItemsConfigAdmin.identity = "items"
    admin.add_view(AdminAuditLogAdmin)
