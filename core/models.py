import uuid

from django.db import models
from django.utils import timezone


class UniqueID(models.Model):
    """
    Абстрактная базовая модель, заменяющая стандартный целочисленный ID на UUIDv4.
    Используется для повышения безопасности (защита от последовательного перебора ID)
    и удобства распределенных систем.
    """
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4, verbose_name='ID')

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """
    Абстрактная базовая модель для автоматического отслеживания времени создания и обновления записей
    """
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated at')

    class Meta:
        abstract = True


class SoftDeleteManager(models.Manager):
    """
    Менеджер для работы с моделями мягкого удаления
    """
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    """
    Абстрактная базовая модель, реализующая логику мягкого удаления.
    Вместо физического удаления записи из базы данных проставляет метку времени `deleted_at`.
    Предоставляет методы для полного удаления (`hard_delete`) и восстановления (`restore`).
    """
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Deleted at')

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self):
        """
        Проверяет, помечен ли объект как удаленный
        """
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False):
        """
        Выполняет мягкое удаление объекта, проставляя текущую дату и время в `deleted_at`
        """

        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=['deleted_at'])

    def hard_delete(self, using=None, keep_parents=False):
        """
        Выполняет физическое удаление объекта из базы данных
        """
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        """
        Восстанавливает мягко удаленный объект, сбрасывая поле `deleted_at` в null
        """
        self.deleted_at = None
        self.save(update_fields=['deleted_at'])