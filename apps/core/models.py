from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import models
from django.utils import timezone


class PasswordState(models.Model):
    """Tracks whether a user must replace their generated initial password."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_state',
    )
    must_change_password = models.BooleanField(default=False)
    generated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Password state for {self.user}'


class PasswordResetPIN(models.Model):
    """Single-use, short-lived PIN issued by an admin for a password reset."""

    MAX_ATTEMPTS = 5

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_pins',
    )
    pin_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Password reset PIN for {self.user}'

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def verify(self, pin):
        if self.is_used or self.is_expired or self.attempts >= self.MAX_ATTEMPTS:
            return False
        if check_password(pin, self.pin_hash):
            self.used_at = timezone.now()
            self.save(update_fields=['used_at'])
            return True
        self.attempts += 1
        self.save(update_fields=['attempts'])
        return False
