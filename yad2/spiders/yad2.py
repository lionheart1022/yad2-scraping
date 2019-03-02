# -*- coding: utf-8 -*-
import scrapy
import requests
import re
from googletrans import Translator
import json
import time
from scrapy.conf import settings
import traceback


class Yad2Item(scrapy.Item):
    # define the fields for your item here like:
    address = scrapy.Field()
    spec = scrapy.Field()
    price = scrapy.Field()
    phone_num = scrapy.Field()
    description = scrapy.Field()
    updated_date = scrapy.Field()
    ad_num = scrapy.Field()
    pass


class Yad2Spider(scrapy.Spider):
    name = "yad2_spider"
    allowed_domains = ['yad2.co.il']
    start_url = 'https://www.yad2.co.il/api/search/engine/realestate/forsale'
    SEARCH_URL = 'https://www.yad2.co.il/realestate/forsale/?city=5000&' \
                 'neighborhood=205&' \
                 'property={property}&' \
                 'rooms=1-12&page={page}'

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/72.0.3626.119 Safari/537.36'
    }

    def __init__(self, *args, **kwargs):
        super(Yad2Spider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

        settings.overrides['DOWNLOAD_DELAY'] = 2

    def start_requests(self):
        yield scrapy.Request(self.start_url,
                             callback=self.parse_search_url, headers=self.HEADERS)

    def parse_search_url(self, response):
        property_value_list = []
        search_bar = None

        try:
            # data = requests.get(self.start_url, headers=self.HEADERS).json()
            search_bar = json.loads(response.body)['search_bar']['items']
            # search_bar = data['search_bar']['items']
        except:
            self.log('Error parsing Search Bar content: {}'.format(traceback.format_exc()))

        if search_bar:
            for row in search_bar:
                if self.translateArabic(row['title']) == 'asset':
                    for data in row['fields'][0]['dataFromMethod']:
                        property_value_list.append(data['value'])

            for property_value in property_value_list:
                for page in range(1, 6):
                    url = self.SEARCH_URL.format(property=property_value, page=page)
                    yield scrapy.Request(url, callback=self.parse_product, headers=self.HEADERS)

    def parse_product(self, response):
        item = Yad2Item()

        item_id_list = re.findall('feedItemCode:"(.*?)&', response.body_as_unicode())

        for item_id in item_id_list:
            main_data = self.get_main_json(item_id)

            street = None
            important_info_items = main_data['important_info_items']
            for important_info in important_info_items:
                if self.translateArabic(important_info['key']).lower() == 'street':
                    street = self.translateArabic(important_info['value'])

            address_home_number = main_data['address_home_number']

            item['address'] = '{} {}'.format(street, address_home_number)
            item['price'] = main_data.get('price')
            item['ad_num'] = main_data.get('ad_number')

            info_bar_items = main_data.get('info_bar_items')

            rooms = None
            floor = None
            meters = None

            for info_bar_item in info_bar_items:
                if info_bar_item.get('key') == 'rooms':
                    rooms = info_bar_item.get('titleWithoutLabel')
                if info_bar_item.get('key') == 'floor':
                    floor = info_bar_item.get('titleWithoutLabel')
                if info_bar_item.get('key') == 'meter':
                    meters = info_bar_item.get('titleWithoutLabel')

            spec = {
                'square_meters': meters,
                'floor': floor,
                'rooms': rooms
            }
            item['spec'] = spec

            content = main_data.get('info_text')
            balconies = main_data.get('balconies')
            entry_date = main_data.get('date_of_entry')

            updated_date = main_data['date_raw']
            item['updated_date'] = updated_date.split(' ')[0]

            description = {
                'content': self.translateArabic(content),
                # 'content': content,
                'balconies': balconies,
                'entry_date': entry_date
            }
            item['description'] = description

            item['phone_num'] = self.get_phone_num(item_id)

            yield item

    def get_main_json(self, item_id):
        url = 'https://www.yad2.co.il/api/item/{}'.format(item_id)
        data = requests.get(url, headers=self.HEADERS).json()
        return data

    def get_phone_num(self, item_id):
        phone_num_list = []
        url = 'https://www.yad2.co.il/api/item/{}/contactinfo?id={}&isPlatinum=true'.format(item_id, item_id)
        data = requests.get(url, headers=self.HEADERS).json()
        phone_nums = data['data']['phone_numbers']
        for phone_num in phone_nums:
            phone_num_list.append(phone_num['title'])
        if len(phone_num_list) == 1:
            phone_num_list = phone_num_list[0]

        return phone_num_list

    def translateArabic(self, text):
        translator = Translator()
        return translator.translate(text).text

    def normalizeArabic(self, text):
        text = re.sub("[إأٱآا]", "ا", text)
        text = re.sub("ى", "ي", text)
        text = re.sub("ؤ", "ء", text)
        text = re.sub("ئ", "ء", text)
        return text
