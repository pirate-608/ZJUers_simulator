import secrets
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.core.config import settings
from app.models.user import User
from app.models.game_save import GameSave
from app.models.admin import UserRestriction, UserBlacklist, AdminAuditLog


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        if not username or not password:
            return False

        if not secrets.compare_digest(username, settings.ADMIN_USERNAME):
            return False
        if not secrets.compare_digest(password, settings.ADMIN_PASSWORD):
            return False

        request.session["admin"] = "1"
        request.session["admin_user"] = username
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("admin") == "1"


class UserAdmin(ModelView, model=User):
    column_list = [
        User.id,
        User.username,
        User.tier,
        User.exam_score,
        User.highest_gpa,
        User.created_at,
    ]
    column_searchable_list = [User.username]
    column_sortable_list = [User.id, User.created_at, User.exam_score, User.highest_gpa]


class GameSaveAdmin(ModelView, model=GameSave):
    column_list = [
        GameSave.id,
        GameSave.user_id,
        GameSave.save_slot,
        GameSave.semester_index,
        GameSave.saved_at,
    ]
    column_sortable_list = [GameSave.id, GameSave.user_id, GameSave.saved_at]


class UserRestrictionAdmin(ModelView, model=UserRestriction):
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
        _log_admin_action(
            request,
            "restriction_delete",
            "user_restrictions",
            str(model.id) if model.id else None,
            {"user_id": model.user_id, "restriction_type": model.restriction_type},
        )


class UserBlacklistAdmin(ModelView, model=UserBlacklist):
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
        _log_admin_action(
            request,
            "blacklist_delete",
            "user_blacklist",
            str(model.id) if model.id else None,
            {"identifier": model.identifier, "identifier_type": model.identifier_type},
        )


class AdminAuditLogAdmin(ModelView, model=AdminAuditLog):
    column_list = [
        AdminAuditLog.id,
        AdminAuditLog.admin_username,
        AdminAuditLog.action,
        AdminAuditLog.target_type,
        AdminAuditLog.target_id,
        AdminAuditLog.created_at,
    ]
    column_sortable_list = [AdminAuditLog.id, AdminAuditLog.created_at]


def _build_sync_engine():
    url = make_url(settings.DATABASE_URL)
    if "+asyncpg" in url.drivername:
        url = url.set(drivername="postgresql+psycopg2")
    return create_engine(url)


def _log_admin_action(
    request: Request, action: str, target_type: str, target_id: str, details
):
    engine = _build_sync_engine()
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        session.add(
            AdminAuditLog(
                admin_username=request.session.get("admin_user") or "admin",
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
            )
        )
        session.commit()


def setup_admin(app):
    auth_backend = AdminAuth(secret_key=settings.ADMIN_SESSION_SECRET)
    admin = Admin(app, _build_sync_engine(), authentication_backend=auth_backend)

    admin.add_view(UserAdmin)
    admin.add_view(GameSaveAdmin)
    admin.add_view(UserRestrictionAdmin)
    admin.add_view(UserBlacklistAdmin)
    admin.add_view(AdminAuditLogAdmin)
