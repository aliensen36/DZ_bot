# from tortoise.models import Model
# from tortoise import fields
#
#
# class User(Model):
#     id = fields.IntField(pk=True)
#     tg_id = fields.BigIntField(unique=True)
#     is_bot = fields.BooleanField(default=False)
#     first_name = fields.CharField(max_length=64, default="Unknown")
#     last_name = fields.CharField(max_length=64, null=True)
#     username = fields.CharField(max_length=32, null=True, unique=True)
#     phone_number = fields.CharField(max_length=20, null=True)
#     created_at = fields.DatetimeField(auto_now_add=True)
#     updated_at = fields.DatetimeField(auto_now=True)
#     last_activity = fields.DatetimeField(null=True)
#
#     card = fields.OneToOneField(
#         'models.LoyaltyCard',
#         related_name='card_owner',
#         null=True,
#         on_delete=fields.SET_NULL
#     )
#
#     class Meta:
#         table = "users"
#         indexes = [("tg_id",), ("username",)]
#
#     def __str__(self):
#         return f"{self.tg_id} ({self.username or self.first_name})"
#
# class Mailing(Model):
#     """Модель для хранения информации о рассылках"""
#     id = fields.IntField(pk=True)
#     from_user = fields.ForeignKeyField("models.User", related_name="mails", on_delete=fields.CASCADE)
#     text = fields.TextField()
#     image = fields.CharField(max_length=255, null=True)
#     button_url = fields.CharField(max_length=255, null=True)
#     type = fields.CharField(max_length=20, default="text", choices=["news", "advertising", "promotion", "poster", "other"])
#     created_at = fields.DatetimeField(auto_now_add=True)
#
#     class Meta:
#         table = "mails"
#         indexes = [("from_user",)]
#
#     def __str__(self):
#         return f"{self.from_user} ({self.created_at})"
