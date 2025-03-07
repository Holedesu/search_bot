import asyncio
import os
import logging
import ssl

import aiohttp

from io import BytesIO

from playwright.async_api import async_playwright
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.ttfonts import TTFont

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
# Функция для прогрузки данных перед их парсингом с Авито
# ---------------------------------------------------------------------


async def scroll_smoothly(page, steps=20, delay=0.5):
    """
    Выполняет плавный скроллинг страницы вниз для подгрузки данных.

    :param page: Объект страницы Playwright.
    :param steps: Количество шагов скроллинга.
    :param delay: Задержка между шагами (в секундах).
    """
    logger.debug(f"Начинаю плавный скролл: шагов={steps}, задержка={delay}")
    total_height = await page.evaluate("document.body.scrollHeight")
    step_size = total_height / steps
    for i in range(steps):
        await page.evaluate(f"window.scrollBy(0, {step_size})")
        await page.wait_for_selector("div.iva-item-content-OWwoq")
        await asyncio.sleep(delay)

    logger.debug("Скролл завершён")


# ---------------------------------------------------------------------
# Функция для загрузки картинки
# ---------------------------------------------------------------------


async def download_image(url):
    """
    Загружает изображение по URL и возвращает объект ImageReader.

    :param url: Ссылка на изображение.
    :return: Объект ImageReader или None, если загрузка не удалась.
    """
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


# ---------------------------------------------------------------------
# Функция для загрузки всех картинок
# ---------------------------------------------------------------------


async def download_all_images(urls):
    """
    Загружает все изображения из списка URL асинхронно.

    :param urls: Список строковых URL.
    :return: Список объектов ImageReader.
    """
    tasks = [download_image(url) for url in urls]
    images = await asyncio.gather(*tasks)
    return images


# ---------------------------------------------------------------------
# Функция парсинга с Авито
# ---------------------------------------------------------------------


async def parse_avito(query: str, limit=50, max_attempts=3):
    """
    Ищет товары на Avito, парсит страницу, извлекает изображения и описание.

    :param query: Строка поиска.
    :param limit: Максимальное количество объявлений для обработки.
    :param max_attempts: Количество попыток подгрузки данных при нехватке информации.
    :return: Список объектов ImageReader, список текстов и список заголовков объявлений.
    """
    logger.info(f"Парсим Avito для запроса: '{query}'")
    search_url = f"{query.replace(' ', '+')}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        logger.debug("Браузер Chromium запущен (headless=False)")
        page = await browser.new_page()
        await page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
        logger.debug(f"Перешли на страницу: {search_url}")

        attempt = 0
        pics_results = []
        text_results = []
        title_results = []
        company_info_results = []

        while attempt < max_attempts:
            attempt += 1
            logger.info(f"Попытка {attempt} загрузки данных...")
            await scroll_smoothly(page, steps=14, delay=1.0)
            items = await page.query_selector_all("div.iva-item-content-OWwoq")
            logger.info(f"Найдено {len(items)} элементов на странице")

            for i, item in enumerate(items[:limit]):
                img_tag = await item.query_selector("img")
                if img_tag:
                    temp_url = await img_tag.get_attribute("src")
                    if temp_url:
                        img_url = temp_url

                title_block = await item.query_selector("div.iva-item-body-GQomw")
                title_tag = await title_block.query_selector("a")
                title_text = await title_tag.inner_text()
                title_results.append(title_text)

                price_tag = await item.query_selector("span")
                price_result = await price_tag.inner_text()

                company_name_tag = await item.query_selector("div.style-root-Dh2i5")
                if company_name_tag:
                    company_nam = await company_name_tag.query_selector("p")
                    company_name = await company_nam.inner_text()
                else:
                    company_name = "Не предоставили"

                company_info_tag = await item.query_selector("div.style-root-Dh2i5")
                if company_info_tag and company_name != "Не предоставили":
                    combined_info = await company_info_tag.inner_text()
                    combined_info_sliced = combined_info[len(company_name):].replace(
                        "\n", ""
                    )
                    company_rating = combined_info_sliced[:3]
                    company_review = combined_info_sliced[3:]
                elif company_info_tag and company_name == "Не предоставили":
                    combined_info = await company_info_tag.inner_text()
                    co = combined_info.replace("\n", "")
                    company_review = f"Нет компании \n{co}"
                else:
                    company_rating = "Не предоставлено"
                    company_review = "Не предоставлено"

                temp_container = [
                    price_result,
                    company_name,
                    company_rating,
                    company_review,
                ]
                company_info_results.append(temp_container)

                text_div_list = await item.query_selector_all(
                    "div.iva-item-bottomBlock-FhNhY"
                )
                if text_div_list:
                    text_div = text_div_list[0]
                    text_tag = await text_div.query_selector("p")
                    if text_tag:
                        raw_text_temp = await text_tag.inner_text()
                        if raw_text_temp:
                            raw_text = raw_text_temp.strip()

                logger.debug(
                    f"[{i}] Картинка: {img_url}, Заголовок: {title_text},"
                    f" Текст: {raw_text[:50]}..."
                )
                logger.debug(
                    f"[{i}]Цена: {temp_container[0]}, Компания: {temp_container[1]},"
                    f" Рейтинг: {temp_container[2]} и {temp_container[3]}"
                )

                pics_results.append(img_url)
                text_results.append(raw_text)

            if len(pics_results) < len(items) or len(text_results) < len(items):
                logger.warning("Недостаточно данных, пробуем ещё раз...")
                await page.reload()
                continue
            else:
                break

        image_readers = await download_all_images(pics_results)
        await browser.close()
        logger.debug("Браузер Chromium закрыт")
    return image_readers, text_results, title_results, company_info_results
