import asyncio
import os
import logging

from asgiref.sync import sync_to_async
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib import colors

from telegram import Update
from telegram.ext import ContextTypes

from bot.models import TelegramUser
from bot.parser import parse_avito

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Настройка логов
# ---------------------------------------------------------------------
FONT_PATH_REG = os.path.join("fonts/open-sans", "OpenSans-Regular.ttf")
FONT_PATH_BOLD = os.path.join("fonts/open-sans", "OpenSans-Bold.ttf")
pdfmetrics.registerFont(TTFont("OpenSans", FONT_PATH_REG))
pdfmetrics.registerFont(TTFont("OpenSansBold", FONT_PATH_BOLD))

# ---------------------------------------------------------------------
# Функция для обработки команды /start
# ---------------------------------------------------------------------


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /start, создаёт запись пользователя в БД (если её нет),
    и отправляет приветственное сообщение.
    """
    logger.info(f"Пользователь {update.effective_user.id} вызвал /start")

    await sync_to_async(TelegramUser.objects.get_or_create)(
        telegram_id=update.effective_user.id,
    )
    await update.message.reply_text(
        "Привет! Я твой бот-помощник. Введите ссылку, а я постараюсь найти для вас варианты."
    )


# ---------------------------------------------------------------------
# Функция для переноса текста в пдф файле
# ---------------------------------------------------------------------


def wrap_text(c, text, x, y, max_width, test_mode=False):
    """
    Оборачивает текст в заданной области.

    :param c: Объект Canvas.
    :param text: Текст.
    :param x: Координата X.
    :param y: Координата Y.
    :param max_width: Максимальная ширина строки.
    :param test_mode: Если True, просто рассчитывает высоту текста без отрисовки.
    :return: Высота блока текста.
    """
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


# ---------------------------------------------------------------------
# Функция для создания фала в формате пдф
# ---------------------------------------------------------------------
async def generate_pdf_file(
    pics_url_array, text_array, title_array, company_info, file_path="output.pdf"
):
    """
    Создаёт PDF с изображениями и описаниями объявлений.

    :param pics_url_array: Список объектов ImageReader.
    :param title_array: Список заголовков объявлений.
    :param text_array: Список текстов объявлений.
    :param file_path: Имя файла.
    :return: Путь к созданному PDF.
    """
    logger.info(f"Начинаем генерацию PDF: {file_path}")

    page_width, page_height = A4
    c = canvas.Canvas(file_path, pagesize=A4)

    cols = 5
    padding_x = 2
    padding_y = 2
    img_height = 77
    img_width = ((page_width - 77) - (cols - 1) * padding_x) / cols

    c.setFont("OpenSans", 14)
    c.drawString(40, page_height - 30, "Изображения по запросу: ")

    y_start = page_height - img_height - 40
    x_start = 100

    for i, url in enumerate(pics_url_array):
        col = i % cols
        row = i // cols

        x = x_start + col * (img_width - 23)
        y = y_start - (row * (img_height + padding_y))

        if url:
            c.drawImage(
                url, x, y, img_width, img_height, preserveAspectRatio=True, anchor="c"
            )

    c.showPage()

    text_y = page_height - 50
    max_text_width = page_width - 80
    min_text_space = 50
    first_page = True

    for idx, text in enumerate(text_array):
        header_height = 20

        short_text = text[:100]
        text_height_short = (
            wrap_text(c, short_text, 40, text_y, max_text_width, test_mode=True) + 10
        )

        long_text = text[:200]
        text_height_long = (
            wrap_text(c, long_text, 40, text_y, max_text_width, test_mode=True) + 10
        )

        block_height = header_height + text_height_short + text_height_long

        if not first_page and (text_y - block_height < min_text_space):
            c.showPage()
            text_y = page_height - 50

        first_page = False

        c.setFont("OpenSansBold", 11)
        header = f"Объявление {idx + 1}: {title_array[idx]}"
        c.drawString(40, text_y, header)
        text_y -= 10

        c.setFont("OpenSans", 10)
        company_price = f"Цена: {company_info[idx][0]}"
        h1 = wrap_text(c, company_price, 40, text_y, max_text_width)
        text_y -= h1 + 10

        c.setFont("OpenSans", 10)
        company_name = f"Компания/ИП: {company_info[idx][1]}"
        h1 = wrap_text(c, company_name, 40, text_y, max_text_width)
        text_y -= h1 + 10

        c.setFont("OpenSans", 10)
        company_rating = f"Рейтинг: {company_info[idx][2]}"
        h1 = wrap_text(c, company_rating, 40, text_y, max_text_width)
        text_y -= h1 + 10

        c.setFont("OpenSans", 10)
        company_reviews = f"Кол-во отзывов: {company_info[idx][3]}"
        h1 = wrap_text(c, company_reviews, 40, text_y, max_text_width)
        text_y -= h1 + 10

        c.setFont("OpenSans", 10)
        h1 = wrap_text(c, short_text, 40, text_y, max_text_width)
        text_y -= h1 + 10

        c.setFont("OpenSans", 10)
        h2 = wrap_text(c, long_text, 40, text_y, max_text_width)
        text_y -= h2 + 30

    c.save()
    logger.info(f"PDF успешно сгенерирован: {file_path}")
    return file_path


# ---------------------------------------------------------------------
# Функция обрабатывающая запрос пользователя и возвращающая готовый пдф файл
# ---------------------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает текстовые сообщения от пользователя в Telegram.

    1. Получает текстовое сообщение от пользователя.
    2. Запускает процесс парсинга Avito для поиска товаров по введённому запросу.
    3. Генерирует PDF-файл с найденными объявлениями.
    4. Отправляет PDF обратно пользователю в Telegram.

    :param update: Объект обновления Telegram API, содержащий данные о входящем сообщении.
    :param context: Контекст бота, содержащий дополнительную информацию.
    """
    message = update.message.text
    logger.info(
        f"Получено сообщение от пользователя {update.effective_user.id}: {message}"
    )

    await update.message.reply_text(f"Вы сказали: {message}")
    await update.message.reply_text("Произвожу поиск на Avito...")



    try:
        asyncio.create_task(process_and_send_pdf(update, message))
    except Exception as e:
        await update.message.reply_text("Произошла непредвиденная ошибка, попробуйте позже")
        logger.error(f"Ошибка при запуске браузера: {e}")


async def process_and_send_pdf(update: Update, message: str):
    pics_results, text_results, title_results, company_info = await parse_avito(
        message, limit=50
    )

    await update.message.reply_text("Генерирую PDF...")
    pdf_path = await generate_pdf_file(
        pics_results, text_results, title_results, company_info, "output.pdf"
    )

    with open(pdf_path, "rb") as doc:
        await update.message.reply_document(doc, filename="output.pdf")

    logger.info("PDF отправлен пользователю")
