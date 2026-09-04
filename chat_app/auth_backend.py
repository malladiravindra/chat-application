from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class PhoneAuthBackend(ModelBackend):
    """
    Authenticates users by phone_number + password.
    Since phone_number IS the USERNAME_FIELD, standard ModelBackend
    already handles it — but we override authenticate() explicitly
    to support both `phone_number` kwarg and the default `username` kwarg.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # Accept phone_number kwarg OR the default username kwarg
        phone_number = kwargs.get("phone_number") or username
        if not phone_number:
            return None

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return None

        if not user.is_verified:
            return None  # Block unverified accounts from logging in

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
