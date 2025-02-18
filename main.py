import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "search_bot.settings")
django.setup()
from telegram.ext import MessageHandler, filters, ApplicationBuilder, CommandHandler
from bot.views import start_command, handle_message

TOKEN = '7764254536:AAHP_CN3cyh7utv7oY4W1DPWpkMNOSOIwcQ'

if __name__ == "__main__":
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()