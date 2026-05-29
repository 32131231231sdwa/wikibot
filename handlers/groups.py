from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from keyboards import group_view_kb, group_settings_kb, cancel_kb, confirm_kb, article_list_kb
from utils import escape_html
import nav

router = Router()


class GroupStates(StatesGroup):
    waiting_name = State()
    renaming = State()


def _get_group_back_cb(group):
    if group['parent_group_id']:
        return f"group:{group['parent_group_id']}"
    elif group['folder_id']:
        return f"folder:{group['folder_id']}"
    return "my_folders"


@router.callback_query(F.data.startswith("create_group:"))
async def cb_create_group_start(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    parent_type = parts[1]
    parent_id = int(parts[2])
    await state.set_state(GroupStates.waiting_name)
    await state.update_data(parent_type=parent_type, parent_id=parent_id)
    back = f"folder:{parent_id}" if parent_type == 'folder' else f"group:{parent_id}"
    await call.message.edit_text(
        "📂 <b>Создание группы</b>\n\nВведите название группы:",
        parse_mode="HTML",
        reply_markup=cancel_kb(back),
    )
    await call.answer()


@router.message(GroupStates.waiting_name)
async def msg_group_name(message: Message, state: FSMContext):
    data = await state.get_data()
    parent_type = data['parent_type']
    parent_id = data['parent_id']
    title = message.text.strip()
    if not title:
        await message.answer("❗ Название не может быть пустым:")
        return

    folder_id = parent_id if parent_type == 'folder' else None
    parent_group_id = parent_id if parent_type == 'group' else None

    if parent_type == 'group':
        parent = db.get_group(parent_id)
        if parent:
            folder_id = parent['folder_id']

    group_id = db.create_group(
        title=title,
        owner_tg_id=message.from_user.id,
        folder_id=folder_id,
        parent_group_id=parent_group_id,
    )
    await state.clear()

    user = db.get_user(message.from_user.id)
    group = db.get_group(group_id)
    is_owner = user and group['owner_id'] == user['id']

    await message.answer(
        f"✅ Группа <b>{escape_html(title)}</b> создана!\n\nДобавляйте статьи и подгруппы:",
        parse_mode="HTML",
        reply_markup=group_view_kb(group_id, is_owner_or_editor=True),
    )


@router.callback_query(F.data.startswith("group:"))
async def cb_group_view(call: CallbackQuery, state: FSMContext):
    group_id = int(call.data.split(":")[1])
    group = db.get_group(group_id)
    if not group:
        await call.answer("Группа не найдена!", show_alert=True)
        return

    user = db.get_user(call.from_user.id)
    is_owner = user and group['owner_id'] == user['id']
    is_editor = db.is_editor('group', group_id, call.from_user.id)

    subgroups = db.get_subgroups(group_id)
    articles = db.get_group_articles(group_id)

    text = (
        f"📂 <b>{escape_html(group['title'])}</b>\n\n"
        f"📂 Подгрупп: {len(subgroups)}\n"
        f"📜 Статей: {len(articles)}"
    )
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=group_view_kb(group_id, is_owner_or_editor=is_owner or is_editor),
    )
    await call.answer()


@router.callback_query(F.data.startswith("group_back:"))
async def cb_group_back(call: CallbackQuery):
    group_id = int(call.data.split(":")[1])
    group = db.get_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    back_cb = _get_group_back_cb(group)
    if back_cb.startswith("folder:"):
        folder_id = int(back_cb.split(":")[1])
        await nav.show_folder(call, folder_id)
    elif back_cb.startswith("group:"):
        parent_id = int(back_cb.split(":")[1])
        await nav.show_group(call, parent_id)
    else:
        await nav.show_my_folders(call)


@router.callback_query(F.data.startswith("group_subgroups:"))
async def cb_group_subgroups(call: CallbackQuery):
    group_id = int(call.data.split(":")[1])
    subgroups = db.get_subgroups(group_id)
    group = db.get_group(group_id)

    builder = InlineKeyboardBuilder()
    for g in subgroups:
        builder.button(text=f"📂 {g['title']}", callback_data=f"group:{g['id']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"group:{group_id}"))

    text = f"📂 <b>Подгруппы в «{escape_html(group['title'])}»</b>\n\n"
    text += f"Найдено: {len(subgroups)}" if subgroups else "Подгрупп пока нет."
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("group_articles:"))
async def cb_group_articles(call: CallbackQuery):
    group_id = int(call.data.split(":")[1])
    articles = db.get_group_articles(group_id)
    group = db.get_group(group_id)

    text = f"📜 <b>Статьи в «{escape_html(group['title'])}»</b>\n\n"
    if articles:
        await call.message.edit_text(
            text + f"Найдено: {len(articles)}",
            parse_mode="HTML",
            reply_markup=article_list_kb(articles, back_cb=f"group:{group_id}"),
        )
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="◀️ Назад", callback_data=f"group:{group_id}")
        await call.message.edit_text(
            text + "Статей пока нет.",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
    await call.answer()


@router.callback_query(F.data.startswith("group_settings:"))
async def cb_group_settings(call: CallbackQuery):
    group_id = int(call.data.split(":")[1])
    group = db.get_group(group_id)
    user = db.get_user(call.from_user.id)
    if not group:
        await call.answer("Не найдено", show_alert=True)
        return
    is_owner = user and group['owner_id'] == user['id']
    is_editor = db.is_editor('group', group_id, call.from_user.id)
    if not is_owner and not is_editor:
        await call.answer("Нет прав", show_alert=True)
        return
    await call.message.edit_text(
        f"⚙️ <b>Настройки группы «{escape_html(group['title'])}»</b>",
        parse_mode="HTML",
        reply_markup=group_settings_kb(group_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("rename_group:"))
async def cb_rename_group_start(call: CallbackQuery, state: FSMContext):
    group_id = int(call.data.split(":")[1])
    await state.set_state(GroupStates.renaming)
    await state.update_data(group_id=group_id)
    await call.message.edit_text(
        "✏️ Введите новое название группы:",
        reply_markup=cancel_kb(f"group_settings:{group_id}"),
    )
    await call.answer()


@router.message(GroupStates.renaming)
async def msg_rename_group(message: Message, state: FSMContext):
    data = await state.get_data()
    group_id = data['group_id']
    title = message.text.strip()
    if not title:
        await message.answer("❗ Название не может быть пустым:")
        return
    db.update_group_title(group_id, title)
    await state.clear()
    await message.answer(
        f"✅ Группа переименована в <b>{escape_html(title)}</b>",
        parse_mode="HTML",
        reply_markup=group_settings_kb(group_id),
    )


@router.callback_query(F.data.startswith("delete_group:"))
async def cb_delete_group_confirm(call: CallbackQuery):
    group_id = int(call.data.split(":")[1])
    group = db.get_group(group_id)
    user = db.get_user(call.from_user.id)
    if not user or group['owner_id'] != user['id']:
        await call.answer("Только владелец может удалить группу.", show_alert=True)
        return
    await call.message.edit_text(
        f"🗑 Удалить группу <b>{escape_html(group['title'])}</b>?\n\n"
        "⚠️ Все подгруппы и статьи также будут удалены.",
        parse_mode="HTML",
        reply_markup=confirm_kb(f"delete_group_yes:{group_id}", f"group_settings:{group_id}"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("delete_group_yes:"))
async def cb_delete_group_yes(call: CallbackQuery):
    group_id = int(call.data.split(":")[1])
    group = db.get_group(group_id)
    user = db.get_user(call.from_user.id)
    if not user or not group or group['owner_id'] != user['id']:
        await call.answer("Нет прав", show_alert=True)
        return
    back_cb = _get_group_back_cb(group)
    db.delete_group(group_id)
    await call.answer("✅ Группа удалена.")
    if back_cb.startswith("folder:"):
        folder_id = int(back_cb.split(":")[1])
        await nav.show_folder(call, folder_id)
    elif back_cb.startswith("group:"):
        parent_id = int(back_cb.split(":")[1])
        await nav.show_group(call, parent_id)
    else:
        await nav.show_my_folders(call)
