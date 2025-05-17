import os
from aiogram import Bot, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message



# DB_URL = os.getenv("DB_URL")
#DB_HOST = os.getenv("DB_HOST")
#DB_PORT = os.getenv("DB_PORT")
#DB_USER = os.getenv("DB_USER")
#DB_PASS = os.getenv("DB_PASS")
#DB_NAME = os.getenv("DB_NAME")

 # sqlite
# TORTOISE_ORM = {
#     "connections": {
#         "default": DB_URL,
#     },
#     "apps": {
#         "models": {
#             "models": ["database.models", "aerich.models"],
#             "default_connection": "default",
#         },
#     },
# }

# postgres
#TORTOISE_ORM = {
#   "connections": {
#        "default": {
#            "engine": "tortoise.backends.asyncpg",
#            "credentials": {
#                "host": DB_HOST,
#                "port": DB_PORT,
#                "user": DB_USER,
#                "password": DB_PASS,
#                "database": DB_NAME,
#            },
#        }
#    },
#    "apps": {
#        "models": {
#            "models": ["app.database.models", "aerich.models"],
#            "default_connection": "default",
#        }
#    },
#}

