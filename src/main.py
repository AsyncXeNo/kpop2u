from __future__ import annotations

import time
import asyncio

from apify import Actor, Request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        start_urls = actor_input.get('urls')

        if not start_urls:
            Actor.log.info('No start URLs specified in actor input, exiting...')
            await Actor.exit()

        request_queue = await Actor.open_request_queue()

        for start_url in start_urls:
            url = start_url.get('url')
            Actor.log.info(f'Enqueuing {url} ...')
            new_request = Request.from_url(url)
            await request_queue.add_request(new_request)

        Actor.log.info('Launching Chrome WebDriver...')
        chrome_options = ChromeOptions()

        if Actor.config.headless:
            chrome_options.add_argument('--headless')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        driver = webdriver.Chrome(options=chrome_options)

        data = []

        while request := await request_queue.fetch_next_request():
            url = request.url

            Actor.log.info(f'Scraping {url} ...')

            try:
                await asyncio.to_thread(driver.get, url)

                collection_divs = driver.find_elements(By.CSS_SELECTOR, '.product--large .collections-in-product-page2 a')
                collections = [collection_div.get_attribute('innerText').strip() for collection_div in collection_divs]

                title = driver.find_element(By.CSS_SELECTOR, '.product--large .product__title h1').get_attribute('innerText').strip()

                price = float(driver.find_element(By.CSS_SELECTOR, '.product--large .price__sale .price-item--sale').get_attribute('innerText').replace('$', '').replace('USD', '').replace(',', '').strip())

                main_image = driver.find_element(By.CSS_SELECTOR, '.product--large .product__media img').get_attribute('src')

                image_tags = driver.find_elements(By.CSS_SELECTOR, '.product--large .product__media img')
                images = [image.get_attribute('src') for image in image_tags]

                description = driver.find_element(By.CSS_SELECTOR, '.product--large .product__description').get_attribute('innerText').strip()

                description_image_tags = driver.find_elements(By.CSS_SELECTOR, '.product--large .product__description img')
                description_images = [image.get_attribute('src') for image in description_image_tags]

                variant_labels = driver.find_elements(By.CSS_SELECTOR, '.product--large variant-radios label')
                variant_info = []
                for variant_label in variant_labels:
                    variant_label.click()
                    time.sleep(0.5)
                    variant_price = float(driver.find_element(By.CSS_SELECTOR, '.product--large .price__sale .price-item--sale').get_attribute('innerText').replace('$', '').replace('USD', '').replace(',', '').strip())
                    variant_image = driver.find_element(By.CSS_SELECTOR, '.product--large .product__media img').get_attribute('src')
                    variant_info.append({
                        'name': variant_label.get_attribute('innerText').strip(),
                        'price': variant_price,
                        'image': variant_image
                    })

                data.append({
                    'url': url,
                    'title': title,
                    'collections': collections,
                    'price': price,
                    'main_image': main_image,
                    'images': images,
                    'description_images': description_images,
                    'description': description,
                    'variants': variant_info
                })

            except Exception:
                Actor.log.exception(f'Cannot extract data from {url}.')

            finally:
                await request_queue.mark_request_as_handled(request)

        driver.quit()

        await Actor.push_data({
            'urls': data
        })