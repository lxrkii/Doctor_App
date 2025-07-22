from tortoise import fields
from tortoise.models import Model
from .user import User

class WearSession(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField('models.User', related_name='wear_sessions')
    date = fields.DateField()
    start_time = fields.DatetimeField()
    end_time = fields.DatetimeField(null=True)
    duration_seconds = fields.IntField(null=True)

    class Meta:
        table = "wear_sessions" 