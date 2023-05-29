import requests
import json

def update_cities():
    """Обновляет список доступных городов и возвращает его, в формате: {id: int, name: str, 
       slug: str (название на английском), isDelivery: (доступность доставки)}
    """
    base_url = "https://apteka-ot-sklada.ru/api/region"
    response = requests.get(base_url)
    data = response.json()

    id_list = [item["id"] for item in data]

    cities = []
    for id_ in id_list:
        response = requests.get(f"{base_url}/{id_}")
        data = response.json()
        for item in data:
            city = {key: item[key] for key in ["id", "name", "slug", "regionId", "isDelivery"]}
            cities.append(city)

    with open("results/cities.json", "w") as outfile:
        json.dump(cities, outfile, ensure_ascii=False)
    return cities