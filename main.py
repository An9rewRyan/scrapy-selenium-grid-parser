from fastapi import FastAPI, Query
from models import ProductInfo, City, Categorie
from fastapi import HTTPException
from typing import Optional
from spiders.spider import MySpider
from scrapy.utils.project import get_project_settings
from tasks import run_spider
import asyncio
from celery.exceptions import TimeoutError
import json
import os
from loaders.cities import update_cities
from loaders.categories import update_categories

tags_metadata = [
    {
        "name": "goods",
        "description": "Получение группы товаров с фильтрацией, либо одной позиции по идентификатору.",
    },
    {
        "name": "cities",
        "description": "Получение списка всех городов, которые обслуживаются на сайте и дополнительной информации о них.",
    },
    {
        "name": "categories",
        "description": "Получение списка доступных на сайте категорий и ссылок для них, которые понадобятся для работы с методами 'goods'. (из-за особенностей api сайта, данные грузятся чуть дольше обычного)",
    },
]

description = """
AptekaParsingApp - это переработанный api сайта https://apteka-ot-sklada.ru/. 
Данная документация позволяет ознакомится с доступными методами для прямого получения информации о товарах с их сайта
(и не только).

В разработке:

* **Фронтэнд интерфейс на реакт** .
* **Подключение базы данных и фоновая подгрузка** .
"""

app = FastAPI(
    title="AptekaParsingApp",
    description=description,
    version="0.0.1",
    contact={
        "name": "Михаил Еременко",
        "url": "https://t.me/Michael_J_Goldberg",
        # "email": "mjgoldberg123321@gmail.com",
    },
    openapi_tags=tags_metadata
)

from enum import Enum

# from fastapi import FastAPI


class SortName(str, Enum):
    popularity = "popindex"
    name = "name"
    price_to_high = "price_asc"
    price_to_low = "proce_desc"

# class YesNo(int, Enum):
#     aviliable = 1
#     not_aviliable = 0

@app.get("/cities/", response_model=list[City], tags=["cities"])
def get_cities():
    cities_json = update_cities()
    cities_formatted = []
    for city in cities_json:
        cities_formatted.append(City(**city))
    return cities_formatted

@app.get("/categories/", response_model=list[Categorie], tags=["categories"])
def get_cities():
    categories_json = update_categories()
    categories_formatted = []
    for categorie in categories_json:
        categories_formatted.append(Categorie(**categorie))
    return categories_formatted

@app.get("/goods/{good_id}", response_model=ProductInfo, responses={404: {"description": "requested id didn't match any positions"}}, tags=["goods"])
def read_item(good_id: int):
    spider = MySpider(name='new_spider')
    good_dict = spider.parse_good(good_id)
    if good_dict is None or good_dict == 'HTTP/1.1 404 Not Found':
        raise HTTPException(status_code=404, detail="Item not found")
    good = ProductInfo(**good_dict)
    return good

@app.get("/goods", response_model = list[ProductInfo], responses={404: {"description": "requested id didn't match any positions"}}, tags=["goods"])
async def read_items(city: Optional[int] = Query(None, gt=0, lt=1000, description="город для которого будет отправляться запрос (идентификатор)", example="92"),     
                     category: str = Query(max_length=300,description="категория в формате ссылки", example="medikamenty-i-bady/zabolevaniya-mochepolovoy-sistemy"),                      
                     sortby: Optional[SortName] = Query(None, description="метод сортировки"),
                     mincost: Optional[int] = Query(None, gt=0, lt=100000, description="минимальная цена"),
                     maxcost: Optional[int] = Query(None, gt=0, lt=100000, description=" максимальная цена"), 
                     onsold: Optional[int] = Query(None, gt=-1, lt=2, description="доступность в продаже (1/0)"),     
                     limit: Optional[int] = Query(None, gt=0, lt=100, description="пагинация результатов"),      
                     ondiscount: Optional[int] = Query(None, gt=-1, lt=2, description="наличие скидки (1/0)"),
                    ):
    print(onsold, type(onsold))
    params = {'city': city,
              'cat': category,
              'sortBy': sortby, 
              'filter':{
                  'mincost':mincost,
                  'maxcost':maxcost,
                  'onsold':onsold,
                  'limit':limit,
                  'ondiscount':ondiscount
              }}
    # из-за проблем с асинхронным запуском спайдер запускается в виде задачи в celery
    task = run_spider.delay(params=params)
    correct_response = False

    for _ in range(50): 
        try:
            # если задача выдала результат, значит парсинг окончен
            result = task.get(timeout=10) 
            print(result)
            if result['spider_closed']:
                correct_response = True
                break
        except TimeoutError: 
            # иначе ждем и проверяем снова
            print('Ожидаем выполнения...')
            await asyncio.sleep(5) 

    if not correct_response:
        raise HTTPException(status_code=404, detail="Items not found")
    
    # Получаем список файлов во временной директории
    dir_path = os.path.join('results', 'current')
    files = os.listdir(dir_path)

    # Читаем содержимое файлов и переформатируем под модель ProductInfo
    product_info_list = []
    for file in files:
        file_path = os.path.join(dir_path, file)
        product_info = read_product_info(file_path)
        product_info_list.append(product_info)
    
    # Удаляем временные файлы
    for f in os.listdir(dir_path):
        os.remove(os.path.join(dir_path, f))

    return product_info_list

def read_product_info(file_path: str) -> ProductInfo:
    # принимает путь к файлу и возвращает значение в готовом на вывод формате
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return ProductInfo(**data)
