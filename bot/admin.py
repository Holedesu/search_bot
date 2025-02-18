from django.contrib import admin

from .models import TelegramUser, UserMessage


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "first_interaction")

@admin.register(UserMessage)
class UserMessageAdmin(admin.ModelAdmin):
    list_display = ("user", "message" ,"timestamp")