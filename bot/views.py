import asyncio
import os
import time
import requests

from asgiref.sync import sync_to_async
from playwright.async_api import async_playwright
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from telegram import Update
from telegram.ext import ContextTypes

from bs4 import BeautifulSoup

from io import BytesIO
from bot.models import TelegramUser

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib import colors

FONT_PATH_REG = os.path.join("fonts/open-sans", "OpenSans-Regular.ttf")
FONT_PATH_BOLD = os.path.join("fonts/open-sans", "OpenSans-Bold.ttf")
pdfmetrics.registerFont(TTFont('OpenSans', FONT_PATH_REG))
pdfmetrics.registerFont(TTFont('OpenSansBold', FONT_PATH_BOLD))

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await sync_to_async(TelegramUser.objects.get_or_create)(
        telegram_id=update.effective_user.id,

    )
    await update.message.reply_text('Привет! Я твой бот-помощник. Введи название товара, который вы хотите найти,'
                              ' а я постараюсь вывести для вас варианты')

async def scroll_smoothly(page, steps=20, delay=0.5):
    total_height = await page.evaluate("document.body.scrollHeight")
    step_size = total_height / steps

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

        text_results = []
        pics_results = []
        items_img = await page.query_selector_all("div.iva-item-content-OWwoq")

        for item in items_img[:50]:
            img_tag = await item.query_selector("img")
            img_url = await img_tag.get_attribute("src") if img_tag else "Нет фото"
            pics_results.append(img_url)

            text_tags_div_list = await item.query_selector_all("div.iva-item-bottomBlock-FhNhY")

            text_tags_div = text_tags_div_list[0]
            text_tags = await text_tags_div.query_selector("p")
            text = await text_tags.inner_text()

            # print(text)
            text = text[:200]
            print(text)
            text_results.append(text)

    await browser.close()
    await generate_pdf(message, pics_results, text_results)
    with open("output.pdf", "rb") as document:
        await update.message.reply_document(document)

def download_image(url):
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return ImageReader(BytesIO(response.content))
    except requests.exceptions.RequestException as e:
        print(f"Ошибка загрузки {url}: {e}")
        return None

async def generate_pdf(title, pics_url_array, text_array):
    page_width, page_height = A4
    c = canvas.Canvas("output.pdf", pagesize=A4)

    cols = 5
    padding_x = 2
    padding_y = 2

    img_height = 77
    img_width = ((page_width - 77) - (cols - 1) * padding_x) / cols

    c.setFont("OpenSans", 14)
    c.drawString(40, page_height - 30, f"{title}: ")

    y_start = page_height - img_height - 40
    x_start = 100

    for i, url in enumerate(pics_url_array):
        col = i % cols
        row = i // cols

        x = x_start + col * (img_width - 23)
        y = y_start - (row * (img_height + padding_y))

        img = download_image(url)
        if img:
            c.drawImage(img, x, y, img_width, img_height, preserveAspectRatio=True, anchor='c')
    c.showPage()

    text_y = page_height - 50
    max_text_width = page_width - 80
    min_text_space = 50

    first_page = True

    for idx, text in enumerate(text_array):

        header_height = 20
        text_height = wrap_text(c, text, 40, text_y, max_text_width, test_mode=True) + 10


        if not first_page and text_y - (header_height + text_height) < min_text_space:
            c.showPage()
            c.setFont("OpenSansBold", 10)
            text_y = page_height - 50

        first_page = False


        c.setFont("OpenSansBold", 11)
        header = f"{title} {idx + 1}"
        c.drawString(40, text_y, header)
        text_y -= 20

        c.setFont("OpenSans", 10)
        h = wrap_text(c, text[:100], 40, text_y, max_text_width)
        text_y -= h + 15

        c.setFont("OpenSans", 10)
        h = wrap_text(c, text, 40, text_y, max_text_width)
        text_y -= h + 15

    c.save()


def wrap_text(c, text, x, y, max_width, test_mode=False):
    styles = getSampleStyleSheet()
    style = styles["Normal"]
    style.wordWrap = "CJK"
    style.fontName = "OpenSans"
    style.fontSize = 12
    style.textColor = colors.black

    p = Paragraph(text, style)

    w, h = p.wrap(max_width, 1000)

    if not test_mode:
        p.drawOn(c, x, y - h)

    return h


