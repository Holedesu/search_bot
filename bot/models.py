from datetime import datetime

from django.db import models


class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField(unique=True, verbose_name="ID пользователя")
    first_interaction = models.DateTimeField(
        verbose_name="Дата первого взаимодействия", default=datetime.now
    )
