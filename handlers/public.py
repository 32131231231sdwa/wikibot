from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

import database as db
from keyboards import public_feed_kb, main_menu_kb
from utils import escape_html, format_access

router = Router()

PAGE_SIZE = 10


@router.callback_query(F.data.startswith("public:"))
async def cb_public_feed(call: CallbackQuery, state: FSMContext):
    await state.clear()
    parts = call.data.split(":")
    sort = parts[1]
    offset = int(parts[2])

    articles = db.get_public_articles(sort=sort, limit=PAGE_SIZE + 1, offset=offset)
    folders = db.get_public_folders(sort=sort, limit=5, offset=0) if offset == 0 else []

    has_more = len(articles) > PAGE_SIZE
    articles = articles[:PAGE_SIZE]

    sort_label = "Новое 🆕" if sort == 'new' else "Залайканное ❤️"
    text_parts = [f"🌍 <b>Выложенное — {sort_label}</b>\n"]

    builder = InlineKeyboardBuilder()

    if offset == 0 and folders:
        text_parts.append(f"\n📁 <b>Публичные папки:</b>")
        for f in folders:
            text_parts.append(f"• {escape_html(f['title'])}")
            builder.button(text=f"📁 {f['title']}", callback_data=f"folder:{f['id']}")

    if articles:
        text_parts.append(f"\n📄 <b>Статьи:</b>")
        for a in articles:
            owner = a['owner_name'] or "?"
            text_parts.append(f"• {escape_html(a['title'])} — {escape_html(owner)} ❤️{a['like_count']}")
            builder.button(text=f"📄 {a['title']} ❤️{a['like_count']}", callback_data=f"article:{a['id']}")
    else:
        text_parts.append("\nПубличных статей пока нет.")

    builder.adjust(1)

    # Nav buttons
    sort_btns = []
    sort_btns.append(InlineKeyboardButton(
        text=("✅ Новое" if sort == 'new' else "Новое"),
        callback_data="public:new:0"
    ))
    sort_btns.append(InlineKeyboardButton(
        text=("✅ Залайканное" if sort == 'liked' else "Залайканное"),
        callback_data="public:liked:0"
    ))
    builder.row(*sort_btns)

    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"public:{sort}:{max(0,offset-PAGE_SIZE)}"))
    if has_more:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"public:{sort}:{offset+PAGE_SIZE}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    await call.message.edit_text(
        "\n".join(text_parts),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await call.answer()


@router.callback_query(F.data == "my_likes")
async def cb_my_likes(call: CallbackQuery):
    articles = db.get_user_liked_articles(call.from_user.id)
    builder = InlineKeyboardBuilder()
    if articles:
        for a in articles:
            builder.button(text=f"❤️ {a['title']}", callback_data=f"article:{a['id']}")
        builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Профиль", callback_data="profile"))

    text = f"❤️ <b>Мои лайки</b> ({len(articles)})\n\n"
    text += "Статьи, которым вы поставили лайк:" if articles else "Вы ещё не ставили лайки."

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await call.answer()


@router.callback_query(F.data == "profile")
async def cb_profile(call: CallbackQuery):
    from keyboards import profile_kb
    user = db.get_user(call.from_user.id)
    if not user:
        await call.answer("Профиль не найден.", show_alert=True)
        return

    articles = db.get_user_articles(call.from_user.id)
    folders = db.get_user_folders(call.from_user.id)
    liked = db.get_user_liked_articles(call.from_user.id)

    name = f"@{user['username']}" if user['username'] else user['first_name']
    text = (
        f"👤 <b>Профиль: {escape_html(name)}</b>\n\n"
        f"📁 Папок: {len(folders)}\n"
        f"📄 Статей: {len(articles)}\n"
        f"❤️ Лайков поставлено: {len(liked)}\n\n"
        f"Дата регистрации: {user['created_at'][:10]}"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=profile_kb())
    await call.answer()
