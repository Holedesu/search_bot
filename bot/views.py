import asyncio
import os
import logging
import ssl

import aiohttp

from io import BytesIO

from asgiref.sync import sync_to_async
from playwright.async_api import async_playwright
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib import colors

from telegram import Update
from telegram.ext import ContextTypes

from bot.models import TelegramUser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

FONT_PATH_REG = os.path.join("fonts/open-sans", "OpenSans-Regular.ttf")
FONT_PATH_BOLD = os.path.join("fonts/open-sans", "OpenSans-Bold.ttf")
pdfmetrics.registerFont(TTFont('OpenSans', FONT_PATH_REG))
pdfmetrics.registerFont(TTFont('OpenSansBold', FONT_PATH_BOLD))

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Пользователь {update.effective_user.id} вызвал /start")

    # Синхронная операция с базой через sync_to_async
    await sync_to_async(TelegramUser.objects.get_or_create)(
        telegram_id=update.effective_user.id,
    )
    await update.message.reply_text(
        'Привет! Я твой бот-помощник. Введи название товара, который вы хотите найти, а я постараюсь найти для вас варианты.'
    )

async def scroll_smoothly(page, steps=20, delay=0.5):
    logger.debug(f"Начинаю плавный скролл: шагов={steps}, задержка={delay}")
    total_height = await page.evaluate("document.body.scrollHeight")
    step_size = total_height / steps

    for i in range(steps):
        await page.evaluate(f"window.scrollBy(0, {step_size})")
        await asyncio.sleep(delay)
    logger.debug("Скролл завершён")

async def parse_avito(query: str, limit=50):
    logger.info(f"Парсим Avito для запроса: '{query}'")
    search_url = f"https://www.avito.ru/all?q={query.replace(' ', '+')}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        logger.debug("Браузер Chromium запущен (headless=True)")
        page = await browser.new_page()
        await page.goto(search_url)
        logger.debug(f"Перешли на страницу: {search_url}")

        await scroll_smoothly(page, steps=10, delay=0.3)

        items = await page.query_selector_all("div.iva-item-content-OWwoq")
        logger.info(f"Найдено {len(items)} элементов на странице")

        pics_results = []
        text_results = []

        for i, item in enumerate(items[:limit]):
            img_tag = await item.query_selector("img")
            img_url = "Нет фото"
            if img_tag:
                temp_url = await img_tag.get_attribute("src")
                if temp_url:
                    img_url = temp_url

            text_div_list = await item.query_selector_all("div.iva-item-bottomBlock-FhNhY")
            raw_text = "Нет описания"
            if text_div_list:
                text_div = text_div_list[0]
                text_tag = await text_div.query_selector("p")
                if text_tag:
                    raw_text_temp = await text_tag.inner_text()
                    if raw_text_temp:
                        raw_text = raw_text_temp.strip()

            logger.debug(f"[{i}] Картинка: {img_url}, Текст: {raw_text[:50]}...")

            pics_results.append(img_url)
            text_results.append(raw_text)

        image_readers = await download_all_images(pics_results)
        await browser.close()
        logger.debug("Браузер Chromium закрыт")

    return image_readers, text_results

async def download_image(url):
    if url == "Нет фото":
        return None

    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5, ssl=ssl_context) as response:
                if response.status == 200:
                    data = await response.read()  # Считываем данные в бинарном виде
                    return ImageReader(BytesIO(data))
                else:
                    logger.warning(f"Ошибка загрузки {url}: статус {response.status}")
                    return None
    except Exception as e:
        logger.warning(f"Ошибка загрузки {url}: {e}")
        return None

async def download_all_images(urls):
    tasks = [download_image(url) for url in urls]
    images = await asyncio.gather(*tasks)
    return images

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

async def generate_pdf_file(pics_url_array, text_array, file_path="output.pdf"):
    logger.info(f"Начинаем генерацию PDF: {file_path}")

    page_width, page_height = A4
    c = canvas.Canvas(file_path, pagesize=A4)

    cols = 5
    padding_x = 2
    padding_y = 2
    img_height = 77
    img_width = ((page_width - 77) - (cols - 1) * padding_x) / cols

    c.setFont("OpenSans", 14)
    c.drawString(40, page_height - 30, f"Объявление: ")

    y_start = page_height - img_height - 40
    x_start = 100

    for i, url in enumerate(pics_url_array):
        col = i % cols
        row = i // cols

        x = x_start + col * (img_width - 23)
        y = y_start - (row * (img_height + padding_y))

        if url:
            c.drawImage(url, x, y, img_width, img_height, preserveAspectRatio=True, anchor='c')

    c.showPage()

    text_y = page_height - 50
    max_text_width = page_width - 80
    min_text_space = 50
    first_page = True

    for idx, text in enumerate(text_array):
        header_height = 20

        short_text = text[:100]
        text_height_short = wrap_text(c, short_text, 40, text_y, max_text_width, test_mode=True) + 10

        long_text = text[:200]
        text_height_long = wrap_text(c, long_text, 40, text_y, max_text_width, test_mode=True) + 10

        block_height = header_height + text_height_short + text_height_long

        if not first_page and (text_y - block_height < min_text_space):
            c.showPage()
            text_y = page_height - 50

        first_page = False

        c.setFont("OpenSansBold", 11)
        header = f"Объявление: {idx + 1}"
        c.drawString(40, text_y, header)
        text_y -= 10

        c.setFont("OpenSans", 10)
        h1 = wrap_text(c, short_text, 40, text_y, max_text_width)
        text_y -= (h1 + 10)

        c.setFont("OpenSans", 10)
        h2 = wrap_text(c, long_text, 40, text_y, max_text_width)
        text_y -= (h2 + 30)

    c.save()
    logger.info(f"PDF успешно сгенерирован: {file_path}")
    return file_path

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message.text
    logger.info(f"Получено сообщение от пользователя {update.effective_user.id}: {message}")

    await update.message.reply_text(f"Вы сказали: {message}")
    await update.message.reply_text("Произвожу поиск на Avito...")

    pics_results, text_results = await parse_avito(message, limit=50)

    await update.message.reply_text("Генерирую PDF...")
    pdf_path = await generate_pdf_file(pics_results, text_results, "output.pdf")

    logger.info(f"Отправляем PDF {pdf_path} пользователю {update.effective_user.id}")
    with open(pdf_path, "rb") as doc:
        await update.message.reply_document(doc, filename="output.pdf")

    logger.info("Сообщение с PDF успешно отправлено пользователю")