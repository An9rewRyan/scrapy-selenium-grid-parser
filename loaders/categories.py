import json
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from spiders.spider import MySpider
from selenium.common.exceptions import TimeoutException

def prepare_click_buttons(driver):
    """Принимает драйвер и переходит в каталог категорий товаров"""
    driver.get("https://apteka-ot-sklada.ru/")
    button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable(
        (By.XPATH, "//div[@class='layout-city-confirm-dialog__controls']/button")))
    button.click()

    button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable(
        (By.XPATH, "//div[@class='layout-catalog-bar__catalog-trigger']/button")))
    button.click()


def scrape_data(driver):
    """Принимает драйвер и возвращает два идентичных словаря формата {категория:{подкатегория:[подподкатегория]}}:
       1) Словарь с именами категорий на сайте
       2) Словарь с именами категорий в формате url-запроса вида "medikamenty-i-bady/anesteziya-i-rastvoriteli";
       Структура словарей и позиции элементов идентичны, то есть: при запросе на идентичный индекс из словаря 1 в 
       словарь 2 можно получить соответствующую названию категории ссылку.
       Функция сначала собирает кнопки категорий, затем последовательно проходится по ним и сохраняет данные.
    """
    categories = {}
    links = {}
    cat_btns = driver.find_elements(By.XPATH, "//span[@class='ui-list-item__content']")

    for btn in cat_btns:
        name = btn.text
        categories[name] = {}
        links[name] = {}
    idx = 0
    while idx < len(categories):
        no_subcategories = False
        if idx:
            try:
                button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable(cat_btns[idx]))
                button.click()
            except TimeoutException:
                button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable(
                    (By.XPATH, "//div[@class='layout-catalog-bar__catalog-trigger']/button")))
                button.click()
                no_subcategories = True
        if no_subcategories:
            if idx == len(categories) -1:
                idx += 1
            categories[cat]= {}
            links[cat] = {}
            continue
        cat = list(categories.keys())[idx]

        subcats = driver.find_elements(By.XPATH, "//li[@class='layout-catalog-dropdown-subcategories__group']")
        # чтобы избежать лишних запросов данные по категории и подподкатегории собираются из общего элемента
        for subcat in subcats:
            html = subcat.get_attribute('innerHTML')
            soup = BeautifulSoup(html)
            subsubcats = soup.find_all("a", {"class" : "layout-catalog-dropdown-subcategories__link"}, href=True)
            sub = subsubcats[0].text.strip()
            sub_link = subsubcats[0]['href'][9:]
            categories[cat][sub] = []
            links[cat][sub_link] = []
            for subsubcat in subsubcats[1:]:
                categories[cat][sub].append(subsubcat.text.strip())
                links[cat][sub_link].append(subsubcat['href'][9:])
        idx += 1
    # последний элемент всегда грузится пустой
    categories.pop('', None)
    links.pop('', None)

    return categories, links


def save_cats(cats: dict, name: str):
    """Принимает словарь категорий и сохраняет его в каталоге "categories"."""
    cats_json = json.dumps(cats, ensure_ascii=False).encode('utf8')
    with open(f'results/{name}.json', 'w', encoding='utf-8') as file:
        file.write(cats_json.decode())

def load_dict(filename):
    with open(filename, 'r') as file:
        return json.load(file)

def load_dicts():
    names_dict = load_dict('results/names.json')
    links_dict = load_dict('results/links.json')

    return names_dict, links_dict

spider = MySpider(name='superspider')

def find_path_names(cats, cat_names):
    if not cats or not isinstance(cat_names, (dict, list)):
        return None

    for pos, category in enumerate(cat_names):
        if isinstance(cat_names, dict) and category == cats[0]:
            next_level = cats[1:]
            if not next_level:  # If we are at the last category
                return [pos]
            else:
                result = find_path_names(next_level, cat_names[category])
                if result is not None:
                    return [pos] + result
        elif isinstance(cat_names, list) and category == cats[0]:  # If we are at the last level and it's a list
            return [pos]
            
    return None

def find_path_links(way: list, cat_links: dict):
    cat = list(cat_links.keys())[way[0]]
    if len(way) == 1:
        return cat
    subcat = list(cat_links[cat].keys())[way[1]]
    if len(way) == 2:
        return subcat
    subsubcat = cat_links[cat][subcat][way[2]]
    if len(way) == 3:
        return subsubcat

def update_categories():
    """Объединяет функционал всех функций выше и возвращает словарь категорий формата {name:{parent_name, link}}"""
    driver = spider.setup_webdriver()
    prepare_click_buttons(driver)
    categories, links = scrape_data(driver)
    save_cats(categories, 'names')
    save_cats(links, 'links')
    categories_full = []
    names_dict, links_dict = load_dicts()
    # уровень категории
    for cat_name in list(names_dict.keys()):
        # уровень подкатегории
        path = []
        path.append(cat_name)
        for pos, subcat_name in enumerate(names_dict[cat_name]):
            path = [path[0]]
            path.append(subcat_name)
            name = subcat_name
            parent = cat_name
            path_ids = find_path_names(path, names_dict)
            print(path_ids, path)
            link = find_path_links(path_ids, links_dict)
            categories_full.append({'name':name, 'parent':parent, 'link':link})
            # уровень подподкатегории
            for subpos, subsubcat_name in enumerate(names_dict[cat_name][subcat_name]):
                path = path[:2]
                path.append(subsubcat_name)
                name = subsubcat_name
                parent = subcat_name
                path_ids = find_path_names(path, names_dict)
                print(path_ids, path)
                link = find_path_links(path_ids, links_dict)
                categories_full.append({'name':name, 'parent':parent, 'link':link})
    driver.quit()
    return categories_full

# print(update_categories())

# функции ниже использовались в целях тестирования и позволяли подгружать из файлов и сопоставлять категории --
# -- с сылками на них

# def compose_url(part_urlL: str) -> str:
#     full_url = f"https://apteka-ot-sklada.ru/api/catalog/search?sort=popindex&slug={part_urlL}&limit=30"
#     return full_url



