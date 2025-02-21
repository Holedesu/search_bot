import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "search_bot.settings")
django.setup()
from telegram.ext import MessageHandler, filters, ApplicationBuilder, CommandHandler
from bot.views import start_command, handle_message

TOKEN = '7764254536:AAHP_CN3cyh7utv7oY4W1DPWpkMNOSOIwcQ'

#---------------------------------------------------------------------
# Точка входа
#---------------------------------------------------------------------
if __name__ == "__main__":
    """
    Инициализирует и запускает Telegram-бота.

    1. Создаёт экземпляр приложения с токеном бота.
    2. Добавляет обработчики команд и текстовых сообщений.
    3. Запускает бот в режиме polling (опрос сервера Telegram на новые сообщения).

    Примечание:
    - Для работы необходимо предварительно задать переменную `TOKEN` (API-ключ бота).
    - Используется библиотека `python-telegram-bot` версии 20+.
    """
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()