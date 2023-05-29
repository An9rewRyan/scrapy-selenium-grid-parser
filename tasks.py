from celery import Celery
# from scrapy.crawler import CrawlerProcess
# from spiders.spider import MySpider
# import subprocess
# from scrapy.crawler import CrawlerRunner
# from twisted.internet import reactor
# from scrapy import signals
# from scrapy.signalmanager import dispatcher

# # Создайте новый экземпляр Celery с именем 'tasks' и URL-адресом брокера.
app = Celery('tasks', broker='pyamqp://guest@rabbitmq//', backend='redis://redis:6379/0')

# # Определите вашу задачу Celery.
# from twisted.internet import reactor
# from scrapy.crawler import CrawlerRunner
# from scrapy import signals
# from scrapy.signalmanager import dispatcher

# @app.task
# def run_spider(params: dict):
#     result = {'spider_closed': False, 'reason': None, 'spider': None}

#     def spider_closed(spider, reason):
#         print('CRAWLING FINISHED!')
#         result['spider_closed'] = True
#         result['reason'] = reason
#         result['spider'] = spider.name
#         reactor.stop()

#     dispatcher.connect(spider_closed, signals.spider_closed)
#     runner = CrawlerRunner({"LOG_LEVEL": 'ERROR'})
#     d = runner.crawl(MySpider, params=params)
#     d.addBoth(lambda _: reactor.stop())
#     reactor.run() 

#     return result

import subprocess
import json

@app.task
def run_spider(params: dict):
    """Принимает набор параметров и передает их в паука. По завершении возвращает статус."""
    params_str = json.dumps(params)  
    # Из-за проблем с реактором скрапер запускается в отдельном подпроцессе
    command = f"scrapy runspider spiders/spider.py -a 'params="f"{params_str}'" 
    process = subprocess.Popen(command, shell=True)
    process.wait()  # Ожидаем завершения процесса
    return {"spider_closed": True}