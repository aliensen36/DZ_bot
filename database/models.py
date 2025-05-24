from tortoise.models import Model
from tortoise import fields


class Mailing(Model):
    """Модель для хранения информации о рассылках"""
    id = fields.IntField(pk=True)
    from_user = fields.ForeignKeyField("models.User", related_name="mails", on_delete=fields.CASCADE)
    text = fields.TextField()
    image = fields.CharField(max_length=255, null=True)
    button_url = fields.CharField(max_length=255, null=True)
    type = fields.CharField(max_length=20, default="text", choices=["news", "advertising", "promotion", "poster", "other"])
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "mails"
        indexes = [("from_user",)]

    def __str__(self):
        return f"{self.from_user} ({self.created_at})"
