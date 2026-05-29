from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from database import upsert_user, get_user_language, get_user_view_mode
from i18n import get_strings
from keyboards import main_menu_kb, back_main_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    tg_id = message.from_user.id
    upsert_user(
        tg_id=tg_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    lang = get_user_language(tg_id)
    s = get_strings(lang)
    name = message.from_user.first_name or "пользователь"
    await message.answer(
        s.get('welcome', '👋 Привет, <b>{name}</b>!\n\nВыбери действие:').format(name=name),
        parse_mode="HTML",
        reply_markup=main_menu_kb(s),
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    tg_id = call.from_user.id
    lang = get_user_language(tg_id)
    s = get_strings(lang)
    await call.message.edit_text(
        s.get('main_menu_title', '🏠 <b>Главное меню</b>\n\nВыбери действие:'),
        parse_mode="HTML",
        reply_markup=main_menu_kb(s),
    )
    await call.answer()
