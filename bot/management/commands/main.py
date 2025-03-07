import os
import django
from django.core.management import BaseCommand
from telegram.ext import MessageHandler, filters, ApplicationBuilder, CommandHandler
from bot.handlers import handle_message, start_command
from search_bot.settings import API_KEY

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "search_bot.settings")
django.setup()


# ---------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------
class Command(BaseCommand):
    help = "Запускает Telegram-бота"

    def handle(self, *args, **options):
        # application = ApplicationBuilder().token(API_KEY).concurrent_updates(True).build()
        application = ApplicationBuilder().token(API_KEY).build()

        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )
        application.add_handler(CommandHandler("start", start_command)),

        self.stdout.write("Бот запущен, начинается polling...")
        application.run_polling()
