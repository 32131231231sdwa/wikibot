from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from i18n import get_strings, TRANSLATIONS
from keyboards import settings_kb, language_select_kb, view_mode_select_kb, main_menu_kb

router = Router()


def _s(tg_id: int) -> dict:
    lang = db.get_user_language(tg_id)
    return get_strings(lang)


# ─── Settings main screen ─────────────────────────────────────────────────────

@router.callback_query(F.data == "settings")
async def cb_settings(call: CallbackQuery, state: FSMContext):
    await state.clear()
    tg_id = call.from_user.id
    lang = db.get_user_language(tg_id)
    view_mode = db.get_user_view_mode(tg_id)
    s = get_strings(lang)
    await call.message.edit_text(
        s.get('settings_title', '⚙️ <b>Настройки</b>'),
        parse_mode="HTML",
        reply_markup=settings_kb(s, lang, view_mode),
    )
    await call.answer()


# ─── Language picker ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "settings_language")
async def cb_settings_language(call: CallbackQuery):
    tg_id = call.from_user.id
    lang = db.get_user_language(tg_id)
    s = get_strings(lang)
    await call.message.edit_text(
        s.get('language_title', '🌐 <b>Выберите язык:</b>'),
        parse_mode="HTML",
        reply_markup=language_select_kb(lang, s),
    )
    await call.answer()


@router.callback_query(F.data.startswith("set_language:"))
async def cb_set_language(call: CallbackQuery):
    tg_id = call.from_user.id
    new_lang = call.data.split(":", 1)[1]
    if new_lang not in TRANSLATIONS:
        await call.answer("Неизвестный язык.", show_alert=True)
        return
    db.set_user_language(tg_id, new_lang)
    s = get_strings(new_lang)
    lang_name = TRANSLATIONS[new_lang].get('lang_name', new_lang)
    await call.answer(s.get('lang_saved', '✅ Язык изменён!').format(lang=lang_name), show_alert=False)
    # Refresh settings screen in new language
    view_mode = db.get_user_view_mode(tg_id)
    await call.message.edit_text(
        s.get('settings_title', '⚙️ <b>Настройки</b>'),
        parse_mode="HTML",
        reply_markup=settings_kb(s, new_lang, view_mode),
    )


# ─── View mode picker ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "settings_mode")
async def cb_settings_mode(call: CallbackQuery):
    tg_id = call.from_user.id
    s = _s(tg_id)
    view_mode = db.get_user_view_mode(tg_id)
    await call.message.edit_text(
        s.get('mode_title', '👁 <b>Режим просмотра</b>'),
        parse_mode="HTML",
        reply_markup=view_mode_select_kb(view_mode, s),
    )
    await call.answer()


@router.callback_query(F.data.startswith("set_view_mode:"))
async def cb_set_view_mode(call: CallbackQuery):
    tg_id = call.from_user.id
    new_mode = call.data.split(":", 1)[1]
    if new_mode not in ('full', 'compact'):
        await call.answer("Неизвестный режим.", show_alert=True)
        return
    db.set_user_view_mode(tg_id, new_mode)
    lang = db.get_user_language(tg_id)
    s = get_strings(lang)
    await call.answer(s.get('mode_saved', '✅ Режим изменён!'), show_alert=False)
    # Refresh settings screen
    await call.message.edit_text(
        s.get('settings_title', '⚙️ <b>Настройки</b>'),
        parse_mode="HTML",
        reply_markup=settings_kb(s, lang, new_mode),
    )
