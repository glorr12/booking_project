from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from simple_history.models import HistoricalRecords

from core.models import TimeStampedModel, UniqueID


class AccountRole(models.TextChoices):
    TENANT = 'tenant', 'Tenant'
    LANDLORD = 'landlord', 'Landlord'


class AccountManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address.')

        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_landlord', extra_fields.get('role') == AccountRole.LANDLORD)

        account = self.model(email=self.normalize_email(email), **extra_fields)
        account.set_password(password)
        account.save(using=self._db)
        return account

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', AccountRole.LANDLORD)

        if not extra_fields.get('is_staff'):
            raise ValueError('A superuser requires is_staff=True.')
        if not extra_fields.get('is_superuser'):
            raise ValueError('A superuser requires is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(UniqueID, TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, verbose_name='Email')
    name = models.CharField(max_length=150, verbose_name='Name')
    role = models.CharField(
        max_length=10,
        choices=AccountRole.choices,
        default=AccountRole.TENANT,
        verbose_name='Role',
    )
    is_staff = models.BooleanField(default=False, verbose_name='Staff status')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    # `role` is kept as the user's primary/default persona; `is_landlord` is separate so a
    # tenant can also list properties without switching their whole account over.
    is_landlord = models.BooleanField(default=False, verbose_name='Can list properties')

    objects = AccountManager()

    history = HistoricalRecords()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        db_table = 'users'
        ordering = ('-created_at',)
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email