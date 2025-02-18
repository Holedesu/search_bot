from asgiref.sync import sync_to_async
from telegram import Update
from telegram.ext import ContextTypes

from bot.models import TelegramUser, UserMessage


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await sync_to_async(TelegramUser.objects.get_or_create)(
        telegram_id=update.effective_user.id,

    )
    await update.message.reply_text('Привет! Я твой бот-помощник. Введи название товара, который вы хотите найти,'
                              ' а я постараюсь вывести для вас варианты')



async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    message = update.message.text

    user, created = await sync_to_async(TelegramUser.objects.get_or_create)(
        telegram_id=user_id,
        defaults={"first_interaction": update.message.date}
    )

    await sync_to_async(UserMessage.objects.get_or_create)(
        user=user,
        message=message,
        defaults={"first_interaction": update.message.date}
    )
    response = f"Вы сказали: {message}"
    await update.message.reply_text(response)
