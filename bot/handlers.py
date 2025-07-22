from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from backend.models.user import User
from tortoise.exceptions import DoesNotExist
from backend.models.wear_session import WearSession
from datetime import datetime, date, timedelta
from tortoise.transactions import in_transaction
from bot.reminders import create_after_stop_reminder, create_evening_reminder, create_lagging_reminder, create_aligner_change_reminders
from backend.models.reminder import Reminder
import logging

logger = logging.getLogger(__name__)

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user is None:
        return
    logger.info(f"Received /start command from user {message.from_user.id}")
    telegram_id = message.from_user.id
    logger.info(f"Looking for user with telegram_id: {telegram_id}")
    user = await User.filter(telegram_id=telegram_id).first()
    logger.info(f"User found: {user is not None}")
    if not user:
        logger.info("Creating new user...")
        user = await User.create(
            telegram_id=telegram_id,
            name=message.from_user.first_name or None,
            current_aligner_number=1,
            last_aligner_change_date=message.date.date(),
            aligner_change_interval_days=14,
            daily_goal_hours=22
        )
        logger.info("User created successfully")
        await message.answer("Вы зарегистрированы! Введите ваше имя (или используйте текущее):")
        logger.info("Welcome message sent")
    else:
        logger.info("User already exists")
        try:
            await message.answer(f"С возвращением, {user.name or 'пациент'}! Используйте /profile для просмотра профиля.")
            logger.info("Return message sent")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            await message.answer("Произошла ошибка при отправке сообщения.")
    # Создаём вечернее и lagging-напоминание на сегодня, если их нет
    # today = date.today()
    # from datetime import datetime
    # today_start = datetime.combine(today, datetime.min.time())
    # today_end = datetime.combine(today, datetime.max.time())
    # if not await Reminder.filter(user=user, type='evening', scheduled_for__gte=today_start, scheduled_for__lte=today_end).exists():
    #     await create_evening_reminder(user)
    # if not await Reminder.filter(user=user, type='lagging', scheduled_for__gte=today_start, scheduled_for__lte=today_end).exists():
    #     await create_lagging_reminder(user)

@router.message(F.text)
async def set_name_if_needed(message: Message):
    if message.from_user is None:
        return
    # Проверяем, что это не команда
    if message.text is not None and message.text.startswith('/'):
        return
    telegram_id = message.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if user and not user.name and message.text is not None:
        user.name = message.text.strip()
        await user.save()
        await message.answer(f"Имя сохранено: {user.name}\nИспользуйте /profile для просмотра профиля.")

@router.message(Command("next"))
async def cmd_next(message: Message):
    if message.from_user is None:
        return
    telegram_id = message.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    user.current_aligner_number += 1
    user.last_aligner_change_date = date.today()
    await user.save()
    await message.answer(f"Поздравляем! Теперь у вас элайнер №{user.current_aligner_number}.")
    # Создаём напоминание о следующей смене
    await create_aligner_change_reminders(user)

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    if message.from_user is None:
        return
    logger.info(f"Received /profile command from user {message.from_user.id}")
    telegram_id = message.from_user.id
    logger.info(f"Looking for user with telegram_id: {telegram_id}")
    user = await User.filter(telegram_id=telegram_id).first()
    logger.info(f"User found: {user is not None}")
    if not user:
        logger.info("User not found, sending registration message")
        await message.answer("Вы не зарегистрированы. Используйте /start.")
        return
    logger.info("Building profile text...")
    text = (
        f"Профиль:\n"
        f"Имя: {user.name or 'не указано'}\n"
        f"Номер элайнера: {user.current_aligner_number}\n"
        f"Дата последней смены: {user.last_aligner_change_date}\n"
        f"График смены: {user.aligner_change_interval_days} дней\n"
        f"Цель по ношению: {user.daily_goal_hours} ч/сутки\n"
        f"/next — отметить смену каппы"
    )
    logger.info("Sending profile message...")
    try:
        await message.answer(text)
        logger.info("Profile message sent successfully")
    except Exception as e:
        logger.error(f"Error sending profile message: {e}")
        await message.answer("Произошла ошибка при отправке профиля.")

@router.message(Command("start_wear"))
async def cmd_start_wear(message: Message):
    if message.from_user is None:
        return
    telegram_id = message.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    # Проверяем, есть ли незавершённая сессия
    open_session = await WearSession.filter(user=user, end_time=None).first()
    if open_session:
        await message.answer("У вас уже запущена сессия ношения элайнеров.")
        return
    await WearSession.create(
        user=user,
        date=date.today(),
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None
    )
    await message.answer("Таймер ношения элайнеров запущен!")

@router.message(Command("stop_wear"))
async def cmd_stop_wear(message: Message):
    if message.from_user is None:
        return
    telegram_id = message.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    open_session = await WearSession.filter(user=user, end_time=None).first()
    if not open_session:
        await message.answer("Нет активной сессии ношения. Используйте /start_wear для запуска.")
        return
    end_time = datetime.now()
    duration = int((end_time - open_session.start_time).total_seconds())
    open_session.end_time = end_time
    open_session.duration_seconds = duration
    await open_session.save()
    await message.answer(f"Сессия завершена! Длительность: {duration // 3600}ч {(duration % 3600) // 60}м.")
    # Создаём напоминание надеть элайнеры через 20 минут
    await create_after_stop_reminder(user)

@router.message(Command("today"))
async def cmd_today(message: Message):
    if message.from_user is None:
        return
    telegram_id = message.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    today = date.today()
    sessions = await WearSession.filter(user=user, date=today).all()
    total_seconds = sum(s.duration_seconds or int((datetime.now() - s.start_time).total_seconds()) for s in sessions)
    total_hours = total_seconds / 3600
    percent = int((total_hours / user.daily_goal_hours) * 100) if user.daily_goal_hours else 0
    left = max(0, user.daily_goal_hours - total_hours)
    text = (
        f"Сегодня вы носили элайнеры {total_hours:.1f} ч ({percent}% от цели {user.daily_goal_hours} ч).\n"
        f"Осталось до цели: {left:.1f} ч.\n\n"
        f"Сессии за день:\n"
    )
    for s in sessions:
        st = s.start_time.strftime('%H:%M')
        et = s.end_time.strftime('%H:%M') if s.end_time else '...'
        dur = (s.duration_seconds or int((datetime.now() - s.start_time).total_seconds())) // 60
        text += f"{st} — {et} ({dur} мин)\n"
    if total_hours >= user.daily_goal_hours:
        text += "\nОтличная работа! Вы выполнили план на сегодня. Так держать!"
    elif percent >= 80:
        text += "\nПочти достигли цели! Ещё немного — и вы молодец!"
    else:
        text += "\nСегодня не получилось выполнить план. Это нормально! Завтра новый день. Главное — не сдаваться!"
    await message.answer(text)

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user is None:
        return
    telegram_id = message.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    from datetime import timedelta
    days = 7
    today = date.today()
    stats = []
    days_with_goal = 0
    total_hours = 0
    for i in range(days):
        d = today - timedelta(days=i)
        sessions = await WearSession.filter(user=user, date=d).all()
        day_seconds = sum(s.duration_seconds or 0 for s in sessions)
        day_hours = day_seconds / 3600
        total_hours += day_hours
        if day_hours >= user.daily_goal_hours:
            days_with_goal += 1
        stats.append((d, day_hours))
    stats.reverse()
    avg_hours = total_hours / days
    percent_goal = int((days_with_goal / days) * 100)
    text = (
        f"Статистика за последние {days} дней:\n"
        f"Среднее время ношения: {avg_hours:.1f} ч/день\n"
        f"Дней с выполнением цели: {days_with_goal} из {days} ({percent_goal}%)\n\n"
        f"День         Часы\n"
    )
    for d, h in stats:
        text += f"{d.strftime('%d.%m')}:   {h:.1f}\n"
    await message.answer(text)

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "/start — регистрация\n"
        "/profile — профиль\n"
        "/start_wear — начать сессию ношения\n"
        "/stop_wear — завершить сессию\n"
        "/today — статистика за сегодня\n"
        "/stats — статистика за период\n"
        "/next — отметить смену каппы\n"
        "/tips — советы\n"
        "/support — поддержка"
    )

@router.message(Command("tips"))
async def cmd_tips(message: Message):
    import random
    tips = [
        "Носите элайнеры не менее 22 часов в сутки для максимального эффекта.",
        "Снимайте элайнеры только во время еды и чистки зубов.",
        "Очищайте элайнеры ежедневно мягкой щёткой и тёплой водой.",
        "Не забывайте менять элайнеры согласно графику.",
        "Если элайнеры натирают — обратитесь к врачу, не терпите дискомфорт.",
        "Пейте воду с элайнерами, но избегайте сладких и горячих напитков."
    ]
    await message.answer(random.choice(tips))

@router.message(Command("support"))
async def cmd_support(message: Message):
    await message.answer("Контакты клиники: +7 900 000-00-00, email: support@alignerclinic.ru\nЕсли нужна помощь — напишите сюда или обратитесь к ассистенту.") 