from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from keyboards import editors_kb, cancel_kb
from utils import escape_html
import nav

router = Router()


class EditorStates(StatesGroup):
    waiting_username = State()


@router.callback_query(F.data.startswith("editors:"))
async def cb_editors_view(call: CallbackQuery):
    parts = call.data.split(":")
    entity_type = parts[1]
    entity_id = int(parts[2])

    # Check ownership
    user = db.get_user(call.from_user.id)
    if not user:
        await call.answer("Не авторизован.", show_alert=True)
        return

    if entity_type == 'folder':
        entity = db.get_folder(entity_id)
        is_owner = entity and entity['owner_id'] == user['id']
    elif entity_type == 'group':
        entity = db.get_group(entity_id)
        is_owner = entity and entity['owner_id'] == user['id']
    else:
        entity = db.get_article(entity_id)
        is_owner = entity and entity['owner_id'] == user['id']

    if not is_owner:
        await call.answer("Только владелец может управлять редакторами.", show_alert=True)
        return

    editors = db.get_editors(entity_type, entity_id)
    title = entity['title'] if entity else "?"

    text = (
        f"👥 <b>Редакторы «{escape_html(title)}»</b>\n\n"
    )
    if editors:
        for ed in editors:
            name = f"@{ed['username']}" if ed['username'] else ed['first_name']
            text += f"• {escape_html(name)}\n"
    else:
        text += "Редакторов пока нет.\n"
    text += "\nНажмите на редактора, чтобы удалить его."

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=editors_kb(entity_type, entity_id, editors),
    )
    await call.answer()


@router.callback_query(F.data.startswith("add_editor:"))
async def cb_add_editor_start(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    entity_type = parts[1]
    entity_id = int(parts[2])
    await state.set_state(EditorStates.waiting_username)
    await state.update_data(entity_type=entity_type, entity_id=entity_id)
    await call.message.edit_text(
        "➕ Введите @username или Telegram ID пользователя для добавления редактором:\n\n"
        "⚠️ Пользователь должен ранее запустить бота.",
        reply_markup=cancel_kb(f"editors:{entity_type}:{entity_id}"),
    )
    await call.answer()


@router.message(EditorStates.waiting_username)
async def msg_add_editor_username(message: Message, state: FSMContext):
    data = await state.get_data()
    entity_type = data['entity_type']
    entity_id = data['entity_id']
    text = (message.text or "").strip()

    target_user = None
    if text.lstrip('@').isdigit():
        # By Telegram ID
        tg_id = int(text.lstrip('@'))
        target_user = db.get_user(tg_id)
    else:
        # By username
        target_user = db.get_user_by_username(text)

    if not target_user:
        await message.answer(
            "❗ Пользователь не найден. Убедитесь, что он запускал бота.\n\nВведите @username или ID:"
        )
        return

    # Check if trying to add self
    self_user = db.get_user(message.from_user.id)
    if self_user and target_user['id'] == self_user['id']:
        await message.answer("❗ Нельзя добавить себя как редактора.")
        return

    db.add_editor(entity_type, entity_id, target_user['id'])
    await state.clear()

    name = f"@{target_user['username']}" if target_user['username'] else target_user['first_name']
    editors = db.get_editors(entity_type, entity_id)

    await message.answer(
        f"✅ <b>{escape_html(name)}</b> добавлен как редактор!",
        parse_mode="HTML",
        reply_markup=editors_kb(entity_type, entity_id, editors),
    )


@router.callback_query(F.data.startswith("remove_editor:"))
async def cb_remove_editor(call: CallbackQuery):
    parts = call.data.split(":")
    entity_type = parts[1]
    entity_id = int(parts[2])
    editor_user_id = int(parts[3])

    user = db.get_user(call.from_user.id)
    if not user:
        await call.answer("Нет прав.", show_alert=True)
        return

    if entity_type == 'folder':
        entity = db.get_folder(entity_id)
    elif entity_type == 'group':
        entity = db.get_group(entity_id)
    else:
        entity = db.get_article(entity_id)

    if not entity or entity['owner_id'] != user['id']:
        await call.answer("Только владелец может удалять редакторов.", show_alert=True)
        return

    db.remove_editor(entity_type, entity_id, editor_user_id)
    editors = db.get_editors(entity_type, entity_id)
    ed_user = db.get_user_by_id(editor_user_id)
    name = f"@{ed_user['username']}" if ed_user and ed_user['username'] else (ed_user['first_name'] if ed_user else "?")

    await call.answer(f"Редактор {name} удалён.")

    entity_obj = entity
    title = entity_obj['title']
    text = f"👥 <b>Редакторы «{escape_html(title)}»</b>\n\n"
    if editors:
        for ed in editors:
            n = f"@{ed['username']}" if ed['username'] else ed['first_name']
            text += f"• {escape_html(n)}\n"
    else:
        text += "Редакторов пока нет.\n"

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=editors_kb(entity_type, entity_id, editors),
    )


@router.callback_query(F.data.startswith("back_from_editors:"))
async def cb_back_from_editors(call: CallbackQuery):
    parts = call.data.split(":")
    entity_type = parts[1]
    entity_id = int(parts[2])
    if entity_type == 'folder':
        await nav.show_folder_settings(call, entity_id)
    elif entity_type == 'group':
        await nav.show_group_settings(call, entity_id)
    else:
        await nav.show_article_settings(call, entity_id)
