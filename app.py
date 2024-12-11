import os
import threading
import asyncio
from discord_bot import DiscordBot
from flask_app import app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_flask():
    app.run(host='0.0.0.0', port=8080)  # Flask will run on port 8080

def start_discord_bot():
    # Initialize the Discord bot instance
    bot_instance = DiscordBot()
    
    # Create and set a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Run the bot asynchronously in the new event loop
        loop.run_until_complete(bot_instance.run())
    finally:
        # Close the loop to clean up resources
        loop.close()

def main():
    # Start the Flask application in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    print("Flask app started...")

    # Start the Discord bot in a separate thread
    discord_thread = threading.Thread(target=start_discord_bot)
    discord_thread.start()
    print("Discord bot started...")

    # Join threads to ensure they run concurrently without early termination
    flask_thread.join()
    discord_thread.join()

if __name__ == "__main__":
    main()  # Start both Flask and Discord bot concurrently
