from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
import urllib.parse
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user_from_token(token_key):
    try:
        access_token = AccessToken(token_key)
        user = User.objects.get(id=access_token['user_id'])
        return user
    except Exception as e:
        logger.debug(f"Invalid JWT token: {e}")
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Middleware that inspects query string `?token=<jwt>` or `Authorization: Bearer <jwt>`
    header to authenticate WebSocket connections via SimpleJWT.
    Falls back to Django session authentication if no JWT token is supplied.
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = urllib.parse.parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        # Check Authorization header if query param not found
        if not token:
            for header_name, header_val in scope.get("headers", []):
                if header_name.lower() == b"authorization":
                    try:
                        val_str = header_val.decode("utf-8")
                        if val_str.startswith("Bearer "):
                            token = val_str.split(" ", 1)[1].strip()
                    except Exception:
                        pass
                    break

        if token:
            user = await get_user_from_token(token)
            if user and not user.is_anonymous:
                scope["user"] = user
            else:
                scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
