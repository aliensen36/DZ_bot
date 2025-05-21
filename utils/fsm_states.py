from email.mime import image
from aiogram.fsm.state import State, StatesGroup


class MailingFSM(StatesGroup):
    text = State()
    image = State()
    button_url = State()
    wait = State()
    
