import asyncio
from datetime import datetime, timedelta, time, date
from backend.models.reminder import Reminder
from backend.models.user import User
from backend.models.wear_session import WearSession
from aiogram import Bot

AFTER_STOP_MINUTES = 20
EVENING_HOUR = 20
LAGGING_HOUR = 15
LAGGING_PERCENT = 40

async def create_after_stop_reminder(user: User):
    scheduled_for = datetime.now() + timedelta(minutes=AFTER_STOP_MINUTES)
    await Reminder.create(user=user, type='after_stop', scheduled_for=scheduled_for, sent=False)

async def create_evening_reminder(user: User):
    today = date.today()
    scheduled_for = datetime.combine(today, time(hour=EVENING_HOUR))
    await Reminder.create(user=user, type='evening', scheduled_for=scheduled_for, sent=False)

async def create_lagging_reminder(user: User):
    today = date.today()
    scheduled_for = datetime.combine(today, time(hour=LAGGING_HOUR))
    await Reminder.create(user=user, type='lagging', scheduled_for=scheduled_for, sent=False)

async def create_aligner_change_reminders(user: User):
    # Дата следующей смены
    next_change = user.last_aligner_change_date + timedelta(days=user.aligner_change_interval_days)
    # За день до смены
    scheduled_for1 = datetime.combine(next_change - timedelta(days=1), time(hour=10))
    await Reminder.create(user=user, type='aligner_change_soon', scheduled_for=scheduled_for1, sent=False)
    # В день смены
    scheduled_for2 = datetime.combine(next_change, time(hour=10))
    await Reminder.create(user=user, type='aligner_change_today', scheduled_for=scheduled_for2, sent=False)

async def send_reminder(bot: Bot, reminder: Reminder):
    user = await reminder.user
    if reminder.type == 'after_stop':
        await bot.send_message(user.telegram_id, "Не забудьте надеть элайнеры!")
    elif reminder.type == 'evening':
        # Статистика за день
        today = date.today()
        sessions = await WearSession.filter(user=user, date=today).all()
        total_seconds = sum(s.duration_seconds or 0 for s in sessions)
        total_hours = total_seconds / 3600
        left = max(0, user.daily_goal_hours - total_hours)
        await bot.send_message(user.telegram_id, f"Сегодня вы носили элайнеры {total_hours:.1f} ч. До цели осталось {left:.1f} ч. Успейте надеть!")
    elif reminder.type == 'lagging':
        today = date.today()
        sessions = await WearSession.filter(user=user, date=today).all()
        total_seconds = sum(s.duration_seconds or 0 for s in sessions)
        total_hours = total_seconds / 3600
        percent = int((total_hours / user.daily_goal_hours) * 100) if user.daily_goal_hours else 0
        if percent < LAGGING_PERCENT:
            await bot.send_message(user.telegram_id, f"Внимание! Сейчас вы набрали только {total_hours:.1f} ч. Пора надеть элайнеры, чтобы успеть к цели!")
    elif reminder.type == 'aligner_change_soon':
        await bot.send_message(user.telegram_id, f"Завтра пора сменить элайнер на следующий №{user.current_aligner_number + 1}! Не забудьте.")
    elif reminder.type == 'aligner_change_today':
        await bot.send_message(user.telegram_id, f"Сегодня день смены! Переходите на элайнер №{user.current_aligner_number + 1}.")
    # ...добавить другие типы при необходимости...
    reminder.sent = True
    await reminder.save()

async def reminders_worker(bot: Bot):
    while True:
        now = datetime.now()
        reminders = await Reminder.filter(sent=False, scheduled_for__lte=now).all()
        for reminder in reminders:
            try:
                await send_reminder(bot, reminder)
            except Exception as e:
                print(f"Ошибка отправки напоминания: {e}")
        await asyncio.sleep(30) 