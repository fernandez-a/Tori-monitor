# mongodb_scraper.py
import os
import requests
from concurrent.futures import ThreadPoolExecutor
import datetime
from pymongo import MongoClient
import time
import asyncio
from dotenv import load_dotenv

class MongoDBScraper:
    def __init__(self, mongo_uri, db_name, collection_name):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        self.collection = self.db[self.collection_name]
        self.base_url = "https://www.tori.fi/recommerce-search-page/api/search/SEARCH_ID_BAP_COMMON?q=artek"
        self.is_running = False

    def fetch_page(self, page):
        """Fetch items from a specific page."""
        response = requests.get(f"{self.base_url}&page={page}")
        return response.json().get('docs', [])

    @staticmethod
    def get_date(timestamp):
        """Convert timestamp to a readable date format."""
        dt = datetime.datetime.fromtimestamp(timestamp / 1000)
        return dt.strftime('%d-%m-%Y')

    def scrape_pages(self, min_price, max_price, location):
        items = []
        total_pages = requests.get(self.base_url).json().get('metadata')['paging']['last']

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.fetch_page, page) for page in range(1, total_pages + 1)]
            for future in futures:
                items.extend([
                    {
                        'id': i['id'],
                        'title': i['heading'],
                        'location': i['location'],
                        'price': i['price']['amount'],
                        'currency': i['price']['currency_code'],
                        'image': i['image'].get('url') if 'image' in i else None,
                        'timestamp': self.get_date(i['timestamp']),
                        'coords': i.get('coordinates'),
                        'url': i['canonical_url'],
                        'image_urls': i.get('image_urls', []),
                        'trade_type': i['trade_type']
                    } for i in future.result()
                    if min_price <= i['price']['amount'] <= max_price
                    and location.lower() in i['location'].lower()
                ])
        return items


    def update_collection(self, items, min_price, max_price, location):
        """Compare scraped items with the collection and update the database."""
        # Filter only the existing items that match the min/max price and location
        existing_items = {
            str(item['_id']): item for item in self.collection.find({
                'trade_type': 'Myydään',
                'price': {'$gte': min_price, '$lte': max_price},
                'location': {'$regex': f'.*{location}.*', '$options': 'i'}
            })
        }

        # Filter new items based on the price and location constraints
        new_items = {
            item['id']: item for item in items
            if min_price <= item['price'] <= max_price and location.lower() in item['location'].lower()
        }

        price_changes = []
        new_entries = []
        items_to_remove = set(existing_items.keys()) - set(new_items.keys())

        # Identify new items and price changes
        for item_id, item in new_items.items():
            existing_item = existing_items.get(item_id)
            if existing_item:
                if existing_item['price'] != item['price']:
                    print(f"Price changed for {item['title']} from {existing_item['price']} to {item['price']}")
                    self.collection.update_one(
                        {'_id': existing_item['_id']},
                        {'$set': {'price': item['price'], 'old_price': existing_item['price']}}
                    )
                    price_changes.append(item)
            else:
                print(f"New item added: {item['title']}")
                new_entries.append(item)

        # Remove items no longer available
        if items_to_remove:
            print(f"Removing items no longer available: {items_to_remove}")
            self.collection.delete_many({'_id': {'$in': list(items_to_remove)}})

        # Insert new items
        if new_entries:
            self.collection.insert_many(new_entries)

        return {'price_changes': price_changes, 'new_entries': new_entries}


    async def run(self, min_price, max_price, location):
        """Main loop for scraping and updating the MongoDB collection."""
        self.is_running = True
        try:
            while self.is_running:
                print("Scraping pages...")
                items = self.scrape_pages()
                self.update_collection(items, min_price,max_price, location)
                print("Update complete. Waiting 10 minutes.")
                await asyncio.sleep(600)  # Wait 10 minutes before the next run
        except Exception as e:
            print(f"An error occurred in scraping: {e}")
        finally:
            self.is_running = False

    def start(self, min_price, max_price, location):
        """Start the scraper in a separate asyncio task."""
        asyncio.create_task(self.run(min_price, max_price, location))

    def stop(self):
        """Stop the scraper."""
        self.is_running = False
