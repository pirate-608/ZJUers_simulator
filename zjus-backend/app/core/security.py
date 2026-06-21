"""JWT creation and verification helpers.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
Game HTTP and WebSocket entry points share this module to keep token lifetime
and signing behavior consistent.
"""

from datetime import datetime, timedelta

from jose import jwt

from app.core.config import settings


def create_access_token(data: dict):
    """Create a signed JWT with the configured access-token lifetime."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt
