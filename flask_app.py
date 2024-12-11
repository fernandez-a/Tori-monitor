from flask import Flask
import threading
import asyncio

app = Flask(__name__)

@app.route('/')
def index():
    return "Discord Bot is running!"

