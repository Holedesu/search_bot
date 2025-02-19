import asyncio
import time

from asgiref.sync import sync_to_async
from playwright.async_api import async_playwright
from telegram import Update
from telegram.ext import ContextTypes
import requests
from bs4 import BeautifulSoup

from io import BytesIO
from bot.models import TelegramUser, UserMessage
from django.http import HttpResponse
from reportlab.pdfgen import canvas


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await sync_to_async(TelegramUser.objects.get_or_create)(
        telegram_id=update.effective_user.id,

    )
    await update.message.reply_text('Привет! Я твой бот-помощник. Введи название товара, который вы хотите найти,'
                              ' а я постараюсь вывести для вас варианты')

async def scroll_smoothly(page, steps=20, delay=0.5):
    """Плавно прокручивает страницу вниз."""
    total_height = await page.evaluate("document.body.scrollHeight")
    step_size = total_height / steps  # Размер одного шага

    for i in range(steps):
        await page.evaluate(f"window.scrollBy(0, {step_size})")
        await asyncio.sleep(delay)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message.text

    response_in_chat = f"Вы сказали: {message}"
    search_url = f"https://www.avito.ru/all?q={message.replace(' ', '+')}"
    # await update.message.reply_text("Произвожу поиск")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(search_url)


        await update.message.reply_text("Сканирую страницу")
        await scroll_smoothly(page, steps=20, delay=0.5)
        await update.message.reply_text("Сканирование завершено")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36"
        }
        response = requests.get(search_url, headers=headers)

        soup = BeautifulSoup(response.text, "lxml")
        results = []
        results2 = []
        items_img = await page.query_selector_all('div.iva-item-content-OWwoq')

        for item in items_img[:50]:
            img_tag = await item.query_selector("img")
            img_url = await img_tag.get_attribute("src") if img_tag else "Нет фото"
            print(f"{img_url}")
            results2.append(img_url)

        for item in soup.find_all("div", class_="iva-item-content-OWwoq"):
            text_tag = item.find("p", class_="styles-module-root-s4tZ2 "
                                         "styles-module-size_s-nEvE8 styles-module-size_s_compensated-wyNaE "
                                         "styles-module-size_s-PDQal styles-module-ellipsis-A5gkK "
                                         "stylesMarningNormal-module-root-_xKyG "
                                         "stylesMarningNormal-module-paragraph-s-HX94M "
                                         "styles-module-noAccent-XIvJm styles-module-root_bottom-x1f86 "
                                         "styles-module-margin-bottom_6-SOtsv")
            text = text_tag.text.strip() if text_tag else "Нет данных"
            text = text[:200]
            print(f"{text}")
            results.append(f"{text}")

    await browser.close()
    # await generate_pdf(message, results)
    await update.message.reply_text("Поиск завершен")


async def generate_pdf(title, info):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename='custom_report.pdf'"

    p = canvas.Canvas(response)

    for data in info:
        img_url, text = data.split("\n")
        response_img = requests.get(img_url)
        print(text)
    p.showPage()
    p.save()

    return response

