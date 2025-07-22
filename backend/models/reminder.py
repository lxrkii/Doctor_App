from tortoise import fields
from tortoise.models import Model
from .user import User

class Reminder(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField('models.User', related_name='reminders')
    type = fields.CharField(max_length=32)
    scheduled_for = fields.DatetimeField()
    sent = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "reminders" 