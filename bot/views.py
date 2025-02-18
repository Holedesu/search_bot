from asgiref.sync import sync_to_async
from telegram import Update
from telegram.ext import ContextTypes
import requests
from bs4 import BeautifulSoup

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

    # user, created = await sync_to_async(TelegramUser.objects.get_or_create)(
    #     telegram_id=user_id,
    #     defaults={"first_interaction": update.message.date}
    # )
    #
    # await sync_to_async(UserMessage.objects.get_or_create)(
    #     user=user,
    #     message=message,
    #     defaults={"first_interaction": update.message.date}
    # )
    response_in_chat = f"Вы сказали: {message}"
    search_message =f"https://www.avito.ru/all?q={message.replace(' ', '+')}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36"
    }
    response = requests.get(search_message, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "lxml")
        results = []

        for item in soup.find_all("div", class_="iva-item-content-OWwoq"):

            text = item.find("p", class_="styles-module-root-s4tZ2 "
                                             "styles-module-size_s-nEvE8 styles-module-size_s_compensated-wyNaE "
                                             "styles-module-size_s-PDQal styles-module-ellipsis-A5gkK "
                                             "stylesMarningNormal-module-root-_xKyG "
                                             "stylesMarningNormal-module-paragraph-s-HX94M "
                                             "styles-module-noAccent-XIvJm styles-module-root_bottom-x1f86 "
                                             "styles-module-margin-bottom_6-SOtsv")
            text = text.text.strip() if text else "Нет данных"

            img_tag = item.find("img")
            img_url = img_tag["src"] if img_tag and "src" in img_tag.attrs else "Нет изображения"

            results.append(f"{img_url}\n {text}")
            if len(results) >= 50:
                break

            for item in results:
                print(item)

    else:
        return ["Ошибка при получении данных с Avito."]

    await update.message.reply_text(response_in_chat)
