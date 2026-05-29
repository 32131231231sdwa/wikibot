from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from keyboards import (
    folder_list_kb, folder_view_kb, folder_settings_kb,
    main_menu_kb, cancel_kb, confirm_kb, back_main_kb
)
from utils import generate_token, format_access, escape_html

router = Router()


class FolderStates(StatesGroup):
    waiting_name = State()
    renaming = State()


# ─── My Folders ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_folders")
async def cb_my_folders(call: CallbackQuery, state: FSMContext):
    await state.clear()
    folders = db.get_user_folders(call.from_user.id)
    if not folders:
        await call.message.edit_text(
            "📁 У вас пока нет папок.\n\nСоздайте первую!",
            reply_markup=cancel_kb("main_menu"),
        )
    else:
        await call.message.edit_text(
            f"📁 <b>Мои папки</b> ({len(folders)})\n\nВыберите папку:",
            parse_mode="HTML",
            reply_markup=folder_list_kb(folders),
        )
    await call.answer()


@router.callback_query(F.data.startswith("my_folders_page:"))
async def cb_my_folders_page(call: CallbackQuery):
    page = int(call.data.split(":")[1])
    folders = db.get_user_folders(call.from_user.id)
    await call.message.edit_text(
        f"📁 <b>Мои папки</b> ({len(folders)})\n\nВыберите папку:",
        parse_mode="HTML",
        reply_markup=folder_list_kb(folders, page=page),
    )
    await call.answer()


# ─── Create Folder ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "create_folder")
async def cb_create_folder(call: CallbackQuery, state: FSMContext):
    await state.set_state(FolderStates.waiting_name)
    await call.message.edit_text(
        "📁 <b>Создание папки</b>\n\nВведите название папки:",
        parse_mode="HTML",
        reply_markup=cancel_kb("main_menu"),
    )
    await call.answer()


@router.message(FolderStates.waiting_name)
async def msg_folder_name(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("❗ Название не может быть пустым. Введите название:")
        return
    folder_id = db.create_folder(title, message.from_user.id)
    await state.clear()
    folder = db.get_folder(folder_id)
    await message.answer(
        f"✅ Папка <b>{escape_html(title)}</b> создана!\n\n"
        f"Доступ: {format_access(folder['access'])}\n\n"
        "Теперь вы можете добавлять статьи и группы:",
        parse_mode="HTML",
        reply_markup=folder_view_kb(folder_id, is_owner=True, access=folder['access']),
    )


# ─── View Folder ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("folder:"))
async def cb_folder_view(call: CallbackQuery, state: FSMContext):
    folder_id = int(call.data.split(":")[1])
    folder = db.get_folder(folder_id)
    if not folder:
        await call.answer("Папка не найдена!", show_alert=True)
        return

    user = db.get_user(call.from_user.id)
    is_owner = user and folder['owner_id'] == user['id']
    is_editor = db.is_editor('folder', folder_id, call.from_user.id)

    if not is_owner and not is_editor:
        if folder['access'] == 'private':
            await call.answer("🔒 Доступ закрыт.", show_alert=True)
            return

    groups = db.get_folder_groups(folder_id)
    articles = db.get_folder_articles(folder_id)

    text = (
        f"📁 <b>{escape_html(folder['title'])}</b>\n\n"
        f"🔑 Доступ: {format_access(folder['access'])}\n"
        f"📂 Групп: {len(groups)}\n"
        f"📜 Статей: {len(articles)}"
    )
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=folder_view_kb(folder_id, is_owner=is_owner or is_editor, access=folder['access']),
    )
    await call.answer()


# ─── Folder Groups & Articles ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("folder_groups:"))
async def cb_folder_groups(call: CallbackQuery):
    folder_id = int(call.data.split(":")[1])
    groups = db.get_folder_groups(folder_id)
    folder = db.get_folder(folder_id)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if groups:
        for g in groups:
            builder.button(text=f"📂 {g['title']}", callback_data=f"group:{g['id']}")
        builder.adjust(1)
    builder.row(
        __import__('aiogram').types.InlineKeyboardButton(
            text="◀️ Назад", callback_data=f"folder:{folder_id}"
        )
    )

    text = f"📂 <b>Группы в «{escape_html(folder['title'])}»</b>\n\n"
    text += f"Найдено: {len(groups)}" if groups else "Групп пока нет."

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("folder_articles:"))
async def cb_folder_articles(call: CallbackQuery):
    folder_id = int(call.data.split(":")[1])
    articles = db.get_folder_articles(folder_id)
    folder = db.get_folder(folder_id)

    from keyboards import article_list_kb
    text = f"📜 <b>Статьи в «{escape_html(folder['title'])}»</b>\n\n"
    if articles:
        await call.message.edit_text(
            text + f"Найдено: {len(articles)}",
            parse_mode="HTML",
            reply_markup=article_list_kb(articles, back_cb=f"folder:{folder_id}"),
        )
    else:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="◀️ Назад", callback_data=f"folder:{folder_id}")
        await call.message.edit_text(
            text + "Статей пока нет.",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
    await call.answer()


# ─── Folder Settings ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("folder_settings:"))
async def cb_folder_settings(call: CallbackQuery):
    folder_id = int(call.data.split(":")[1])
    folder = db.get_folder(folder_id)
    if not folder:
        await call.answer("Не найдено", show_alert=True)
        return
    user = db.get_user(call.from_user.id)
    if not user or folder['owner_id'] != user['id']:
        await call.answer("Только владелец может управлять настройками.", show_alert=True)
        return
    await call.message.edit_text(
        f"⚙️ <b>Настройки папки «{escape_html(folder['title'])}»</b>\n\n"
        f"Текущий доступ: {format_access(folder['access'])}",
        parse_mode="HTML",
        reply_markup=folder_settings_kb(folder_id, folder['access']),
    )
    await call.answer()


@router.callback_query(F.data.startswith("folder_access:"))
async def cb_folder_access(call: CallbackQuery):
    _, folder_id_str, access = call.data.split(":")
    folder_id = int(folder_id_str)
    folder = db.get_folder(folder_id)
    user = db.get_user(call.from_user.id)
    if not user or folder['owner_id'] != user['id']:
        await call.answer("Нет прав", show_alert=True)
        return

    if access == 'link' and not folder['invite_token']:
        db.update_folder(folder_id, invite_token=generate_token())
    db.update_folder(folder_id, access=access)
    folder = db.get_folder(folder_id)
    await call.message.edit_text(
        f"⚙️ <b>Настройки папки «{escape_html(folder['title'])}»</b>\n\n"
        f"Доступ изменён: {format_access(access)}",
        parse_mode="HTML",
        reply_markup=folder_settings_kb(folder_id, access),
    )
    await call.answer(f"Доступ изменён на: {format_access(access)}")


@router.callback_query(F.data.startswith("get_folder_link:"))
async def cb_get_folder_link(call: CallbackQuery):
    folder_id = int(call.data.split(":")[1])
    folder = db.get_folder(folder_id)
    if not folder or not folder['invite_token']:
        await call.answer("Сначала включите доступ по ссылке.", show_alert=True)
        return
    bot = call.bot
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=folder_{folder['invite_token']}"
    await call.answer(f"Ссылка: {link}", show_alert=True)


@router.callback_query(F.data.startswith("rename_folder:"))
async def cb_rename_folder_start(call: CallbackQuery, state: FSMContext):
    folder_id = int(call.data.split(":")[1])
    await state.set_state(FolderStates.renaming)
    await state.update_data(folder_id=folder_id)
    await call.message.edit_text(
        "✏️ Введите новое название папки:",
        reply_markup=cancel_kb(f"folder_settings:{folder_id}"),
    )
    await call.answer()


@router.message(FolderStates.renaming)
async def msg_rename_folder(message: Message, state: FSMContext):
    data = await state.get_data()
    folder_id = data['folder_id']
    title = message.text.strip()
    if not title:
        await message.answer("❗ Название не может быть пустым:")
        return
    db.update_folder(folder_id, title=title)
    await state.clear()
    folder = db.get_folder(folder_id)
    await message.answer(
        f"✅ Папка переименована в <b>{escape_html(title)}</b>",
        parse_mode="HTML",
        reply_markup=folder_settings_kb(folder_id, folder['access']),
    )


@router.callback_query(F.data.startswith("delete_folder:"))
async def cb_delete_folder_confirm(call: CallbackQuery):
    folder_id = int(call.data.split(":")[1])
    folder = db.get_folder(folder_id)
    user = db.get_user(call.from_user.id)
    if not user or folder['owner_id'] != user['id']:
        await call.answer("Только владелец может удалить папку.", show_alert=True)
        return
    await call.message.edit_text(
        f"🗑 Удалить папку <b>{escape_html(folder['title'])}</b>?\n\n"
        "⚠️ Все группы и статьи внутри также будут удалены.",
        parse_mode="HTML",
        reply_markup=confirm_kb(f"delete_folder_yes:{folder_id}", f"folder_settings:{folder_id}"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("delete_folder_yes:"))
async def cb_delete_folder_yes(call: CallbackQuery):
    folder_id = int(call.data.split(":")[1])
    folder = db.get_folder(folder_id)
    user = db.get_user(call.from_user.id)
    if not user or folder['owner_id'] != user['id']:
        await call.answer("Нет прав", show_alert=True)
        return
    db.delete_folder(folder_id)
    await call.message.edit_text(
        "✅ Папка удалена.",
        reply_markup=main_menu_kb(),
    )
    await call.answer()
