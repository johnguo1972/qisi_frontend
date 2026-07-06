"""Custom DRF authentication that allows unauthenticated requests."""
from rest_framework_simplejwt.authentication import JWTAuthentication


class OptionalJWTAuthentication(JWTAuthentication):
    """JWT authentication that doesn't force authentication.

    Returns None if no Authorization header is present, allowing
    AllowAny permission to work properly.
    """

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None
        return super().authenticate(request)
