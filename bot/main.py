import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import logging
from backend.db import init_db
from bot.handlers import router as user_router
from bot.reminders import reminders_worker
from backend.models.user import User
from backend.models.wear_session import WearSession
from datetime import datetime, date

API_TOKEN = os.getenv("BOT_TOKEN", "8174579900:AAHoDQb8bHjfamt4g8vEGnIs_j8eoObY3fg")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Подключаем роутер
# dp.include_router(user_router)
logger.info("Router included successfully")
# logger.info(f"Router handlers: {len(user_router.message.handlers)}")
# for i, handler in enumerate(user_router.message.handlers):
#     logger.info(f"Handler {i}: {handler.callback.__name__}")

def get_main_keyboard():
    """Создаёт основную клавиатуру с главными функциями"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Начать ношение", callback_data="start_wear"),
            InlineKeyboardButton(text="🔴 Остановить ношение", callback_data="stop_wear")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика сегодня", callback_data="today"),
            InlineKeyboardButton(text="📈 Статистика за неделю", callback_data="stats")
        ],
        [
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"),
            InlineKeyboardButton(text="🔄 Сменить каппу", callback_data="next")
        ],
        [
            InlineKeyboardButton(text="💡 Советы", callback_data="tips"),
            InlineKeyboardButton(text="❓ Помощь", callback_data="help")
        ],
        [
            InlineKeyboardButton(text="📞 Поддержка", callback_data="support")
        ]
    ])
    return keyboard

def get_wear_keyboard():
    """Клавиатура для управления ношением"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Остановить ношение", callback_data="stop_wear"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="today")
        ],
        [
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ]
    ])
    return keyboard

# Добавляем тестовый хэндлер
@dp.message(Command("test"))
async def test_handler(message: Message):
    logger.info("TEST HANDLER WORKING!")
    await message.answer("Тестовый хэндлер работает!")

# Добавляем профиль хэндлер для тестирования
@dp.message(Command("profile"))
async def profile_test_handler(message: Message):
    logger.info("PROFILE TEST HANDLER WORKING!")
    if message.from_user is None:
        return
    telegram_id = message.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await message.answer("Вы не зарегистрированы. Используйте /start.")
        return
    text = f"Профиль:\nИмя: {user.name or 'не указано'}\nНомер элайнера: {user.current_aligner_number}"
    await message.answer(text)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user is None:
        return
    telegram_id = message.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        user = await User.create(
            telegram_id=telegram_id,
            name=message.from_user.first_name or None,
            current_aligner_number=1,
            last_aligner_change_date=message.date.date(),
            aligner_change_interval_days=14,
            daily_goal_hours=22
        )
        welcome_text = (
            "🎉 Добро пожаловать в <b>ЭлайнерКонтроль</b>!\n\n"
            "Я помогу вам отслеживать время ношения элайнеров и достигать ваших целей.\n\n"
            "Выберите действие:"
        )
        await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="HTML")
    else:
        welcome_text = (
            f"👋 С возвращением, {user.name or 'пациент'}!\n\n"
            "Готовы продолжить лечение? Выберите действие:"
        )
        await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="HTML")

# Удаляем обработчик /name и set_name_if_needed
# (Оставляем только профиль и приветствие)

@dp.message(Command("start_wear"))
async def cmd_start_wear(message: Message):
    if message.from_user is None:
        return
    telegram_id = message.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
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

@dp.message(Command("stop_wear"))
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
    # Приводим к наивному datetime для совместимости
    start_time = open_session.start_time.replace(tzinfo=None) if open_session.start_time.tzinfo else open_session.start_time
    duration = int((end_time - start_time).total_seconds())
    open_session.end_time = end_time
    open_session.duration_seconds = duration
    await open_session.save()
    await message.answer(f"Сессия завершена! Длительность: {duration // 3600}ч {(duration % 3600) // 60}м.")

@dp.message(Command("today"))
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
    total_seconds = sum(s.duration_seconds or int((datetime.now() - (s.start_time.replace(tzinfo=None) if s.start_time.tzinfo else s.start_time)).total_seconds()) for s in sessions)
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
        dur = (s.duration_seconds or int((datetime.now() - (s.start_time.replace(tzinfo=None) if s.start_time.tzinfo else s.start_time)).total_seconds())) // 60
        text += f"{st} — {et} ({dur} мин)\n"
    if total_hours >= user.daily_goal_hours:
        text += "\nОтличная работа! Вы выполнили план на сегодня. Так держать!"
    elif percent >= 80:
        text += "\nПочти достигли цели! Ещё немного — и вы молодец!"
    else:
        text += "\nСегодня не получилось выполнить план. Это нормально! Завтра новый день. Главное — не сдаваться!"
    await message.answer(text)

@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "🤖 <b>ЭлайнерКонтроль - ваш помощник в лечении</b>\n\n"
        "<b>Основные команды:</b>\n"
        "🟢 Начать ношение - запустить таймер\n"
        "🔴 Остановить ношение - завершить сессию\n"
        "📊 Статистика сегодня - прогресс за день\n"
        "📈 Статистика за неделю - общий прогресс\n"
        "👤 Мой профиль - информация о лечении\n"
        "🔄 Сменить каппу - переход на следующий элайнер\n"
        "💡 Советы - полезные рекомендации\n"
        "📞 Поддержка - связаться с клиникой\n\n"
        "Используйте кнопки ниже для удобной навигации!"
    )
    await message.answer(help_text, reply_markup=get_main_keyboard(), parse_mode="HTML")

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    if callback.message is None:
        await callback.answer("Ошибка: сообщение недоступно")
        return
        
    if callback.data == "main_menu":
        await callback.message.answer(
            "🏠 <b>Главное меню</b>\n\nВыберите действие:",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    elif callback.data == "start_wear":
        await handle_start_wear_callback(callback)
    elif callback.data == "stop_wear":
        await handle_stop_wear_callback(callback)
    elif callback.data == "today":
        await handle_today_callback(callback)
    elif callback.data == "stats":
        await handle_stats_callback(callback)
    elif callback.data == "profile":
        await handle_profile_callback(callback)
    elif callback.data == "next":
        await handle_next_callback(callback)
    elif callback.data == "tips":
        await handle_tips_callback(callback)
    elif callback.data == "help":
        await handle_help_callback(callback)
    elif callback.data == "support":
        await handle_support_callback(callback)
    
    await callback.answer()

async def handle_start_wear_callback(callback: types.CallbackQuery):
    if callback.from_user is None or callback.message is None:
        return
    telegram_id = callback.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await callback.message.answer("Сначала зарегистрируйтесь через /start.")
        return
    open_session = await WearSession.filter(user=user, end_time=None).first()
    if open_session:
        await callback.message.answer("⚠️ У вас уже запущена сессия ношения элайнеров.")
        return
    await WearSession.create(
        user=user,
        date=date.today(),
        start_time=datetime.now(),
        end_time=None,
        duration_seconds=None
    )
    await callback.message.answer(
        "🟢 <b>Таймер ношения запущен!</b>\n\n"
        "Элайнеры надеты. Не забудьте остановить таймер, когда снимете их.",
        reply_markup=get_wear_keyboard(),
        parse_mode="HTML"
    )

async def handle_stop_wear_callback(callback: types.CallbackQuery):
    if callback.from_user is None or callback.message is None:
        return
    telegram_id = callback.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await callback.message.answer("Сначала зарегистрируйтесь через /start.")
        return
    open_session = await WearSession.filter(user=user, end_time=None).first()
    if not open_session:
        await callback.message.answer("⚠️ Нет активной сессии ношения. Используйте кнопку 'Начать ношение'.")
        return
    end_time = datetime.now()
    start_time = open_session.start_time.replace(tzinfo=None) if open_session.start_time.tzinfo else open_session.start_time
    duration = int((end_time - start_time).total_seconds())
    open_session.end_time = end_time
    open_session.duration_seconds = duration
    await open_session.save()
    
    hours = duration // 3600
    minutes = (duration % 3600) // 60
    
    await callback.message.answer(
        f"🔴 <b>Сессия завершена!</b>\n\n"
        f"⏱️ Длительность: {hours}ч {minutes}м\n"
        f"✅ Отличная работа! Не забудьте надеть элайнеры снова.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

async def handle_today_callback(callback: types.CallbackQuery):
    if callback.from_user is None or callback.message is None:
        return
    telegram_id = callback.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await callback.message.answer("Сначала зарегистрируйтесь через /start.")
        return
    today = date.today()
    sessions = await WearSession.filter(user=user, date=today).all()
    total_seconds = sum(s.duration_seconds or int((datetime.now() - (s.start_time.replace(tzinfo=None) if s.start_time.tzinfo else s.start_time)).total_seconds()) for s in sessions)
    total_hours = total_seconds / 3600
    percent = int((total_hours / user.daily_goal_hours) * 100) if user.daily_goal_hours else 0
    left = max(0, user.daily_goal_hours - total_hours)
    
    # Создаём прогресс-бар
    progress_bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
    
    text = (
        f"📊 <b>Статистика за сегодня</b>\n\n"
        f"⏱️ Время ношения: <b>{total_hours:.1f}ч</b> ({percent}% от цели {user.daily_goal_hours}ч)\n"
        f"📈 Прогресс: [{progress_bar}] {percent}%\n"
        f"🎯 Осталось до цели: <b>{left:.1f}ч</b>\n\n"
    )
    
    if sessions:
        text += "📋 <b>Сессии за день:</b>\n"
        for s in sessions:
            st = s.start_time.strftime('%H:%M')
            et = s.end_time.strftime('%H:%M') if s.end_time else '...'
            dur = (s.duration_seconds or int((datetime.now() - (s.start_time.replace(tzinfo=None) if s.start_time.tzinfo else s.start_time)).total_seconds())) // 60
            text += f"🕐 {st} — {et} ({dur} мин)\n"
    
    if total_hours >= user.daily_goal_hours:
        text += "\n🎉 <b>Отличная работа! Вы выполнили план на сегодня!</b>"
    elif percent >= 80:
        text += "\n👍 Почти достигли цели! Ещё немного — и вы молодец!"
    else:
        text += "\n💪 Сегодня не получилось выполнить план. Завтра новый день!"
    
    await callback.message.answer(text, reply_markup=get_main_keyboard(), parse_mode="HTML")

async def handle_stats_callback(callback: types.CallbackQuery):
    if callback.from_user is None or callback.message is None:
        return
    telegram_id = callback.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await callback.message.answer("Сначала зарегистрируйтесь через /start.")
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
        f"📈 <b>Статистика за последние {days} дней</b>\n\n"
        f"📊 Среднее время ношения: <b>{avg_hours:.1f}ч/день</b>\n"
        f"✅ Дней с выполнением цели: <b>{days_with_goal} из {days}</b> ({percent_goal}%)\n\n"
        f"📅 <b>По дням:</b>\n"
    )
    for d, h in stats:
        emoji = "✅" if h >= user.daily_goal_hours else "⚠️" if h > 0 else "❌"
        text += f"{emoji} {d.strftime('%d.%m')}: <b>{h:.1f}ч</b>\n"
    
    await callback.message.answer(text, reply_markup=get_main_keyboard(), parse_mode="HTML")

async def handle_profile_callback(callback: types.CallbackQuery):
    if callback.from_user is None or callback.message is None:
        return
    telegram_id = callback.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await callback.message.answer("Сначала зарегистрируйтесь через /start.")
        return
    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"📝 Имя: <b>{user.name or 'не указано'}</b>\n"
        f"🦷 Номер элайнера: <b>№{user.current_aligner_number}</b>\n"
        f"📅 Дата последней смены: <b>{user.last_aligner_change_date}</b>\n"
        f"🔄 График смены: <b>{user.aligner_change_interval_days} дней</b>\n"
        f"🎯 Цель по ношению: <b>{user.daily_goal_hours}ч/сутки</b>\n\n"
        f"💡 Имя можно изменить только через администратора."
    )
    await callback.message.answer(text, reply_markup=get_main_keyboard(), parse_mode="HTML")

async def handle_next_callback(callback: types.CallbackQuery):
    if callback.from_user is None or callback.message is None:
        return
    telegram_id = callback.from_user.id
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        await callback.message.answer("Сначала зарегистрируйтесь через /start.")
        return
    user.current_aligner_number += 1
    user.last_aligner_change_date = date.today()
    await user.save()
    await callback.message.answer(
        f"🎉 <b>Поздравляем с переходом на новый элайнер!</b>\n\n"
        f"🦷 Теперь у вас элайнер <b>№{user.current_aligner_number}</b>\n"
        f"📅 Дата смены: <b>{user.last_aligner_change_date}</b>\n\n"
        f"💪 Продолжайте в том же духе!",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

async def handle_tips_callback(callback: types.CallbackQuery):
    if callback.message is None:
        return
    import random
    tips = [
        "💡 <b>Носите элайнеры не менее 22 часов в сутки</b> для максимального эффекта лечения.",
        "🍽️ <b>Снимайте элайнеры только во время еды и чистки зубов</b> - это поможет быстрее достичь результата.",
        "🧼 <b>Очищайте элайнеры ежедневно</b> мягкой щёткой и тёплой водой для гигиены.",
        "📅 <b>Не забывайте менять элайнеры</b> согласно графику, назначенному врачом.",
        "⚠️ <b>Если элайнеры натирают</b> - обратитесь к врачу, не терпите дискомфорт.",
        "💧 <b>Пейте воду с элайнерами</b>, но избегайте сладких и горячих напитков."
    ]
    tip = random.choice(tips)
    await callback.message.answer(
        f"💡 <b>Полезный совет</b>\n\n{tip}",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

async def handle_help_callback(callback: types.CallbackQuery):
    if callback.message is None:
        return
    help_text = (
        "🤖 <b>ЭлайнерКонтроль - ваш помощник в лечении</b>\n\n"
        "<b>Основные функции:</b>\n"
        "🟢 <b>Начать ношение</b> - запустить таймер\n"
        "🔴 <b>Остановить ношение</b> - завершить сессию\n"
        "📊 <b>Статистика сегодня</b> - прогресс за день\n"
        "📈 <b>Статистика за неделю</b> - общий прогресс\n"
        "👤 <b>Мой профиль</b> - информация о лечении\n"
        "🔄 <b>Сменить каппу</b> - переход на следующий элайнер\n"
        "💡 <b>Советы</b> - полезные рекомендации\n"
        "📞 <b>Поддержка</b> - связаться с клиникой\n\n"
        "💪 <b>Регулярное ношение элайнеров - залог успешного лечения!</b>"
    )
    await callback.message.answer(help_text, reply_markup=get_main_keyboard(), parse_mode="HTML")

async def handle_support_callback(callback: types.CallbackQuery):
    if callback.message is None:
        return
    await callback.message.answer(
        "📞 <b>Поддержка</b>\n\n"
        "🏥 <b>Контакты клиники:</b>\n"
        "📱 Телефон: +7 900 000-00-00\n"
        "📧 Email: support@alignerclinic.ru\n\n"
        "💬 Если нужна помощь — напишите сюда или обратитесь к ассистенту.\n\n"
        "⏰ <b>Время работы:</b> Пн-Пт 9:00-18:00",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

@dp.message(Command("tips"))
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

@dp.message(Command("support"))
async def cmd_support(message: Message):
    await message.answer("Контакты клиники: +7 900 000-00-00, email: support@alignerclinic.ru\nЕсли нужна помощь — напишите сюда или обратитесь к ассистенту.")

@dp.message(Command("next"))
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

@dp.message(Command("stats"))
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

async def main():
    logger.info("Starting bot...")
    await init_db()
    logger.info("Database initialized")
    import asyncio
    asyncio.create_task(reminders_worker(bot))
    logger.info("Starting polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
