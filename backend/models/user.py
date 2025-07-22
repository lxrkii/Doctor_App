from tortoise import fields
from tortoise.models import Model

class User(Model):
    id = fields.IntField(pk=True)
    telegram_id = fields.BigIntField(unique=True)
    phone_hash = fields.CharField(max_length=128, null=True)
    name = fields.CharField(max_length=128, null=True)
    name_locked = fields.BooleanField(default=False)  # Блокировка изменения имени
    clinic_patient_id = fields.CharField(max_length=64, null=True)
    current_aligner_number = fields.IntField()
    last_aligner_change_date = fields.DateField()
    aligner_change_interval_days = fields.IntField(default=14)
    daily_goal_hours = fields.FloatField(default=22)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users" 