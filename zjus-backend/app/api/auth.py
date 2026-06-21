import secrets
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.cache import RedisCache
from app.core.config import settings
from app.core.input_safety import validate_username
from app.core.security import create_access_token
from app.game.stat_definitions import stat_definitions
from app.game.state import RedisState
from app.models.user import User
from app.repositories.redis_repo import RedisRepository
from app.services.game_service import GameService
from app.services.restriction_service import RestrictionService
from app.services.save_service import SaveService
from app.services.world_service import WorldService

router = APIRouter()

DbSessionDep = Annotated[AsyncSession, Depends(deps.get_db)]
AuthorizationHeader = Annotated[str, Header(..., description="Bearer <JWT>")]
LEGACY_INITIAL_STAT_DEFAULTS = stat_definitions.initial_default_stats()

# ─── 模型 ───


class AuthRequest(BaseModel):
    username: str
    invite_code: str
    token: Optional[str] = None  # 老玩家凭证


class SaveSummary(BaseModel):
    save_slot: int
    major: str
    major_abbr: str
    semester: str
    semester_idx: int
    gpa: str
    saved_at: Optional[str] = None
    total_play_time: int = 0


class AuthResponse(BaseModel):
    status: str  # "new_user" | "returning"
    jwt: Optional[str] = None
    user_token: Optional[str] = None  # 持久凭证（新用户）
    username: str
    user_id: Optional[int] = None
    message: Optional[str] = None
    saves: List[SaveSummary] = Field(default_factory=list)


class MajorOption(BaseModel):
    name: str
    abbr: str
    iq_buff: int
    stress_base: int
    desc: str


class InitCharacterRequest(BaseModel):
    token: str  # JWT
    major_abbr: str
    iq: int = LEGACY_INITIAL_STAT_DEFAULTS["iq"]
    eq: int = LEGACY_INITIAL_STAT_DEFAULTS["eq"]
    luck: int = LEGACY_INITIAL_STAT_DEFAULTS["luck"]
    charm: int = LEGACY_INITIAL_STAT_DEFAULTS["charm"]
    stats: Optional[Dict[str, int]] = None


class CourseOption(BaseModel):
    id: str
    name: str
    credits: float
    difficulty: int


class InitCharacterResponse(BaseModel):
    success: bool
    major: str
    major_abbr: str
    courses: List[CourseOption]


class AdmissionInfoResponse(BaseModel):
    username: str
    assigned_major: str
    token: str


# ─── 安全校验 ───

def _validate_invite_code(code: str) -> bool:
    raw = settings.INVITE_CODES.strip()
    if not raw:
        return False
    codes = [c.strip() for c in raw.split(",") if c.strip()]
    candidate = code.strip()
    return any(secrets.compare_digest(candidate, valid_code) for valid_code in codes)


def _initial_stats_from_request(req: InitCharacterRequest) -> Dict[str, int]:
    raw_stats = req.stats
    allow_missing = False
    if raw_stats is None:
        raw_stats = {
            stat.id: getattr(req, stat.id, stat.default)
            for stat in stat_definitions.allocatable
        }
        allow_missing = True
    try:
        return stat_definitions.normalize_initial_allocations(
            raw_stats,
            allow_missing=allow_missing,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


def _validate_initial_stats(req: InitCharacterRequest):
    _initial_stats_from_request(req)


# ─── 路由 ───


@router.post("/auth", response_model=AuthResponse)
async def auth(data: AuthRequest, db: DbSessionDep):
    """邀请码认证：验证用户名+邀请码，返回 JWT 和持久凭证"""
    is_safe_username, username, username_error = validate_username(data.username)
    if not is_safe_username:
        return AuthResponse(
            status="error",
            username=username,
            message=username_error or "用户名包含不允许的内容",
        )

    if await RestrictionService.is_blacklisted(db, username, "username"):
        return AuthResponse(
            status="error", username=username,
            message="该用户名已被拉黑",
        )
    if data.token and await RestrictionService.is_blacklisted(db, data.token, "token"):
        return AuthResponse(
            status="error", username=username,
            message="该凭证已被拉黑",
        )

    if not _validate_invite_code(data.invite_code):
        return AuthResponse(
            status="error", username=username,
            message="邀请码无效",
        )

    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        # 新用户
        user_token = secrets.token_urlsafe(16)
        user = User(
            username=username,
            token=user_token,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        jwt_token = create_access_token(
            data={"sub": str(user.id), "username": user.username}
        )
        return AuthResponse(
            status="new_user",
            jwt=jwt_token,
            user_token=user_token,
            username=user.username,
            user_id=user.id,
        )

    # 老用户
    if data.token and user.token == data.token:
        restriction = await RestrictionService.get_active_restriction(db, user.id)
        if restriction:
            return AuthResponse(
                status="error",
                username=username,
                message=f"账号受限：{restriction.restriction_type}",
            )
        saves = await SaveService.list_saves(str(user.id), db)
        jwt_token = create_access_token(
            data={"sub": str(user.id), "username": user.username}
        )
        return AuthResponse(
            status="returning",
            jwt=jwt_token,
            username=user.username,
            user_id=user.id,
            saves=[SaveSummary(**s) for s in saves],
        )

    return AuthResponse(
        status="error", username=username,
        message="用户名已被占用，请填写老玩家凭证重试",
    )


@router.get("/majors", response_model=List[MajorOption])
async def get_majors():
    """返回 majors.json 中所有可选专业"""
    world = WorldService()
    all_majors = await world.get_all_majors()
    return [MajorOption(**m) for m in all_majors]


@router.post("/init_character", response_model=InitCharacterResponse)
async def init_character(req: InitCharacterRequest, db: DbSessionDep):
    """初始化角色：选择专业并分配初始属性"""
    stat_overrides = _initial_stats_from_request(req)
    # 解码 JWT
    try:
        payload = jwt.decode(
            req.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id_raw = payload.get("sub")
        username_raw = payload.get("username")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if not user_id_raw:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user_id = str(user_id_raw)
    username = str(username_raw) if username_raw else None

    stmt = select(User).where(User.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    restriction = await RestrictionService.get_active_restriction(db, int(user_id))
    if restriction:
        raise HTTPException(
            status_code=403, detail=f"账号受限：{restriction.restriction_type}"
        )

    # 查找专业
    world = WorldService()
    major = await world.get_major_by_abbr(req.major_abbr)
    if not major:
        raise HTTPException(status_code=404, detail=f"专业 {req.major_abbr} 不存在")

    # 初始化 Redis 游戏状态
    redis_client = RedisCache.get_client()
    repo = RedisRepository(user_id, redis_client)
    game_service = GameService(str(user_id), repo, world)

    result = await game_service.assign_major_and_init(
        major_abbr=req.major_abbr,
        stat_overrides=stat_overrides,
        username=username or user.username,
    )

    return InitCharacterResponse(
        success=True,
        major=result["major"],
        major_abbr=result["major_abbr"],
        courses=result["courses"],
    )


# ─── 入学信息查询（admission_info） ───


@router.get("/admission_info", response_model=AdmissionInfoResponse)
async def get_admission_info(
    authorization: AuthorizationHeader,
    db: DbSessionDep,
):
    """查询当前用户的用户名和已分配专业"""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username_raw = payload.get("username")
        user_id_raw = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if not user_id_raw:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user_id = str(user_id_raw)
    username = str(username_raw) if username_raw else None

    state = RedisState(user_id)
    stats = await state.get_stats()
    major = stats.get("major")

    stmt = select(User).where(User.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    response_username = username or user.username
    return AdmissionInfoResponse(
        username=response_username,
        assigned_major=major or "未分配专业",
        token=user.token or "",
    )
