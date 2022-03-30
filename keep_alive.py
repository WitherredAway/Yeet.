from flask import Flask
from threading import Thread
import random
import os


app = Flask("")


@app.route("/")
def home():
    return "Im in!"


def run():
    app.run(host="0.0.0.0", port=random.randint(7000, 8000))


def keep_alive():
    # Make it so it only runs on replit
    if not os.getenv("REPL_ID"):
        return
    t = Thread(target=run)
    t.start()
