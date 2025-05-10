from tortoise.models import Model
from tortoise import fields


class User(Model):
    id = fields.IntField(pk=True)
    tg_id = fields.BigIntField(unique=True)
    is_bot = fields.BooleanField(default=False)
    first_name = fields.CharField(max_length=64, default="Unknown")
    last_name = fields.CharField(max_length=64, null=True)
    username = fields.CharField(max_length=32, null=True, unique=True)
    phone_number = fields.CharField(max_length=20, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    last_activity = fields.DatetimeField(null=True)

    class Meta:
        table = "users"
        indexes = [("tg_id",), ("username",)]

    def __str__(self):
        return f"{self.tg_id} ({self.username or self.first_name})"
