from aiogram.types import BotCommand


bot_cmds_list = [
    BotCommand(command='start', description='Рестарт бота'),
    BotCommand(command='help', description='Справка по работе бота'),
    BotCommand(command='admin', description='Админ-панель'),
    BotCommand(command='res_admin', description='Админ-панель резидента'),
]