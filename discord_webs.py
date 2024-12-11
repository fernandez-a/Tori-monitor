import os
from discord_webhook import DiscordWebhook, DiscordEmbed
from pymongo import MongoClient
from datetime import datetime, timedelta

class DiscordWebhookManager:
    def __init__(self, webhook_url, min_price, max_price, location):
        self.webhook_url = webhook_url
        self.min_price = min_price
        self.max_price = max_price
        self.location = location

    def send_webhook_message(self, item, action):
        webhook = DiscordWebhook(url=self.webhook_url)
        coords = f"https://www.google.com/maps/place/{item['coords']['lat']},{item['coords']['lon']}"
        color_map = {
            "Added": int("28a745", 16),
            "Sold": int("dc3545", 16),
            "Price Changed": int("ffc107", 16)
        }

        embed_color = color_map.get(action, 0x03b2f8)
        embed = DiscordEmbed(title=f"{action}:", color=embed_color)

        if item.get('image_urls'):
            embed.set_image(url=item['image_urls'][0])
        embed.set_timestamp()

        embed.add_embed_field(name="🏷️ Product", value=str(item['title']).capitalize(), inline=True)
        embed.add_embed_field(name="🏷️ ID", value=item['id'], inline=True)
        if action == 'Price Changed':
            embed.add_embed_field(name="💰 Last Price", value=f"{item.get('old_price')} {item['currency']}", inline=True)
            embed.add_embed_field(name="📉 New Price", value=f"{item['price']} {item['currency']}", inline=True)
        else:
            embed.add_embed_field(name="💰 Price", value=f"{item['price']} {item['currency']}", inline=True)
        
        embed.add_embed_field(name="📅 Timestamp", value=item['timestamp'])
        embed.add_embed_field(name="🛒 Buy Now", value=f"[Click here to buy now!]({item['url']})")
        embed.add_embed_field(name="🌍 Location", value=f"[{item['location']}]({coords})", inline=False)

        webhook.add_embed(embed)
        response = webhook.execute()
        if response.status_code == 200:
            print(f"Webhook message sent successfully for action: {action}.")
        else:
            print(f"Failed to send webhook message: {response.status_code}")

def check_collection(mongo_uri, db_name, collection_name, webhook_url, min_price, max_price, location):
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]
    
    webhook_manager = DiscordWebhookManager(webhook_url, min_price, max_price, location)
    now = datetime.utcnow()

    current_items = {str(item['_id']): item for item in collection.find({
                'trade_type': 'Myydään',
                'price': {'$gte': min_price, '$lte': max_price},
                'location': {'$regex': f'.*{location}.*', '$options': 'i'}
            })}

    for item_id, item in current_items.items():
        last_notified = item.get("last_notified")
        
        if last_notified:
            last_notified_time = datetime.strptime(last_notified, "%Y-%m-%d %H:%M:%S")
            if now - last_notified_time < timedelta(minutes=10):
                continue

        existing_item = {str(item['_id']): item for item in collection.find({'_id': item['_id']})}
        if existing_item is None:
            action = "Added"
        elif item['price'] != existing_item.get('price'):
            item['old_price'] = existing_item['price']
            action = "Price Changed"
        else:
            continue

        webhook_manager.send_webhook_message(item, action)
        collection.update_one(
            {"_id": item['_id']},
            {"$set": {"last_notified": now.strftime("%Y-%m-%d %H:%M:%S"), "status": action, 'old_price': item.get('old_price')}},
            upsert=True
        )

    for item in collection.find({"trade_type": 'Myydään', "_id": {"$nin": list(current_items.keys())}}):
        last_notified = item.get("last_notified")
        if last_notified:
            last_notified_time = datetime.strptime(last_notified, "%Y-%m-%d %H:%M:%S")
            if now - last_notified_time < timedelta(minutes=10):
                continue
        
        webhook_manager.send_webhook_message(item, "Sold")
        collection.update_one(
            {"_id": item['_id']},
            {"$set": {"last_notified": now.strftime("%Y-%m-%d %H:%M:%S"), "status": "Sold"}}
        )
