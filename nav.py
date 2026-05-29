"""
Shared navigation render functions.
All "back" handlers use these instead of calling other handlers directly.
"""
from aiogram.types import CallbackQuery, Message

import database as db
from utils import escape_html, format_access


async def show_folder(call: CallbackQuery, folder_id: int):
    """Render the folder view into call.message."""
    from keyboards import folder_view_kb
    folder = db.get_folder(folder_id)
    if not folder:
        await call.message.edit_text("❗ Папка не найдена.")
        await call.answer()
        return

    user = db.get_user(call.from_user.id)
    is_owner = bool(user and folder['owner_id'] == user['id'])
    is_editor = db.is_editor('folder', folder_id, call.from_user.id)

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


async def show_group(call: CallbackQuery, group_id: int):
    """Render the group view into call.message."""
    from keyboards import group_view_kb
    group = db.get_group(group_id)
    if not group:
        await call.message.edit_text("❗ Группа не найдена.")
        await call.answer()
        return

    user = db.get_user(call.from_user.id)
    is_owner = bool(user and group['owner_id'] == user['id'])
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


async def show_my_folders(call: CallbackQuery):
    """Render the user's folder list into call.message."""
    from keyboards import folder_list_kb
    folders = db.get_user_folders(call.from_user.id)
    if not folders:
        from keyboards import cancel_kb
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


async def show_my_articles(call: CallbackQuery):
    """Render the user's article list into call.message."""
    from keyboards import article_list_kb, main_menu_kb
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    articles = db.get_user_articles(call.from_user.id)
    if not articles:
        builder = InlineKeyboardBuilder()
        builder.button(text="◀️ Главное меню", callback_data="main_menu")
        await call.message.edit_text(
            "📄 У вас пока нет статей.",
            reply_markup=builder.as_markup(),
        )
    else:
        await call.message.edit_text(
            f"📄 <b>Мои статьи</b> ({len(articles)})\n\nВыберите статью:",
            parse_mode="HTML",
            reply_markup=article_list_kb(articles),
        )
    await call.answer()


async def show_folder_settings(call: CallbackQuery, folder_id: int):
    """Render folder settings view."""
    from keyboards import folder_settings_kb
    folder = db.get_folder(folder_id)
    if not folder:
        await call.answer("Папка не найдена.", show_alert=True)
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


async def show_group_settings(call: CallbackQuery, group_id: int):
    """Render group settings view."""
    from keyboards import group_settings_kb
    group = db.get_group(group_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    await call.message.edit_text(
        f"⚙️ <b>Настройки группы «{escape_html(group['title'])}»</b>",
        parse_mode="HTML",
        reply_markup=group_settings_kb(group_id),
    )
    await call.answer()


async def show_article_settings(call: CallbackQuery, article_id: int):
    """Render article settings view."""
    from keyboards import article_settings_kb
    article = db.get_article(article_id)
    if not article:
        await call.answer("Статья не найдена.", show_alert=True)
        return
    await call.message.edit_text(
        f"⚙️ <b>Настройки статьи «{escape_html(article['title'])}»</b>\n\n"
        f"Текущий доступ: {format_access(article['access'])}",
        parse_mode="HTML",
        reply_markup=article_settings_kb(article_id, article['access']),
    )
    await call.answer()
