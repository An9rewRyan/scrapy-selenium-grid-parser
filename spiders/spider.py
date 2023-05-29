import scrapy
import base64
import json
import time
from scrapy.utils.project import get_project_settings
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver


settings = get_project_settings()

class MySpider(scrapy.Spider):
    name = 'new_spider'
    def __init__(self, params=None, *args, **kwargs):
        super(MySpider, self).__init__(*args, **kwargs)
        self.params = json.loads(params) if params else None
        self.base_url = 'https://apteka-ot-sklada.ru/api'
        # словарь допустимых параметров запроса в формате {alias:оригинальное название}
        self.allowed_params = {'sort':{
                                'popindex':'popindex',
                                'price_asc':'price_asc',
                                'price_desc':'price_desc',
                                'name':'name', 
                                },
                            'filter':{
                                'mincost':'costFrom', 
                                'maxcost':'costTo ',
                                'onsold':'inStock',
                                'ondiscount':'promoOnly',
                                'limit':'limit'
                                },
        }
    
    def start_requests(self):
        """Выполняет переход на запрашиваемый город для дальнейших запросов"""
        url = self.base_url + "/user/city/requestById"
        city_id = self.params['city'] if self.params['city'] else 92 #Томск
        next_url = self.format_url(self.params)
        city_request = scrapy.Request(url=url, method="POST", body=str({"id": city_id}), headers={'Content-Type': 'application/json', 'charset': 'UTF-8'}, callback=self.parse_goods_page, meta={"url":next_url})
        yield self.get_proxy_request(request = city_request)

    def get_proxy_request(self, request):
        """Принимает запрос, добавляет к нему данные для подключения к proxy серверу и
           возвращает дополненный запрос обратно
        """
        proxy_url = 'http://cproxy.site:10952'
        proxy_user = 'USuPgY'
        proxy_pass = 'SEHehSyt8Yz7'
        request.meta['proxy'] = proxy_url
        credentials = f'{proxy_user}:{proxy_pass}'
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        request.headers['Proxy-Authorization'] = f'Basic {encoded_credentials}'
        return request

    def parse_goods_page(self, response):
        """Загружает страницу с товарами и передает в обработчик"""
        parsing_url = response.meta["url"]
        req = scrapy.Request(url=parsing_url, callback=self.parse_goods)
        yield self.get_proxy_request(request = req)
    
    def parse_goods(self, response) -> list[dict]:
        """Проходится по полученному списку товаров, направляя запрос в обработчик страницы и возвращает список
           отформатированных данных.
        """
        goods = response.json()["goods"]
        goods_full = []
        driver = self.setup_webdriver()
        for good in goods:
            good_full = self.parse_good(good['id'], driver = driver, to_save=True, for_celery=False)
            goods_full.append(good_full)
        print('задание закончено.')
        driver.quit()
        self.state = 'Done'
        return goods_full


    def parse_good(self, idx: str, driver = None, to_save: bool = True, for_celery: bool = False) -> dict or str:
        """Принимает идентификатор товара, driver, переключатель для сохранения файла и выбора директории
           ('при for_celery = True' все данные сохраняются во временной директории). Возвращает отформатированный словарь
           товара либо строку с ошибкой. Функция может вызываться как сама по себе, так и внутри класса (для получение)
           одного или множества объектов соответственно.
        """

        # в случае если driver был передан из родительской функции, то используется именно он, в целях экономии времени.
        # (переподключение и пересоздание сессии длится не менее 10ти секунд)
        parent_driver = False
        if driver is None:
            driver = self.setup_webdriver()
        else:
            parent_driver = True
        url = self.base_url + f'/catalog/{idx}'
        driver.get(url)

        # так как по-дефолту используется driver Firefox, для получения чисто json надо нажать на переключатель
        button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, 'rawdata-tab')))
        button.click()
        product_info = json.loads(driver.find_element(By.CLASS_NAME, 'data').text)

        # в случае если страницы товара не существует, возвращаем 404
        if product_info == {"messages":["Goods not found(by f_get_goods_details)."]}:
            return "HTTP/1.1 404 Not Found"

        formatted_product_info = self.format_good(product_info)

        # здесь происходит сохранение файла в каталоге, соответсвующем его положению в иерархии категорий на сайте,
        # под именем формата {id}.json
        if to_save == True:
            category_path = "/".join([parent['name'] for parent in product_info['category']['parents']] + [product_info['category']['name']])
            file_path = os.path.join('results', category_path.replace(" ", "_"), f'{product_info["id"]}.json')
            self.save_good(formatted_product_info, idx, file_path, for_celery)
        
        # если функция запущена в цикле, то, в целях экономии, драйвер не перезапускается
        if not parent_driver:
            driver.quit()

        return formatted_product_info

    def format_good(self, product_info: dict):
        """Принимает неотформатированный json, находит вычисляемые свойства и возвращает объект
           в формате, запрошенном по заданию.
        """
        current_price = product_info['cost'] if product_info['cost'] is not None else 0.
        original_price = product_info['oldCost'] if product_info['oldCost'] is not None else 0.
        sale_tag = ""

        if current_price < original_price:
            discount_percent = ((original_price - current_price) / original_price) * 100
            sale_tag = f"Скидка {discount_percent:.0f}%"

        formatted_product_info = {
            "timestamp": int(time.time()),
            "RPC": None,  # Разные варианты товаров не были найдены 
            "url": f"{self.base_url}/catalog/{product_info['id']}",
            "title": product_info['name'],
            "marketing_tags": [f"{sticker['name']}" for sticker in product_info['stickers']],
            "brand": product_info['producer'],
            "section": [parent['name'] for parent in product_info['category']['parents']] + [product_info['category']['name']],
            "price_data": {
                "current": current_price,
                "original": original_price,
                "sale_tag": sale_tag
            },
            "stock": {
                "in_stock": product_info['inStock'],
                "count": product_info['availability'] 
            },
            "assets": {
                "main_image": f"{self.base_url}{product_info['images'][0]}" if product_info['images'] else "",
                "set_images": [f"{self.base_url}{image}" for image in product_info['images']],
                "view360": [],  # Поле не было найдено ни в одном из сотен товаров в разных категориях
                "video": []  # Поле не было найдено ни в одном из сотен товаров в разных категориях
            },
            "metadata": {
                "__description": product_info['description'],
                "АРТИКУЛ": None,  # Поле не было найдено ни в одном из сотен товаров в разных категориях
                "СТРАНА ПРОИЗВОДИТЕЛЬ": product_info['country']
            },
            "variants": 1 
        }
        return formatted_product_info
    
    def save_good(self, product_info: dict, idx: int, file_path: str, for_celery: bool = False) -> str:
        """Принимает отформатированный товар, его id, базовый путь к нему и переключатель celery 
           для сохранения во временном каталоге.
        """
        if not for_celery:
            print(file_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
        else:
            os.makedirs(os.path.dirname(f'results/current/{idx}.json'), exist_ok=True)
        with open(f'results/current/{idx}.json', 'w', encoding='utf-8') as f:
            json.dump(product_info, f, ensure_ascii=False)
        return "done!"
        
    def format_url(self, params):
        """Принимает параметры запроса в формате словаря и вовзращает ссылку с добавленными значениями.
        """
        url = f"https://apteka-ot-sklada.ru/api/catalog/search?"
        sort = ""
        filtr = ""
        if params['cat'] is None:
            return None
        slug = f"slug={params['cat']}"

        if params['sortBy'] is not None and params['sortBy'] in self.allowed_params['sort']:
            sort=f"&sort={params['sortBy']}"
        if params['filter'] is not None:
            for param_name in list(params['filter'].keys()):
                if param_name in self.allowed_params['filter']:
                    filtr+=f"&{self.allowed_params['filter'][param_name]}={params['filter'][param_name]}"
        return url + slug + sort + filtr

    def setup_webdriver(self):
        """Производит инициализацию драйвера и возвращает его."""
        options = webdriver.FirefoxOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--headless")

        # Аргументы ниже были использованы для запуска драйвера chrome, но он не был использован
        # из-за проблем при запуске в контейнере.

        # options.add_argument("start-maximized")
        # options.add_argument("disable-infobars")
        # options.add_argument("--disable-extensions")
        # options.add_argument("--disable-dev-shm-usage")
        # options.set_preference('intl.accept_languages', 'nl-NL, nl')
        # options.add_argument("--verbose")
        # options.add_argument("--no-sandbox")
        # options.add_argument("--disable-gpu")  # Добавить это
        # options.add_argument("--disable-software-rasterizer")

        driver = webdriver.Remote(
        command_executor="http://selenium-hub:4444/wd/hub",
        desired_capabilities={
                "browserName": "firefox",
            })
        return driver





    
    










