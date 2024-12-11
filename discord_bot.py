import os
import discord
import requests
import asyncio
from dotenv import load_dotenv
from discord.ext import commands, tasks
from mongodb_scraper import MongoDBScraper  # Import the scraper class
from discord_webs import DiscordWebhookManager  # Import the webhook manager

# Load environment variables from .env file
load_dotenv()

class DiscordBot:
    def __init__(self):
        self.TOKEN = os.getenv("DISCORD_BOT_TOKEN")
        self.WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
        self.MONGO_CLUSTER = os.getenv("MONGO_CLUSTER")
        self.MONGO_URI = f"mongodb+srv://{os.getenv('username')}:{os.getenv('password')}@self.MONGO_CLUSTER"
        self.COLLECTION_NAME = os.getenv("COLLECTION_NAME")
        self.DATABASE_NAME = os.getenv("DATABASE_NAME")
        # Initialize the MongoDB scraper
        self.scraper = MongoDBScraper(self.MONGO_URI, self.DATABASE_NAME , self.COLLECTION_NAME)
        
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        self.bot.remove_command('help')
        
        # Bind events and commands
        self.setup_commands()

    def setup_commands(self):
        @self.bot.event
        async def on_ready():
            print(f'Logged in as {self.bot.user}')

        @self.bot.command()
        async def send(ctx):
            await self.send_message_to_webhook(ctx)

        @self.bot.command()
        async def start(ctx, min_price: int, max_price: int, location: str):
            await self.start_monitoring(ctx, min_price, max_price, location)

        @self.bot.command()
        async def stop(ctx):
            await self.stop_monitoring(ctx)

        @self.bot.command()
        async def help(ctx):
            await self.display_help(ctx)

    async def send_message_to_webhook(self, ctx):
        response = requests.post(self.WEBHOOK_URL, json={"content": "Hello from your Discord bot!"})
        if response.status_code == 204:
            await ctx.send("Message sent to webhook!")
        else:
            await ctx.send(f"Failed to send message. Status code: {response.status_code}, Response: {response.text}")

    @tasks.loop(minutes=5)
    async def monitor_items(self, min_price, max_price, location):
        """Monitor items and update the MongoDB collection."""
        try:
            print("Starting the scraper...")
            items = self.scraper.scrape_pages(min_price, max_price, location)  # Scrape pages
            update_info = self.scraper.update_collection(items, min_price, max_price, location)  # Update MongoDB with scraped items

            webhook_manager = DiscordWebhookManager(self.WEBHOOK_URL, min_price, max_price, location)
            for item in update_info['new_entries']:
                if min_price <= item['price'] <= max_price:
                    webhook_manager.send_webhook_message(item, "Added")
            for item in update_info['price_changes']:
                if min_price <= item['price'] <= max_price:
                    webhook_manager.send_webhook_message(item, "Price Changed")

        except Exception as e:
            print(f"An error occurred during monitoring: {e}")

    async def start_monitoring(self, ctx, min_price, max_price, location):
        """Start monitoring with a price range and location."""
        if self.monitor_items.is_running():
            self.monitor_items.cancel()
            await asyncio.sleep(1)  # Ensure the task fully stops
        
        # Start the monitoring task
        self.monitor_items.start(min_price, max_price, location)
        await ctx.send(f"Monitoring started for items priced between {min_price} and {max_price} in {location}!")

    async def stop_monitoring(self, ctx):
        """Stop monitoring."""
        if self.monitor_items.is_running():
            self.monitor_items.stop()
            await ctx.send("Monitoring has been stopped.")
        else:
            await ctx.send("Monitoring is not currently active.")

    async def display_help(self, ctx):
        help_message = (
            "Available commands:\n"
            "`!send` - Send a test message to the webhook.\n"
            "`!start <min_price> <max_price> <location>` - Start monitoring with price range and location.\n"
            "`!stop` - Stop monitoring.\n"
            "`!help` - Display this help message."
        )
        await ctx.send(help_message)

    def run(self):
        self.bot.run(self.TOKEN)

if __name__ == "__main__":
    bot = DiscordBot()
    bot.run()
