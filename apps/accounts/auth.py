"""Custom DRF authentication that allows unauthenticated requests."""
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .roles import VALID_ROLES, has_user_role


def get_request_role(request) -> str | None:
    """Return the independently authenticated role for this request."""
    active_role = getattr(request, 'active_role', None)
    if active_role:
        return active_role
    user = getattr(request, 'user', None)
    return getattr(user, 'role_type', None)


class OptionalJWTAuthentication(JWTAuthentication):
    """JWT authentication that doesn't force authentication.

    Returns None if no Authorization header is present, allowing
    AllowAny permission to work properly.
    """

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result
        active_role = (
            validated_token['active_role']
            if 'active_role' in validated_token
            else user.role_type
        )
        if getattr(user, 'status', None) != 'active':
            raise AuthenticationFailed('Account is inactive', code='ACCOUNT_INACTIVE')
        if active_role not in VALID_ROLES or not has_user_role(user, active_role):
            raise AuthenticationFailed('Role is no longer granted', code='ROLE_NOT_GRANTED')

        request.active_role = active_role
        user._active_role = active_role
        # Compatibility for existing permission code. This is the request-loaded
        # instance only and must never be persisted by authentication.
        user.role_type = active_role
        return user, validated_token
