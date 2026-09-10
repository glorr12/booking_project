import uuid

from django.db import models


class UniqueID(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4, verbose_name='ID')

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated at')

    class Meta:
        abstract = True