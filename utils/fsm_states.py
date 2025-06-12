from email.mime import image
from aiogram.fsm.state import State, StatesGroup


class MailingFSM(StatesGroup):
    """Состояния FSM для процесса создания рассылки.

    States:
        text: Состояние ввода текста рассылки.
        image: Состояние добавления изображения.
        button_url: Состояние добавления ссылки для кнопки.
        wait: Состояние ожидания подтверждения.
    """
    text = State()
    image = State()
    button_url = State()
    wait = State()
    
