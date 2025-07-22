from tortoise import fields
from tortoise.models import Model

class Admin(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=64, unique=True)
    password_hash = fields.CharField(max_length=128)
    is_superuser = fields.BooleanField(default=False)

    class Meta:
        table = "admins" 