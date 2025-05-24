# import logging
# from datetime import datetime
# from typing import Optional
# from database.models import Mailing
#
# logger = logging.getLogger(__name__)
#
#
# class MailingRequests:
#     @staticmethod
#     async def create_mailing(from_user: User, text: str, image: Optional[str] = None, button_url: Optional[str] = None, type: Optional[str] = "other") -> Mailing:
#         """Создает рассылку"""
#         return await Mailing.create(
#             from_user=from_user,
#             text=text,
#             image=image,
#             button_url=button_url
#         )