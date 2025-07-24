from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
import random
import json

from config import BOT_TOKEN
from db import init_db, create_user, get_balance, update_balance, update_game_stats, get_user_stats, add_referral_bonus
from aiogram.types import CallbackQuery

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

init_db()

# Настройки канала - убедитесь что бот добавлен в канал как администратор
CHANNEL_ID = "-1002803457841"
SUBSCRIPTION_CHANNEL = "@MoonCasino777"

# Система очереди ставок
game_queue = []
is_game_running = False

class GameState(StatesGroup):
    main_menu = State()
    play_menu = State()
    profile = State()
    bot_games = State()
    channel_games = State()

    # Игры в боте
    mines_setup = State()
    tower_setup = State()
    mines_game = State()
    tower_game = State()

    # Игры в канале
    channel_bowling = State()
    channel_basketball = State()
    channel_dice_duel = State()
    channel_dice_higher = State()
    channel_dice_even = State()
    channel_triada = State()
    channel_darts = State()

    # Ставки
    waiting_bet = State()

    # Админ функции
    admin_add_coins_id = State()
    admin_add_coins_amount = State()

# Коэффициенты для мин
MINES_COEFFICIENTS = {
    2: [1.02, 1.11, 1.22, 1.34, 1.48, 1.65, 1.84, 2.07, 2.35, 2.69, 3.1, 3.62, 4.27, 5.13, 6.27, 7.83, 10.07, 13.43, 18.8],
    3: [1.07, 1.22, 1.4, 1.63, 1.9, 2.23, 2.65, 3.18, 3.86, 4.75, 5.94, 7.56, 9.83, 13.1, 18.02, 25.74, 38.61, 61.77, 108.0],
    4: [1.12, 1.34, 1.63, 1.99, 2.45, 3.07, 3.89, 5.0, 6.53, 8.71, 11.88, 16.63, 24.02, 36.03, 56.62, 94.37, 169.87, 339.74, 792.73, 2378.2, 11891]
}

# Коэффициенты для башни
TOWER_COEFFICIENTS = {
    1: [1.17, 1.47, 1.84, 2.29, 2.87, 3.59],
    2: [1.57, 2.61, 4.35, 7.25, 12.09, 20.15],
    3: [2.35, 5.87, 14.69, 36.72, 91.80, 229.49],
    4: [4.70, 23.50, 117.50, 587.50, 2937.50, 14687.50]
}

async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(chat_id=SUBSCRIPTION_CHANNEL, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return False

async def require_subscription(user_id):
    """Проверяет подписку и возвращает True если подписан"""
    return await check_subscription(user_id)

def get_subscription_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Подписаться на канал", url="https://t.me/MoonCasino777")],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")]
        ]
    )
    return keyboard

def get_start_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 Играть"), KeyboardButton(text="👤 Профиль")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_play_menu_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤖 Играть в боте")],
            [KeyboardButton(text="💬 Играть в канале")],
            [KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_bot_games_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💣 Мины"), KeyboardButton(text="🏗 Башня")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_bet_input_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_basketball_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Попадание (x1.8)")],
            [KeyboardButton(text="❌ Мимо (x1.3)")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_dice_duel_choice_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Победа (x1.8)"), KeyboardButton(text="💀 Поражение (x1.8)")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_dice_higher_lower_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⬆️ Больше"), KeyboardButton(text="⬇️ Меньше")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_dice_even_odd_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="2️⃣ Четное"), KeyboardButton(text="1️⃣ Нечетное")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_triada_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1️⃣"), KeyboardButton(text="2️⃣"), KeyboardButton(text="3️⃣")],
            [KeyboardButton(text="4️⃣"), KeyboardButton(text="5️⃣"), KeyboardButton(text="6️⃣")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_bowling_choice_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏆 Победа (x1.8)"), KeyboardButton(text="💀 Поражение (x1.8)")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_darts_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔴 Красное (x1.8)"), KeyboardButton(text="⚪ Белое (x1.8)")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_mines_count_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="2 мины"), KeyboardButton(text="3 мины")],
            [KeyboardButton(text="4 мины")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_tower_mines_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1 мина"), KeyboardButton(text="2 мины")],
            [KeyboardButton(text="3 мины"), KeyboardButton(text="4 мины")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def create_mines_field(mines_count=2, opened_cells=None):
    if opened_cells is None:
        opened_cells = []

    field = []
    for i in range(5):
        row = []
        for j in range(5):
            if (i, j) in opened_cells:
                row.append("💎")
            else:
                row.append("⬜")
        field.append(row)
    return field

def create_mines_inline_keyboard(mines_count, opened_cells, current_coeff):
    keyboard = []
    field = create_mines_field(mines_count, opened_cells)

    # Отображаем поле снизу вверх (с 4 ряда до 0)
    for i in range(4, -1, -1):
        row = []
        for j in range(5):
            if (i, j) in opened_cells:
                row.append(InlineKeyboardButton(text="💎", callback_data=f"mines_{i}_{j}"))
            else:
                row.append(InlineKeyboardButton(text="⬜", callback_data=f"mines_{i}_{j}"))
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton(text=f"💰 Забрать {current_coeff}x", callback_data="mines_cash_out"),
        InlineKeyboardButton(text="❌ Выйти", callback_data="mines_exit")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_tower_inline_keyboard(tower_mines, opened_levels, current_level):
    keyboard = []

    # Отображаем башню снизу вверх (с 5 уровня до 0) - 6 уровней всего
    for level in range(5, -1, -1):
        row = []
        for cell in range(5):
            if level < current_level:
                if (level, cell) in opened_levels:
                    row.append(InlineKeyboardButton(text="💎", callback_data=f"tower_{level}_{cell}"))
                else:
                    row.append(InlineKeyboardButton(text="⬜", callback_data=f"tower_{level}_{cell}"))
            elif level == current_level:
                row.append(InlineKeyboardButton(text="⬜", callback_data=f"tower_{level}_{cell}"))
            else:
                row.append(InlineKeyboardButton(text="⬛", callback_data=f"tower_{level}_{cell}"))
        keyboard.append(row)

    if current_level > 0:
        coeffs = TOWER_COEFFICIENTS[tower_mines]
        current_coeff = coeffs[current_level - 1] if current_level - 1 < len(coeffs) else coeffs[-1]
        keyboard.append([
            InlineKeyboardButton(text=f"💰 Забрать {current_coeff}x", callback_data="tower_cash_out"),
            InlineKeyboardButton(text="❌ Выйти", callback_data="tower_exit")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="❌ Выйти", callback_data="tower_exit")
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_profile_keyboard(user_id):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_profile_inline_keyboard(user_id):
    if user_id == 6774136020:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💰 +1000 монет", callback_data="add_1000_coins")],
                [InlineKeyboardButton(text="💳 Начислить валюту по ID", callback_data="add_coins_by_id")]
            ]
        )
        return keyboard
    return None

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext):
    is_subscribed = await check_subscription(callback.from_user.id)

    if is_subscribed:
        create_user(callback.from_user.id)
        balance = get_balance(callback.from_user.id)
        await state.set_state(GameState.main_menu)
        await callback.message.edit_text(
            f"✅ <b>Подписка подтверждена!</b>\n\n"
            f"🎰 <b>Добро пожаловать в MoonCasino!</b>\n"
            f"💰 Ваш баланс: <b>{balance}</b> монет",
            reply_markup=None
        )
        await callback.message.answer(
            "🎮 Выберите действие:",
            reply_markup=get_start_keyboard()
        )
        await callback.answer("✅ Подписка подтверждена!")
    else:
        await callback.answer("❌ Вы не подписаны на канал! Подпишитесь и нажмите 'Проверить подписку'", show_alert=True)

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)

    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для использования бота необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}\n"
            f"🎰 После подписки нажмите 'Проверить подписку'",
            reply_markup=get_subscription_keyboard()
        )
        return

    # Обработка реферальной ссылки
    referrer_id = None
    if len(message.text.split()) > 1:
        start_param = message.text.split()[1]
        if start_param.startswith("ref"):
            try:
                referrer_id = int(start_param[3:])
                if referrer_id == message.from_user.id:
                    referrer_id = None  # Нельзя быть рефералом самого себя
            except ValueError:
                pass

    # Создаем пользователя с рефералом если есть
    from db import create_user_with_referrer
    if referrer_id:
        create_user_with_referrer(message.from_user.id, referrer_id)
        # Уведомляем реферера
        try:
            await bot.send_message(
                referrer_id,
                f"🎉 <b>Новый реферал!</b>\n"
                f"👤 Пользователь {message.from_user.first_name} зарегистрировался по вашей ссылке!\n"
                f"💰 Теперь вы будете получать 5% с его выигрышей!"
            )
        except:
            pass
    else:
        create_user(message.from_user.id)

    balance = get_balance(message.from_user.id)
    await state.set_state(GameState.main_menu)
    
    welcome_text = f"🎰 <b>Добро пожаловать в MoonCasino!</b>\n💰 Ваш баланс: <b>{balance}</b> монет"
    if referrer_id:
        welcome_text += f"\n\n🎁 Вы зарегистрировались по реферальной ссылке!"
    
    await message.answer(welcome_text, reply_markup=get_start_keyboard())

def get_channel_games_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎳 Боулинг"), KeyboardButton(text="🏀 Баскетбол")],
            [KeyboardButton(text="🎲 Кубы (дуэль)"), KeyboardButton(text="🎲 Больше/меньше")],
            [KeyboardButton(text="🎲 Чет/нечет"), KeyboardButton(text="🎲 Триада")],
            [KeyboardButton(text="🎯 Дартс")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

@router.message(F.text == "🎮 Играть")
async def play_menu_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    await state.set_state(GameState.play_menu)
    await message.answer(
        "🎮 <b>Выберите режим игры:</b>",
        reply_markup=get_play_menu_keyboard()
    )

@router.message(F.text == "👤 Профиль")
async def profile_handler(message: Message, state: FSMContext):
    is_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer(
            f"🔒 <b>Для доступа к профилю необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    await state.set_state(GameState.profile)
    balance = get_balance(message.from_user.id)
    username = message.from_user.username or "Без ника"
    first_name = message.from_user.first_name or "Игрок"

    inline_keyboard = get_profile_inline_keyboard(message.from_user.id)

    # Добавляем кнопки реферальной системы и назад
    profile_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Реферальная система")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    # Получаем статистику пользователя
    stats = get_user_stats(message.from_user.id)
    if stats:
        favorite_game = f"{stats['favorite_game']} [{stats['favorite_game_count']}]"
        total_games = stats['total_games']
        biggest_win = stats['biggest_win']
        registration_date = stats['registration_date'][:10] if stats['registration_date'] else "20.10.2024"
    else:
        favorite_game = "Триада [74]"
        total_games = 206
        biggest_win = 9
        registration_date = "20.10.2024"

    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"👤 Имя: {first_name}\n"
        f"📱 Ник: @{username}\n"
        f"💰 Баланс: <b>{balance}</b> монет\n\n"
        f"📊 Статистика\n"
        f"┣ Любимая игра: {favorite_game}\n"
        f"┣ Сыгранные игры: {total_games}\n"
        f"┗ Самый большой выигрыш: {biggest_win}$\n\n"
        f"📆 Дата регистрации: {registration_date}",
        reply_markup=profile_keyboard
    )

    if inline_keyboard:
        await message.answer("🔧 <b>Админ панель:</b>", reply_markup=inline_keyboard)

@router.message(F.text == "Реферальная система")
async def referral_handler(message: Message, state: FSMContext):
    from db import get_referral_info
    
    referrals_count = get_referral_info(message.from_user.id)
    bot_username = (await bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start=ref{message.from_user.id}"
    
    await message.answer(
        f"👥 <b>Реферальная система</b>\n\n"
        f"💰 Вы получаете 5% с каждого выигрыша ваших рефералов!\n\n"
        f"📊 Ваша статистика:\n"
        f"└ Приглашено друзей: {referrals_count}\n\n"
        f"🔗 Ваша реферальная ссылка:\n"
        f"<code>{referral_link}</code>\n\n"
        f"📢 Поделитесь ссылкой с друзьями и получайте бонусы!"
    )

@router.message(F.text == "🤖 Играть в боте")
async def bot_games_handler(message: Message, state: FSMContext):
    await state.set_state(GameState.bot_games)
    await message.answer(
        "🤖 <b>Игры в боте:</b>\n\n"
        "💣 <b>Мины</b> - найдите алмазы, избегая мин\n"
        "🏗 <b>Башня</b> - поднимайтесь выше по уровням",
        reply_markup=get_bot_games_keyboard()
    )

@router.message(F.text == "💬 Играть в канале")
async def channel_games_handler(message: Message, state: FSMContext):
    await state.set_state(GameState.channel_games)
    await message.answer(
        "💬 <b>Игры в канале:</b>\n\n"
        "🎳 <b>Боулинг</b> - дуэль x1.8\n"
        "🏀 <b>Баскетбол</b> - попадание x1.8, мимо x1.3\n"
        "🎲 <b>Кубы (дуэль)</b> - x1.8\n"
        "🎲 <b>Больше/меньше</b> - x1.8\n"
        "🎲 <b>Чет/нечет</b> - x1.8\n"
        "🎲 <b>Триада</b> - 1 совп. x1.8, 2 совп. x2.4, 3 совп. x3.1\n"
        "🎯 <b>Дартс</b> - x1.8",
        reply_markup=get_channel_games_keyboard()
    )

# Обработка игр в боте
@router.message(F.text == "💣 Мины")
async def mines_setup_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.bot_games:
        await state.set_state(GameState.mines_setup)
        await message.answer(
            "💣 <b>Мины</b>\n"
            "Выберите количество мин:",
            reply_markup=get_mines_count_keyboard()
        )

@router.message(F.text == "🏗 Башня")
async def tower_setup_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.bot_games:
        await state.set_state(GameState.tower_setup)
        await message.answer(
            "🏗 <b>Башня</b>\n"
            "Выберите количество мин на уровне:",
            reply_markup=get_tower_mines_keyboard()
        )

@router.message(F.text.in_(["2 мины", "3 мины", "4 мины"]))
async def mines_count_selection(message: Message, state: FSMContext):
    if not await require_subscription(message.from_user.id):
        await message.answer(
            f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    mines_count = int(message.text.split()[0])
    await state.update_data(mines_count=mines_count)
    await state.set_state(GameState.waiting_bet)
    await message.answer(
        f"💣 <b>Мины ({mines_count} мины)</b>\n"
        f"💰 Введите сумму ставки (от 200 до 20000 монет):",
        reply_markup=get_bet_input_keyboard()
    )

@router.message(F.text.in_(["1 мина", "2 мины", "3 мины", "4 мины"]))
async def tower_mines_selection(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.tower_setup:
        if not await require_subscription(message.from_user.id):
            await message.answer(
                f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
                f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
                reply_markup=get_subscription_keyboard()
            )
            return

        tower_mines = int(message.text.split()[0])
        await state.update_data(tower_mines=tower_mines)
        await state.set_state(GameState.waiting_bet)
        await message.answer(
            f"🏗 <b>Башня ({tower_mines} {'мина' if tower_mines == 1 else 'мины'})</b>\n"
            f"💰 Введите сумму ставки (от 200 до 20000 монет):",
            reply_markup=get_bet_input_keyboard()
        )

# Обработка игр в канале
@router.message(F.text.in_(["🎳 Боулинг", "🎳 Боулинг (дуэль)", "Боулинг"]))
async def channel_bowling_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_games:
        if not await require_subscription(message.from_user.id):
            await message.answer(
                f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
                f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
                reply_markup=get_subscription_keyboard()
            )
            return

        await state.set_state(GameState.channel_bowling)
        await state.update_data(game_type="bowling")
        await state.set_state(GameState.waiting_bet)
        await message.answer(
            "🎳 <b>Боулинг (дуэль)</b>\n"
            "Коэффициент: x1.8\n\n"
            f"💰 Введите сумму ставки (от 200 до 20000 монет):",
            reply_markup=get_bet_input_keyboard()
        )

@router.message(F.text.in_(["🏀 Баскетбол", "Баскетбол"]))
async def channel_basketball_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_games:
        if not await require_subscription(message.from_user.id):
            await message.answer(
                f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
                f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
                reply_markup=get_subscription_keyboard()
            )
            return

        await state.set_state(GameState.channel_basketball)
        await state.update_data(game_type="basketball")
        await state.set_state(GameState.waiting_bet)
        await message.answer(
            "🏀 <b>Баскетбол</b>\n"
            "🎯 Попадание: x1.8\n"
            "❌ Мимо: x1.3\n\n"
            f"💰 Введите сумму ставки (от 200 до 20000 монет):",
            reply_markup=get_bet_input_keyboard()
        )

@router.message(F.text.in_(["🎲 Кубы", "🎲 Кубы (дуэль)", "Кубы дуэль", "Кубы"]))
async def channel_dice_duel_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_games:
        if not await require_subscription(message.from_user.id):
            await message.answer(
                f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
                f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
                reply_markup=get_subscription_keyboard()
            )
            return

        await state.set_state(GameState.channel_dice_duel)
        await state.update_data(game_type="dice_duel")
        await state.set_state(GameState.waiting_bet)
        await message.answer(
            "🎲 <b>Кубы (дуэль)</b>\n"
            "Коэффициент: x1.8\n\n"
            f"💰 Введите сумму ставки (от 200 до 20000 монет):",
            reply_markup=get_bet_input_keyboard()
        )

@router.message(F.text.in_(["🎲 Больше/меньше", "Больше меньше", "Больше/меньше"]))
async def channel_dice_higher_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_games:
        if not await require_subscription(message.from_user.id):
            await message.answer(
                f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
                f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
                reply_markup=get_subscription_keyboard()
            )
            return

        await state.set_state(GameState.channel_dice_higher)
        await state.update_data(game_type="dice_higher")
        await state.set_state(GameState.waiting_bet)
        await message.answer(
            "🎲 <b>Кубы больше/меньше</b>\n"
            "Коэффициент: x1.8\n\n"
            f"💰 Введите сумму ставки (от 200 до 20000 монет):",
            reply_markup=get_bet_input_keyboard()
        )

@router.message(F.text.in_(["🎲 Чет/нечет", "Чет нечет", "Чет/нечет"]))
async def channel_dice_even_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_games:
        if not await require_subscription(message.from_user.id):
            await message.answer(
                f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
                f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
                reply_markup=get_subscription_keyboard()
            )
            return

        await state.set_state(GameState.channel_dice_even)
        await state.update_data(game_type="dice_even")
        await state.set_state(GameState.waiting_bet)
        await message.answer(
            "🎲 <b>Кубы чет/нечет</b>\n"
            "Коэффициент: x1.8\n\n"
            f"💰 Введите сумму ставки (от 200 до 20000 монет):",
            reply_markup=get_bet_input_keyboard()
        )

@router.message(F.text.in_(["🎲 Триада", "Триада"]))
async def channel_triada_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_games:
        if not await require_subscription(message.from_user.id):
            await message.answer(
                f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
                f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
                reply_markup=get_subscription_keyboard()
            )
            return

        await state.set_state(GameState.channel_triada)
        await state.update_data(game_type="triada")
        await state.set_state(GameState.waiting_bet)
        await message.answer(
            "🎲 <b>Триада</b>\n"
            "• 1 совпадение: x1.8\n"
            "• 2 совпадения: x2.4\n"
            "• 3 совпадения: x3.1\n\n"
            f"💰 Введите сумму ставки (от 200 до 20000 монет):",
            reply_markup=get_bet_input_keyboard()
        )

@router.message(F.text.in_(["🎯 Дартс", "Дартс"]))
async def channel_darts_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_games:
        if not await require_subscription(message.from_user.id):
            await message.answer(
                f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
                f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
                reply_markup=get_subscription_keyboard()
            )
            return

        await state.set_state(GameState.channel_darts)
        await state.update_data(game_type="darts")
        await state.set_state(GameState.waiting_bet)
        await message.answer(
            "🎯 <b>Дартс</b>\n"
            "🔴 Красное: x1.8\n"
            "⚪ Белое: x1.8\n\n"
            f"💰 Введите сумму ставки (от 200 до 20000 монет):",
            reply_markup=get_bet_input_keyboard()
        )

# Обработка ввода ставок
@router.message(GameState.waiting_bet)
async def process_bet_input(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await back_handler(message, state)
        return

    if not await require_subscription(message.from_user.id):
        await message.answer(
            f"🔒 <b>Для игры необходимо подписаться на наш канал!</b>\n\n"
            f"📢 Канал: {SUBSCRIPTION_CHANNEL}",
            reply_markup=get_subscription_keyboard()
        )
        return

    try:
        bet_amount = int(message.text)
        balance = get_balance(message.from_user.id)

        if bet_amount < 200:
            await message.answer("❌ Минимальная ставка: 200 монет!")
            return

        if bet_amount > 20000:
            await message.answer("❌ Максимальная ставка: 20000 монет!")
            return

        if bet_amount > balance:
            await message.answer("❌ Недостаточно монет!")
            return

        data = await state.get_data()
        await state.update_data(bet=bet_amount)

        # Игры в боте
        if 'mines_count' in data:
            mines_count = data['mines_count']
            update_balance(message.from_user.id, -bet_amount)

            mines_positions = set()
            while len(mines_positions) < mines_count:
                mines_positions.add((random.randint(0, 4), random.randint(0, 4)))

            await state.update_data(
                mines_positions=list(mines_positions),
                opened_cells=[],
                clicks_count=0
            )
            await state.set_state(GameState.mines_game)

            keyboard = create_mines_inline_keyboard(mines_count, [], MINES_COEFFICIENTS[mines_count][0])
            await message.answer(
                f"💣 <b>Мины ({mines_count} мины)</b>\n"
                f"💰 Ставка: {bet_amount} монет\n"
                f"🔍 Найдите алмазы, избегайте мин!\n"
                f"💎 Кликов: 0 | Коэффициент: x{MINES_COEFFICIENTS[mines_count][0]}",
                reply_markup=keyboard
            )

        elif 'tower_mines' in data:
            tower_mines = data['tower_mines']
            update_balance(message.from_user.id, -bet_amount)

            tower_structure = {}
            for level in range(6):
                mines_positions = set()
                while len(mines_positions) < tower_mines:
                    mines_positions.add(random.randint(0, 4))
                tower_structure[level] = list(mines_positions)

            await state.update_data(
                tower_structure=tower_structure,
                current_level=0,
                opened_levels=[]
            )
            await state.set_state(GameState.tower_game)

            keyboard = create_tower_inline_keyboard(tower_mines, [], 0)
            await message.answer(
                f"🏗 <b>Башня ({tower_mines} {'мина' if tower_mines == 1 else 'мины'})</b>\n"
                f"💰 Ставка: {bet_amount} монет\n"
                f"🆙 Уровень: 1/6\n"
                f"🏗 Поднимайтесь выше, избегая мин!",
                reply_markup=keyboard
            )

        # Игры в канале
        elif data.get('game_type') in ['bowling', 'dice_duel']:
            await state.set_state(GameState.channel_bowling if data.get('game_type') == 'bowling' else GameState.channel_dice_duel)
            await message.answer(
                f"Выберите исход:",
                reply_markup=get_bowling_choice_keyboard()
            )

        elif data.get('game_type') == 'basketball':
            await state.set_state(GameState.channel_basketball)
            await message.answer(
                f"Выберите исход:",
                reply_markup=get_basketball_keyboard()
            )

        elif data.get('game_type') == 'dice_higher':
            await state.set_state(GameState.channel_dice_higher)
            await message.answer(
                f"Выберите:",
                reply_markup=get_dice_higher_lower_keyboard()
            )

        elif data.get('game_type') == 'dice_even':
            await state.set_state(GameState.channel_dice_even)
            await message.answer(
                f"Выберите:",
                reply_markup=get_dice_even_odd_keyboard()
            )

        elif data.get('game_type') == 'triada':
            await state.set_state(GameState.channel_triada)
            await message.answer(
                f"Выберите число (1-6):",
                reply_markup=get_triada_keyboard()
            )

        elif data.get('game_type') == 'darts':
            await state.set_state(GameState.channel_darts)
            await message.answer(
                f"Выберите цвет:",
                reply_markup=get_darts_keyboard()
            )

    except ValueError:
        await message.answer("❌ Введите числовое значение ставки!")

# Обработка выборов для канальных игр
@router.message(F.text.in_(["🏆 Победа (x1.8)", "💀 Поражение (x1.8)"]))
async def channel_choice_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in [GameState.channel_bowling, GameState.channel_dice_duel]:
        data = await state.get_data()
        bet_amount = data['bet']
        game_type = data['game_type']
        choice = "win" if "Победа" in message.text else "loss"

        update_balance(message.from_user.id, -bet_amount)

        # Добавляем ставку в очередь
        bet_info = {
            'user': message.from_user,
            'bet_amount': bet_amount,
            'game_type': game_type,
            'choice': choice,
            'game_function': play_bowling_direct if game_type == "bowling" else play_dice_duel_direct
        }
        game_queue.append(bet_info)

        inline_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Смотреть", url="https://t.me/MoonCasino777"),
                InlineKeyboardButton(text="🎰 Играть", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        await message.answer(
            f"✅ <b>Ставка принята!</b>\n"
            f"🎯 Игра: {'🎳 Боулинг' if game_type == 'bowling' else '🎲 Кубы (дуэль)'}\n"
            f"💰 Ставка: {bet_amount} монет\n"
            f"🎲 Выбор: {'🏆 Победа' if choice == 'win' else '💀 Поражение'}\n"
            f"📊 Позиция в очереди: {len(game_queue)}",
            reply_markup=inline_keyboard
        )

        # Запускаем обработку очереди
        if not is_game_running:
            asyncio.create_task(process_game_queue())

        await state.set_state(GameState.channel_games)

# Добавляем обработчики для остальных канальных игр
@router.message(F.text.in_(["⬆️ Больше", "⬇️ Меньше"]))
async def channel_dice_higher_choice(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_dice_higher:
        data = await state.get_data()
        bet_amount = data['bet']
        choice = "higher" if "Больше" in message.text else "lower"

        update_balance(message.from_user.id, -bet_amount)

        # Добавляем ставку в очередь
        bet_info = {
            'user': message.from_user,
            'bet_amount': bet_amount,
            'game_type': 'dice_higher',
            'choice': choice,
            'game_function': play_dice_higher_direct
        }
        game_queue.append(bet_info)

        choice_text = "⬆️ Больше 3" if choice == "higher" else "⬇️ Меньше 4"
        inline_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Смотреть", url="https://t.me/MoonCasino777"),
                InlineKeyboardButton(text="🎰 Играть", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )
        await message.answer(
            f"✅ <b>Ставка принята!</b>\n"
            f"🎯 Игра: 🎲 Кубы больше/меньше\n"
            f"💰 Ставка: {bet_amount} монет\n"
            f"🎲 Выбор: {choice_text}\n"
            f"📊 Позиция в очереди: {len(game_queue)}",
            reply_markup=inline_keyboard
        )

        # Запускаем обработку очереди
        if not is_game_running:
            asyncio.create_task(process_game_queue())

        await state.set_state(GameState.channel_games)

@router.message(F.text.in_(["2️⃣ Четное", "1️⃣ Нечетное"]))
async def channel_dice_even_choice(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_dice_even:
        data = await state.get_data()
        bet_amount = data['bet']
        choice = "even" if "Четное" in message.text else "odd"

        update_balance(message.from_user.id, -bet_amount)

        # Добавляем ставку в очередь
        bet_info = {
            'user': message.from_user,
            'bet_amount': bet_amount,
            'game_type': 'dice_even',
            'choice': choice,
            'game_function': play_dice_even_direct
        }
        game_queue.append(bet_info)

        choice_text = "2️⃣ Четное" if choice == "even" else "1️⃣ Нечетное"
        inline_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Смотреть", url="https://t.me/MoonCasino777"),
                InlineKeyboardButton(text="🎰 Играть", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )
        await message.answer(
            f"✅ <b>Ставка принята!</b>\n"
            f"🎯 Игра: 🎲 Кубы чет/нечет\n"
            f"💰 Ставка: {bet_amount} монет\n"
            f"🎲 Выбор: {choice_text}\n"
            f"📊 Позиция в очереди: {len(game_queue)}",
            reply_markup=inline_keyboard
        )

        # Запускаем обработку очереди
        if not is_game_running:
            asyncio.create_task(process_game_queue())

        await state.set_state(GameState.channel_games)

@router.message(F.text.in_(["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]))
async def channel_triada_choice(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_triada:
        data = await state.get_data()
        bet_amount = data['bet']
        choice = message.text[0]  # Получаем цифру

        update_balance(message.from_user.id, -bet_amount)

        # Добавляем ставку в очередь
        bet_info = {
            'user': message.from_user,
            'bet_amount': bet_amount,
            'game_type': 'triada',
            'choice': choice,
            'game_function': play_triada_direct
        }
        game_queue.append(bet_info)

        inline_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Смотреть", url="https://t.me/MoonCasino777"),
                InlineKeyboardButton(text="🎰 Играть", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )
        await message.answer(
            f"✅ <b>Ставка принята!</b>\n"
            f"🎯 Игра: 🎲 Триада\n"
            f"💰 Ставка: {bet_amount} монет\n"
            f"🎲 Выбор: {choice}\n"
            f"📊 Позиция в очереди: {len(game_queue)}",
            reply_markup=inline_keyboard
        )

        # Запускаем обработку очереди
        if not is_game_running:
            asyncio.create_task(process_game_queue())

        await state.set_state(GameState.channel_games)

@router.message(F.text.in_(["🔴 Красное (x1.8)", "⚪ Белое (x1.8)"]))
async def channel_darts_choice(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_darts:
        data = await state.get_data()
        bet_amount = data['bet']
        choice = "red" if "Красное" in message.text else "white"

        update_balance(message.from_user.id, -bet_amount)

        # Добавляем ставку в очередь
        bet_info = {
            'user': message.from_user,
            'bet_amount': bet_amount,
            'game_type': 'darts',
            'choice': choice,
            'game_function': play_darts_direct
        }
        game_queue.append(bet_info)

        choice_text = "🔴 Красное" if choice == "red" else "⚪ Белое"
        inline_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Смотреть", url="https://t.me/MoonCasino777"),
                InlineKeyboardButton(text="🎰 Играть", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )
        await message.answer(
            f"✅ <b>Ставка принята!</b>\n"
            f"🎯 Игра: 🎯 Дартс\n"
            f"💰 Ставка: {bet_amount} монет\n"
            f"🎲 Выбор: {choice_text}\n"
            f"📊 Позиция в очереди: {len(game_queue)}",
            reply_markup=inline_keyboard
        )

        # Запускаем обработку очереди
        if not is_game_running:
            asyncio.create_task(process_game_queue())

        await state.set_state(GameState.channel_games)

# Добавим аналогичные обработчики для других канальных игр...
@router.message(F.text.in_(["🎯 Попадание (x1.8)", "❌ Мимо (x1.3)"]))
async def channel_basketball_choice(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == GameState.channel_basketball:
        data = await state.get_data()
        bet_amount = data['bet']
        choice = "hit" if "Попадание" in message.text else "miss"

        update_balance(message.from_user.id, -bet_amount)

        # Добавляем ставку в очередь
        bet_info = {
            'user': message.from_user,
            'bet_amount': bet_amount,
            'game_type': 'basketball',
            'choice': choice,
            'game_function': play_basketball_direct
        }
        game_queue.append(bet_info)

        choice_text = "🎯 Попадание" if choice == "hit" else "❌ Мимо"
        coeff = "x1.8" if choice == "hit" else "x1.3"
        inline_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Смотреть", url="https://t.me/MoonCasino777"),
                InlineKeyboardButton(text="🎰 Играть", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )
        await message.answer(
            f"✅ <b>Ставка принята!</b>\n"
            f"🎯 Игра: 🏀 Баскетбол\n"
            f"💰 Ставка: {bet_amount} монет\n"
            f"🎲 Выбор: {choice_text} ({coeff})\n"
            f"📊 Позиция в очереди: {len(game_queue)}",
            reply_markup=inline_keyboard
        )

        # Запускаем обработку очереди
        if not is_game_running:
            asyncio.create_task(process_game_queue())

        await state.set_state(GameState.channel_games)

# Прямые игры в канале
async def play_bowling_direct(message: Message, bet_amount: int, choice: str):
    try:
        # Кидаем кегли игрока
        user_bowling = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎳")
        await asyncio.sleep(4)
        user_pins = user_bowling.dice.value

        # Кидаем кегли бота
        await bot.send_message(CHANNEL_ID, "🤖 Бот кидает...")
        bot_bowling = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎳")
        await asyncio.sleep(4)
        bot_pins = bot_bowling.dice.value

        # Определяем результат
        actual_result = "win" if user_pins > bot_pins else "loss"
        win = choice == actual_result

        if win:
            win_amount = int(bet_amount * 1.8)
            update_balance(message.from_user.id, win_amount)
            update_game_stats(message.from_user.id, "Боулинг", win_amount)

            # Реферальный бонус
            stats = get_user_stats(message.from_user.id)
            if stats and stats['referrer_id']:
                bonus = int(win_amount * 0.05)  # 5%
                add_referral_bonus(stats['referrer_id'], bonus)
                try:
                    await bot.send_message(
                        stats['referrer_id'],
                        f"💰 <b>Реферальный бонус!</b>\n"
                        f"👤 Ваш реферал выиграл в боулинг\n"
                        f"🎁 Ваш бонус: {bonus} монет (5%)"
                    )
                except:
                    pass

            result_text = f"🎉 <b>ПОБЕДА!</b>\n💰 Выигрыш: {win_amount} монет"
        else:
            update_game_stats(message.from_user.id, "Боулинг", 0)
            result_text = f"😢 <b>Поражение</b>\n💸 Проигрыш: {bet_amount} монет"

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        await bot.send_message(
            CHANNEL_ID,
            f"🎳 <b>Результат игры</b>\n\n"
            f"👤 Игрок: {message.from_user.first_name} (@{message.from_user.username or 'без_ника'})\n"
            f"🎯 Игрок: {user_pins} кеглей | 🤖 Бот: {bot_pins} кеглей\n"
            f"🎲 Выбор: {'🏆 Победа' if choice == 'win' else '💀 Поражение'}\n\n"
            f"{result_text}",
            reply_markup=channel_keyboard
        )

        # Уведомление в боте
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                message.from_user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎳 Игра: Боулинг\n"
                f"💰 Выигрыш: {win_amount} монет\n"
                f"💳 Ваш баланс изменен: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                message.from_user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎳 Игра: Боулинг\n"
                f"💸 Проигрыш: {bet_amount} монет\n"
                f"💳 Текущий баланс: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в боулинге: {e}")

async def play_dice_duel_direct(message: Message, bet_amount: int, choice: str):
    try:
        user_dice = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(4)
        user_roll = user_dice.dice.value

        await bot.send_message(CHANNEL_ID, "🤖 Бот кидает...")
        bot_dice = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(4)
        bot_roll = bot_dice.dice.value

        actual_result = "win" if user_roll > bot_roll else "loss"
        win = choice == actual_result

        if win:
            win_amount = int(bet_amount * 1.8)
            update_balance(message.from_user.id, win_amount)
            update_game_stats(message.from_user.id, "Кубы (дуэль)", win_amount)

            # Реферальный бонус
            stats = get_user_stats(message.from_user.id)
            if stats and stats['referrer_id']:
                bonus = int(win_amount * 0.05)  # 5%
                add_referral_bonus(stats['referrer_id'], bonus)
                try:
                    await bot.send_message(
                        stats['referrer_id'],
                        f"💰 <b>Реферальный бонус!</b>\n"
                        f"👤 Ваш реферал выиграл в кубы (дуэль)\n"
                        f"🎁 Ваш бонус: {bonus} монет (5%)"
                    )
                except:
                    pass

            result_text = f"🎉 <b>ПОБЕДА!</b>\n💰 Выигрыш: {win_amount} монет"
        else:
            update_game_stats(message.from_user.id, "Кубы (дуэль)", 0)
            result_text = f"😢 <b>Поражение</b>\n💸 Проигрыш: {bet_amount} монет"

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        await bot.send_message(
            CHANNEL_ID,
            f"🎲 <b>Результат игры</b>\n\n"
            f"👤 Игрок: {message.from_user.first_name} (@{message.from_user.username or 'без_ника'})\n"
            f"🎯 Игрок: {user_roll} | 🤖 Бот: {bot_roll}\n"
            f"🎲 Выбор: {'🏆 Победа' if choice == 'win' else '💀 Поражение'}\n\n"
            f"{result_text}",
            reply_markup=channel_keyboard
        )

        # Уведомление в боте
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                message.from_user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎲 Игра: Кубы (дуэль)\n"
                f"💰 Выигрыш: {win_amount} монет\n"
                f"💳 Ваш баланс изменен: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                message.from_user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎲 Игра: Кубы (дуэль)\n"
                f"💸 Проигрыш: {bet_amount} монет\n"
                f"💳 Текущий баланс: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в кубах: {e}")

async def play_basketball_direct(message: Message, bet_amount: int, choice: str):
    try:
        basketball = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🏀")
        await asyncio.sleep(4)
        basketball_value = basketball.dice.value

        actual_result = "hit" if basketball_value >= 4 else "miss"
        win = choice == actual_result

        if win:
            coeff = 1.8 if choice == 'hit' else 1.3
            win_amount = int(bet_amount * coeff)
            update_balance(message.from_user.id, win_amount)
            update_game_stats(message.from_user.id, "Баскетбол", win_amount)

            # Реферальный бонус
            stats = get_user_stats(message.from_user.id)
            if stats and stats['referrer_id']:
                bonus = int(win_amount * 0.05)  # 5%
                add_referral_bonus(stats['referrer_id'], bonus)
                try:
                    await bot.send_message(
                        stats['referrer_id'],
                        f"💰 <b>Реферальный бонус!</b>\n"
                        f"👤 Ваш реферал выиграл в баскетбол\n"
                        f"🎁 Ваш бонус: {bonus} монет (5%)"
                    )
                except:
                    pass
            result_text = f"🎉 <b>ПОБЕДА!</b>\n💰 Выигрыш: {win_amount} монет (x{coeff})"
        else:
            update_game_stats(message.from_user.id, "Баскетбол", 0)
            result_text = f"😢 <b>Поражение</b>\n💸 Проигрыш: {bet_amount} монет"

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        await bot.send_message(
            CHANNEL_ID,
            f"🏀 <b>Результат игры</b>\n\n"
            f"👤 Игрок: {message.from_user.first_name} (@{message.from_user.username or 'без_ника'})\n"
            f"🎯 Результат: {'🎯 Попадание' if actual_result == 'hit' else '❌ Мимо'} ({basketball_value})\n"
            f"🎲 Выбор: {'🎯 Попадание' if choice == 'hit' else '❌ Мимо'}\n\n"
            f"{result_text}",
            reply_markup=channel_keyboard
        )

        # Уведомление в боте
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            coeff = 1.8 if choice == 'hit' else 1.3
            await bot.send_message(
                message.from_user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🏀 Игра: Баскетбол\n"
                f"💰 Выигрыш: {win_amount} монет (x{coeff})\n"
                f"💳 Ваш баланс изменен: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                message.from_user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🏀 Игра: Баскетбол\n"
                f"💸 Проигрыш: {bet_amount} монет\n"
                f"💳 Текущий баланс: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в баскетболе: {e}")

async def play_dice_higher_direct(message: Message, bet_amount: int, choice: str):
    try:
        dice = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(4)
        dice_value = dice.dice.value

        actual_result = "higher" if dice_value > 3 else "lower"
        win = choice == actual_result

        if win:
            win_amount = int(bet_amount * 1.8)
            update_balance(message.from_user.id, win_amount)
            update_game_stats(message.from_user.id, "Кубы больше/меньше", win_amount)

            # Реферальный бонус
            stats = get_user_stats(message.from_user.id)
            if stats and stats['referrer_id']:
                bonus = int(win_amount * 0.05)  # 5%
                add_referral_bonus(stats['referrer_id'], bonus)
                try:
                    await bot.send_message(
                        stats['referrer_id'],
                        f"💰 <b>Реферальный бонус!</b>\n"
                        f"👤 Ваш реферал выиграл в кубы больше/меньше\n"
                        f"🎁 Ваш бонус: {bonus} монет (5%)"
                    )
                except:
                    pass
            result_text = f"🎉 <b>ПОБЕДА!</b>\n💰 Выигрыш: {win_amount} монет"
        else:
            update_game_stats(message.from_user.id, "Кубы больше/меньше", 0)
            result_text = f"😢 <b>Поражение</b>\n💸 Проигрыш: {bet_amount} монет"

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        await bot.send_message(
            CHANNEL_ID,
            f"🎲 <b>Результат игры</b>\n\n"
            f"👤 Игрок: {message.from_user.first_name} (@{message.from_user.username or 'без_ника'})\n"
            f"🎯 Результат: {dice_value}\n"
            f"🎲 Выбор: {'⬆️ Больше 3' if choice == 'higher' else '⬇️ Меньше 4'}\n\n"
            f"{result_text}",
            reply_markup=channel_keyboard
        )

        # Уведомление в боте
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                message.from_user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎲 Игра: Кубы больше/меньше\n"
                f"💰 Выигрыш: {win_amount} монет\n"
                f"💳 Ваш баланс изменен: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                message.from_user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎲 Игра: Кубы больше/меньше\n"
                f"💸 Проигрыш: {bet_amount} монет\n"
                f"💳 Текущий баланс: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в кубах больше/меньше: {e}")

async def play_dice_even_direct(message: Message, bet_amount: int, choice: str):
    try:
        dice = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(4)
        dice_value = dice.dice.value

        actual_result = "even" if dice_value % 2 == 0 else "odd"
        win = choice == actual_result

        if win:
            win_amount = int(bet_amount * 1.8)
            update_balance(message.from_user.id, win_amount)
            update_game_stats(message.from_user.id, "Кубы чет/нечет", win_amount)

            # Реферальный бонус
            stats = get_user_stats(message.from_user.id)
            if stats and stats['referrer_id']:
                bonus = int(win_amount * 0.05)  # 5%
                add_referral_bonus(stats['referrer_id'], bonus)
                try:
                    await bot.send_message(
                        stats['referrer_id'],
                        f"💰 <b>Реферальный бонус!</b>\n"
                        f"👤 Ваш реферал выиграл в кубы чет/нечет\n"
                        f"🎁 Ваш бонус: {bonus} монет (5%)"
                    )
                except:
                    pass

            result_text = f"🎉 <b>ПОБЕДА!</b>\n💰 Выигрыш: {win_amount} монет"
        else:
            update_game_stats(message.from_user.id, "Кубы чет/нечет", 0)
            result_text = f"😢 <b>Поражение</b>\n💸 Проигрыш: {bet_amount} монет"

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        await bot.send_message(
            CHANNEL_ID,
            f"🎲 <b>Результат игры</b>\n\n"
            f"👤 Игрок: {message.from_user.first_name} (@{message.from_user.username or 'без_ника'})\n"
            f"🎯 Результат: {dice_value}\n"
            f"🎲 Выбор: {'2️⃣ Четное' if choice == 'even' else '1️⃣ Нечетное'}\n\n"
            f"{result_text}",
            reply_markup=channel_keyboard
        )

        # Уведомление в боте
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                message.from_user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎲 Игра: Кубы чет/нечет\n"
                f"💰 Выигрыш: {win_amount} монет\n"
                f"💳 Ваш баланс изменен: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                message.from_user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎲 Игра: Кубы чет/нечет\n"
                f"💸 Проигрыш: {bet_amount} монет\n"
                f"💳 Текущий баланс: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в кубах чет/нечет: {e}")

async def play_triada_direct(message: Message, bet_amount: int, choice: str):
    try:
        await bot.send_message(CHANNEL_ID, "🎲 Кидаем 3 кубика...")
        dice1 = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(2)
        dice2 = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(2)
        dice3 = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎲")
        await asyncio.sleep(2)

        dice_values = [dice1.dice.value, dice2.dice.value, dice3.dice.value]
        choice_num = int(choice)

        matches = dice_values.count(choice_num)
        coeff = 1.8 if matches == 1 else 2.4 if matches == 2 else 3.1 if matches == 3 else 0

        if coeff > 0:
            win_amount = int(bet_amount * coeff)
            update_balance(message.from_user.id, win_amount)
            update_game_stats(message.from_user.id, "Триада", win_amount)

            # Реферальный бонус
            stats = get_user_stats(message.from_user.id)
            if stats and stats['referrer_id']:
                bonus = int(win_amount * 0.05)  # 5%
                add_referral_bonus(stats['referrer_id'], bonus)
                try:
                    await bot.send_message(
                        stats['referrer_id'],
                        f"💰 <b>Реферальный бонус!</b>\n"
                        f"👤 Ваш реферал выиграл в триаду\n"
                        f"🎁 Ваш бонус: {bonus} монет (5%)"
                    )
                except:
                    pass

            result_text = f"🎉 <b>ПОБЕДА!</b>\n💰 Выигрыш: {win_amount} монет (x{coeff})"
        else:
            update_game_stats(message.from_user.id, "Триада", 0)
            result_text = f"😢 <b>Поражение</b>\n💸 Проигрыш: {bet_amount} монет"

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        await bot.send_message(
            CHANNEL_ID,
            f"🎲 <b>Результат игры</b>\n\n"
            f"👤 Игрок: {message.from_user.first_name} (@{message.from_user.username or 'без_ника'})\n"
            f"🎯 Кубики: {dice1.dice.value}, {dice2.dice.value}, {dice3.dice.value}\n"
            f"🎲 Выбор: {choice}\n"
            f"✨ Совпадений: {matches}\n\n"
            f"{result_text}",
            reply_markup=channel_keyboard
        )

        # Уведомление в боте
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if coeff > 0:
            await bot.send_message(
                message.from_user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎲 Игра: Триада\n"
                f"✨ Совпадений: {matches}\n"
                f"💰 Выигрыш: {win_amount} монет (x{coeff})\n"
                f"💳 Ваш баланс изменен: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                message.from_user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎲 Игра: Триада\n"
                f"✨ Совпадений: {matches}\n"
                f"💸 Проигрыш: {bet_amount} монет\n"
                f"💳 Текущий баланс: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в триаде: {e}")

async def process_game_queue():
    global is_game_running
    is_game_running = True

    while game_queue:
        bet_info = game_queue.pop(0)
        user = bet_info['user']

        try:
            # Создаем mock message объект для функций игр
            class MockMessage:
                def __init__(self, user):
                    self.from_user = user

            mock_message = MockMessage(user)

            # Отправляем сообщение о начале игры в канал
            game_names = {
                'bowling': '🎳 Боулинг',
                'dice_duel': '🎲 Кубы (дуэль)',
                'basketball': '🏀 Баскетбол',
                'dice_higher': '🎲 Кубы больше/меньше',
                'dice_even': '🎲 Кубы чет/нечет',
                'triada': '🎲 Триада',
                'darts': '🎯 Дартс'
            }

            choice_texts = {
                ('bowling', 'win'): '🏆 Победа',
                ('bowling', 'loss'): '💀 Поражение',
                ('dice_duel', 'win'): '🏆 Победа',
                ('dice_duel', 'loss'): '💀 Поражение',
                ('basketball', 'hit'): '🎯 Попадание',
                ('basketball', 'miss'): '❌ Мимо',
                ('dice_higher', 'higher'): '⬆️ Больше 3',
                ('dice_higher', 'lower'): '⬇️ Меньше 4',
                ('dice_even', 'even'): '2️⃣ Четное',
                ('dice_even', 'odd'): '1️⃣ Нечетное',
                ('darts', 'red'): '🔴 Красное',
                ('darts', 'white'): '⚪ Белое'
            }

            game_name = game_names.get(bet_info['game_type'], 'Неизвестная игра')
            choice_text = choice_texts.get((bet_info['game_type'], bet_info['choice']), str(bet_info['choice']))

            await bot.send_message(
                CHANNEL_ID,
                f"🎮 <b>Новая игра!</b>\n\n"
                f"👤 Игрок: {user.first_name} (@{user.username or 'без_ника'})\n"
                f"🎯 Игра: {game_name}\n"
                f"💰 Ставка: {bet_info['bet_amount']} монет\n"
                f"🎲 Выбор: {choice_text}\n\n"
                f"🎮 Начинаем игру..."
            )

            await asyncio.sleep(1)

            # Запускаем игру
            await bet_info['game_function'](mock_message, bet_info['bet_amount'], bet_info['choice'])

            # Пауза между играми
            await asyncio.sleep(3)

        except Exception as e:
            print(f"Ошибка в обработке ставки: {e}")
            # Возвращаем деньги при ошибке
            update_balance(user.id, bet_info['bet_amount'])

    is_game_running = False

async def play_darts_direct(message: Message, bet_amount: int, choice: str):
    try:
        darts = await bot.send_dice(chat_id=CHANNEL_ID, emoji="🎯")
        await asyncio.sleep(4)
        darts_value = darts.dice.value

        # Логика определения цвета для дартс (адаптируйте под реальные значения)
        actual_result = "red" if darts_value in [2, 4, 6] else "white"
        win = choice == actual_result

        if win:
            win_amount = int(bet_amount * 1.8)
            update_balance(message.from_user.id, win_amount)
            update_game_stats(message.from_user.id, "Дартс", win_amount)

            # Реферальный бонус
            stats = get_user_stats(message.from_user.id)
            if stats and stats['referrer_id']:
                bonus = int(win_amount * 0.05)  # 5%
                add_referral_bonus(stats['referrer_id'], bonus)
                try:
                    await bot.send_message(
                        stats['referrer_id'],
                        f"💰 <b>Реферальный бонус!</b>\n"
                        f"👤 Ваш реферал выиграл в дартс\n"
                        f"🎁 Ваш бонус: {bonus} монет (5%)"
                    )
                except:
                    pass

            result_text = f"🎉 <b>ПОБЕДА!</b>\n💰 Выигрыш: {win_amount} монет"
        else:
            update_game_stats(message.from_user.id, "Дартс", 0)
            result_text = f"😢 <b>Поражение</b>\n💸 Проигрыш: {bet_amount} монет"

        # Инлайн-кнопка для канала
        channel_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Сделать ставку", url=f"https://t.me/{(await bot.get_me()).username}?start=game")
            ]]
        )

        await bot.send_message(
            CHANNEL_ID,
            f"🎯 <b>Результат игры</b>\n\n"
            f"👤 Игрок: {message.from_user.first_name} (@{message.from_user.username or 'без_ника'})\n"
            f"🎯 Результат: {'🔴 Красное' if actual_result == 'red' else '⚪ Белое'} ({darts_value})\n"
            f"🎲 Выбор: {'🔴 Красное' if choice == 'red' else '⚪ Белое'}\n\n"
            f"{result_text}",
            reply_markup=channel_keyboard
        )

        # Уведомление в боте
        bot_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎰 Главное меню", callback_data="main_menu")
            ]]
        )

        if win:
            await bot.send_message(
                message.from_user.id,
                f"🎉 <b>Поздравляем с победой!</b>\n\n"
                f"🎯 Игра: Дартс\n"
                f"💰 Выигрыш: {win_amount} монет\n"
                f"💳 Ваш баланс изменен: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )
        else:
            await bot.send_message(
                message.from_user.id,
                f"😔 <b>Повезет в другой раз :)</b>\n\n"
                f"🎯 Игра: Дартс\n"
                f"💸 Проигрыш: {bet_amount} монет\n"
                f"💳 Текущий баланс: {get_balance(message.from_user.id)} монет",
                reply_markup=bot_keyboard
            )

    except Exception as e:
        print(f"Ошибка в дартс: {e}")

@router.message(F.text == "⬅️ Назад")
async def back_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()

    if current_state == GameState.play_menu:
        await state.set_state(GameState.main_menu)
        balance = get_balance(message.from_user.id)
        await message.answer(
            f"🎰 <b>MoonCasino</b>\n"
            f"💰 Ваш баланс: <b>{balance}</b> монет",
            reply_markup=get_start_keyboard()
        )
    elif current_state == GameState.profile:
        await state.set_state(GameState.main_menu)
        balance = get_balance(message.from_user.id)
        await message.answer(
            f"🎰 <b>MoonCasino</b>\n"
            f"💰 Ваш баланс: <b>{balance}</b> монет",
            reply_markup=get_start_keyboard()
        )
    elif current_state in [GameState.bot_games, GameState.channel_games]:
        await state.set_state(GameState.play_menu)
        await message.answer(
            "🎮 <b>Выберите режим игры:</b>",
            reply_markup=get_play_menu_keyboard()
        )
    elif current_state in [GameState.mines_setup, GameState.tower_setup]:
        await state.set_state(GameState.bot_games)
        await message.answer(
            "🤖 <b>Игры в боте:</b>\n\n"
            "💣 <b>Мины</b> - найдите алмазы, избегая мин\n"
            "🏗 <b>Башня</b> - поднимайтесь выше по уровням",
            reply_markup=get_bot_games_keyboard()
        )
    elif current_state in [GameState.channel_bowling, GameState.channel_basketball, 
                          GameState.channel_dice_duel, GameState.channel_dice_higher,
                          GameState.channel_dice_even, GameState.channel_triada, 
                          GameState.channel_darts]:
        await state.set_state(GameState.channel_games)
        await message.answer(
            "💬 <b>Игры в канале:</b>\n\n"
            "🎳 <b>Боулинг</b> - дуэль x1.8\n"
            "🏀 <b>Баскетбол</b> - попадание x1.8, мимо x1.3\n"
            "🎲 <b>Кубы (дуэль)</b> - x1.8\n"
            "🎲 <b>Больше/меньше</b> - x1.8\n"
            "🎲 <b>Чет/нечет</b> - x1.8\n"
            "🎲 <b>Триада</b> - 1 совп. x1.8, 2 совп. x2.4, 3 совп. x3.1\n"
            "🎯 <b>Дартс</b> - x1.8",
            reply_markup=get_channel_games_keyboard()
        )
    elif current_state == GameState.waiting_bet:
        # Определяем из какого состояния пришли в waiting_bet
        data = await state.get_data()
        if 'mines_count' in data or 'tower_mines' in data:
            await state.set_state(GameState.bot_games)
            await message.answer(
                "🤖 <b>Игры в боте:</b>\n\n"
                "💣 <b>Мины</b> - найдите алмазы, избегая мин\n"
                "🏗 <b>Башня</b> - поднимайтесь выше по уровням",
                reply_markup=get_bot_games_keyboard()
            )
        else:
            await state.set_state(GameState.channel_games)
            await message.answer(
                "💬 <b>Игры в канале:</b>\n\n"
                "🎳 <b>Боулинг</b> - дуэль x1.8\n"
                "🏀 <b>Баскетбол</b> - попадание x1.8, мимо x1.3\n"
                "🎲 <b>Кубы (дуэль)</b> - x1.8\n"
                "🎲 <b>Больше/меньше</b> - x1.8\n"
                "🎲 <b>Чет/нечет</b> - x1.8\n"
                "🎲 <b>Триада</b> - 1 совп. x1.8, 2 совп. x2.4, 3 совп. x3.1\n"
                "🎯 <b>Дартс</b> - x1.8",
                reply_markup=get_channel_games_keyboard()
            )
    else:
         await state.set_state(GameState.main_menu)
         balance = get_balance(message.from_user.id)
         await message.answer(
            f"🎰 <b>MoonCasino</b>\n"
            f"💰 Ваш баланс: <b>{balance}</b> монет",
            reply_markup=get_start_keyboard()
        )

# Callback handlers для мин
@router.callback_query(F.data.startswith("mines_"))
async def mines_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if callback.data == "mines_cash_out":
        bet_amount = data['bet']
        clicks_count = data['clicks_count']
        mines_count = data['mines_count']

        if clicks_count > 0:
            current_coeff = MINES_COEFFICIENTS[mines_count][clicks_count - 1]
            win_amount = int(bet_amount * current_coeff)
            update_balance(callback.from_user.id, win_amount)

            await callback.message.edit_text(
                f"💰 <b>Выигрыш забран!</b>\n"
                f"💎 Открыто ячеек: {clicks_count}\n"
                f"💰 Выигрыш: {win_amount} монет (x{current_coeff})\n"
                f"💳 Новый баланс: {get_balance(callback.from_user.id)} монет"
            )

        await state.set_state(GameState.main_menu)
        await callback.answer("Выигрыш забран!")
        return

    elif callback.data == "mines_exit":
        await callback.message.edit_text("❌ Игра завершена без выигрыша")
        await state.set_state(GameState.main_menu)
        await callback.answer("Игра завершена")
        return

    coords = callback.data.split("_")[1:]
    row, col = int(coords[0]), int(coords[1])

    mines_positions = data['mines_positions']
    opened_cells = data['opened_cells']
    clicks_count = data['clicks_count']
    mines_count = data['mines_count']
    bet_amount = data['bet']

    if (row, col) in opened_cells:
        await callback.answer("Эта ячейка уже открыта!")
        return

    if (row, col) in mines_positions:
        await callback.message.edit_text(
            f"💥 <b>БУМ! Вы наткнулись на мину!</b>\n"
            f"💸 Проигрыш: {bet_amount} монет\n"
            f"💳 Баланс: {get_balance(callback.from_user.id)} монет"
        )
        await state.set_state(GameState.main_menu)
        await callback.answer("💥 Мина!")
        return

    opened_cells.append((row, col))
    clicks_count += 1

    await state.update_data(opened_cells=opened_cells, clicks_count=clicks_count)

    current_coeff = MINES_COEFFICIENTS[mines_count][clicks_count - 1] if clicks_count <= len(MINES_COEFFICIENTS[mines_count]) else MINES_COEFFICIENTS[mines_count][-1]

    keyboard = create_mines_inline_keyboard(mines_count, opened_cells, current_coeff)

    await callback.message.edit_text(
        f"💣 <b>Мины ({mines_count} мины)</b>\n"
        f"💰 Ставка: {bet_amount} монет\n"
        f"🔍 Найдите алмазы, избегайте мин!\n"
        f"💎 Кликов: {clicks_count} | Коэффициент: x{current_coeff}",
        reply_markup=keyboard
    )

    await callback.answer("💎 Алмаз найден!")

# Callback handlers для башни
@router.callback_query(F.data.startswith("tower_"))
async def tower_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if callback.data == "tower_cash_out":
        bet_amount = data['bet']
        current_level = data['current_level']
        tower_mines = data['tower_mines']

        if current_level > 0:
            coeffs = TOWER_COEFFICIENTS[tower_mines]
            final_coeff = coeffs[current_level - 1] if current_level - 1 < len(coeffs) else coeffs[-1]
            win_amount = int(bet_amount * final_coeff)
            update_balance(callback.from_user.id, win_amount)

            await callback.message.edit_text(
                f"💰 <b>Выигрыш забран!</b>\n"
                f"🆙 Достигнут уровень: {current_level}\n"
                f"💰 Выигрыш: {win_amount} монет (x{final_coeff})\n"
                f"💳 Новый баланс: {get_balance(callback.from_user.id)} монет"
            )

        await state.set_state(GameState.main_menu)
        await callback.answer("Выигрыш забран!")
        return

    elif callback.data == "tower_exit":
        await callback.message.edit_text("❌ Игра завершена")
        await state.set_state(GameState.main_menu)
        await callback.answer("Игра завершена")
        return

    coords = callback.data.split("_")[1:]
    level, cell = int(coords[0]), int(coords[1])

    tower_structure = data['tower_structure']
    opened_levels = data['opened_levels']
    current_level = data['current_level']
    tower_mines = data['tower_mines']
    bet_amount = data['bet']

    if level != current_level:
        await callback.answer("Можно кликать только на текущем уровне!")
        return

    if cell in tower_structure[level]:
        await callback.message.edit_text(
            f"💥 <b>БУМ! Вы наткнулись на мину на уровне {level + 1}!</b>\n"
            f"💸 Проигрыш: {bet_amount} монет\n"
            f"💳 Баланс: {get_balance(callback.from_user.id)} монет"
        )
        await state.set_state(GameState.main_menu)
        await callback.answer("💥 Мина!")
        return

    opened_levels.append((level, cell))
    current_level += 1

    await state.update_data(opened_levels=opened_levels, current_level=current_level)

    if current_level >= 6:
        coeffs = TOWER_COEFFICIENTS[tower_mines]
        final_coeff = coeffs[-1]
        win_amount = int(bet_amount * final_coeff)
        update_balance(callback.from_user.id, win_amount)

        await callback.message.edit_text(
            f"🎉 <b>ПОЗДРАВЛЯЕМ! Вы достигли вершины башни!</b>\n"
            f"🏆 Все 6 уровней пройдены!\n"
            f"💰 Выигрыш: {win_amount} монет (x{final_coeff})\n"
            f"💳 Новый баланс: {get_balance(callback.from_user.id)} монет"
        )
        await state.set_state(GameState.main_menu)
        await callback.answer("🏆 Башня покорена!")
        return

    keyboard = create_tower_inline_keyboard(tower_mines, opened_levels, current_level)

    await callback.message.edit_text(
        f"🏗 <b>Башня ({tower_mines} {'мина' if tower_mines == 1 else 'мины'})</b>\n"
        f"💰 Ставка: {bet_amount} монет\n"
        f"🆙 Уровень: {current_level + 1}/6\n"
        f"🏗 Поднимайтесь выше, избегая мин!",
        reply_markup=keyboard
    )

    await callback.answer(f"✅ Уровень {level + 1} пройден!")

@router.callback_query(F.data == "add_1000_coins")
async def add_coins_callback(callback: CallbackQuery):
    if callback.from_user.id == 6774136020:
        try:
            # Убеждаемся что пользователь существует в базе
            create_user(callback.from_user.id)

            # Начисляем монеты
            update_balance(callback.from_user.id, 1000)
            new_balance = get_balance(callback.from_user.id)

            await callback.answer("✅ Добавлено +1000 монет!")

            # Отправляем новое сообщение вместо редактирования
            await callback.message.answer(
                f"✅ <b>Монеты начислены!</b>\n"
                f"💰 Добавлено: +1000 монет\n"
                f"💳 Новый баланс: <b>{new_balance}</b> монет"
            )
        except Exception as e:
            await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    else:
        await callback.answer("❌ У вас нет доступа к этой функции!", show_alert=True)

@router.callback_query(F.data == "add_coins_by_id")
async def add_coins_by_id_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id == 6774136020:
        await state.set_state(GameState.admin_add_coins_id)
        await callback.message.answer(
            "💳 <b>Начисление валюты</b>\n\n"
            "Введите ID пользователя:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Отмена")]],
                resize_keyboard=True
            )
        )
        await callback.answer()
    else:
        await callback.answer("❌ У вас нет доступа к этой функции!", show_alert=True)

@router.message(GameState.admin_add_coins_id)
async def admin_process_user_id(message: Message, state: FSMContext):
    if message.text == "⬅️ Отмена":
        await state.set_state(GameState.profile)
        await message.answer(
            "❌ Операция отменена",
            reply_markup=get_profile_keyboard(message.from_user.id)
        )
        return

    try:
        user_id = int(message.text)
        await state.update_data(target_user_id=user_id)
        await state.set_state(GameState.admin_add_coins_amount)
        await message.answer(
            f"💳 <b>Начисление валюты</b>\n\n"
            f"ID пользователя: {user_id}\n"
            f"Введите сумму для начисления:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Отмена")]],
                resize_keyboard=True
            )
        )
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите числовой ID:")

@router.message(GameState.admin_add_coins_amount)
async def admin_process_amount(message: Message, state: FSMContext):
    if message.text == "⬅️ Отмена":
        await state.set_state(GameState.profile)
        await message.answer(
            "❌ Операция отменена",
            reply_markup=get_profile_keyboard(message.from_user.id)
        )
        return

    try:
        amount = int(message.text)
        data = await state.get_data()
        target_user_id = data['target_user_id']

        # Создаем пользователя если его нет
        create_user(target_user_id)

        # Начисляем валюту
        update_balance(target_user_id, amount)
        new_balance = get_balance(target_user_id)

        await state.set_state(GameState.profile)
        await message.answer(
            f"✅ <b>Валюта начислена!</b>\n\n"
            f"👤 ID пользователя: {target_user_id}\n"
            f"💰 Начислено: {amount} монет\n"
            f"💳 Новый баланс: {new_balance} монет",
            reply_markup=get_profile_keyboard(message.from_user.id)
        )
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите числовое значение:")

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GameState.main_menu)
    balance = get_balance(callback.from_user.id)
    await callback.message.edit_text(
        f"🎰 <b>MoonCasino</b>\n"
        f"💰 Ваш баланс: <b>{balance}</b> монет"
    )
    await callback.message.answer(
        "🎮 Выберите действие:",
        reply_markup=get_start_keyboard()
    )
    await callback.answer("🏠 Главное меню")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())