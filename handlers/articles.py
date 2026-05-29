from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

import database as db
from keyboards import (
    article_view_kb, article_edit_kb, article_settings_kb,
    article_blocks_editor_kb, cancel_kb, confirm_kb, blocks_list_kb, main_menu_kb
)
from utils import generate_token, format_access, escape_html, split_text
import nav

router = Router()

CHUNK = 4000


class ArticleStates(StatesGroup):
    waiting_title = State()
    waiting_text = State()
    waiting_photo = State()
    waiting_link_text = State()
    waiting_link_url = State()
    renaming = State()
    waiting_comment = State()
    waiting_search = State()
    editing_block_text = State()  # editing an existing text/link block


def _can_edit(article, tg_id: int) -> bool:
    user = db.get_user(tg_id)
    if not user:
        return False
    if article['owner_id'] == user['id']:
        return True
    return db.is_editor('article', article['id'], tg_id)


def _can_view(article, tg_id: int) -> bool:
    user = db.get_user(tg_id)
    if article['access'] == 'public':
        return True
    if article['access'] == 'link':
        return True
    if not user:
        return False
    if article['owner_id'] == user['id']:
        return True
    return db.is_editor('article', article['id'], tg_id)


def _article_back_cb(article) -> str:
    if article['group_id']:
        return f"group:{article['group_id']}"
    if article['folder_id']:
        return f"folder:{article['folder_id']}"
    return "my_articles"


# ─── Create Article ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "create_article_solo")
async def cb_create_article_solo(call: CallbackQuery, state: FSMContext):
    await state.set_state(ArticleStates.waiting_title)
    await state.update_data(folder_id=None, group_id=None)
    await call.message.edit_text(
        "📄 <b>Создание статьи</b>\n\nВведите название статьи:",
        parse_mode="HTML",
        reply_markup=cancel_kb("main_menu"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("create_article:"))
async def cb_create_article_in(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    parent_type = parts[1]
    parent_id = int(parts[2])
    folder_id = parent_id if parent_type == 'folder' else None
    group_id = parent_id if parent_type == 'group' else None
    back = f"folder:{parent_id}" if parent_type == 'folder' else f"group:{parent_id}"
    await state.set_state(ArticleStates.waiting_title)
    await state.update_data(folder_id=folder_id, group_id=group_id, back=back)
    await call.message.edit_text(
        "📄 <b>Создание статьи</b>\n\nВведите название статьи:",
        parse_mode="HTML",
        reply_markup=cancel_kb(back),
    )
    await call.answer()


@router.message(ArticleStates.waiting_title)
async def msg_article_title(message: Message, state: FSMContext):
    title = message.text.strip() if message.text else ""
    if not title:
        await message.answer("❗ Название не может быть пустым:")
        return
    data = await state.get_data()
    article_id = db.create_article(
        title=title,
        owner_tg_id=message.from_user.id,
        folder_id=data.get('folder_id'),
        group_id=data.get('group_id'),
    )
    await state.clear()
    await message.answer(
        f"✅ Статья <b>{escape_html(title)}</b> создана!\n\n"
        "Теперь добавьте содержимое через кнопки редактора:",
        parse_mode="HTML",
        reply_markup=article_edit_kb(article_id),
    )


# ─── View Article ─────────────────────────────────────────────────────────────

async def send_article(message_or_call, article_id: int, tg_id: int, edit=True):
    article = db.get_article(article_id)
    if not article:
        if edit:
            await message_or_call.message.edit_text("❗ Статья не найдена.", reply_markup=main_menu_kb())
        else:
            await message_or_call.answer("❗ Статья не найдена.", reply_markup=main_menu_kb())
        return

    if not _can_view(article, tg_id):
        txt = "🔒 У вас нет доступа к этой статье."
        if edit:
            await message_or_call.message.edit_text(txt, reply_markup=main_menu_kb())
        else:
            await message_or_call.answer(txt, reply_markup=main_menu_kb())
        return

    blocks = db.get_article_blocks(article_id)
    can_edit = _can_edit(article, tg_id)
    liked = db.has_liked(article_id, tg_id)
    is_draft = bool(article['is_draft'])
    kb = article_view_kb(article_id, can_edit, liked, article['access'], is_draft)

    # Build content
    header = f"📄 <b>{escape_html(article['title'])}</b>"
    if is_draft:
        header += " <i>[черновик]</i>"
    header += f"\n❤️ {article['like_count']}"
    header += f"\n🔑 {format_access(article['access'])}\n\n"

    # Collect text and photo blocks
    text_parts = [header]
    photo_blocks = []

    for b in blocks:
        if b['block_type'] == 'text':
            text_parts.append(b['content'] or "")
        elif b['block_type'] == 'photo':
            photo_blocks.append(b['file_id'])
        elif b['block_type'] == 'link':
            text_parts.append(b['content'] or "")

    full_text = "\n\n".join(text_parts)
    chunks = split_text(full_text, CHUNK)

    target = message_or_call if not edit else None
    msg_obj = message_or_call.message if edit else message_or_call

    # Send first chunk (edit or send)
    if edit:
        try:
            await msg_obj.edit_text(chunks[0], parse_mode="HTML", reply_markup=kb if len(chunks) == 1 and not photo_blocks else None)
        except Exception:
            await msg_obj.answer(chunks[0], parse_mode="HTML")
    else:
        await msg_obj.answer(chunks[0], parse_mode="HTML")

    # Extra text chunks
    for chunk in chunks[1:]:
        await msg_obj.answer(chunk, parse_mode="HTML")

    # Photos
    for i, fid in enumerate(photo_blocks):
        try:
            await msg_obj.answer_photo(fid)
        except Exception:
            await msg_obj.answer(f"[Фото #{i+1} недоступно]")

    # Final keyboard
    if len(chunks) > 1 or photo_blocks:
        await msg_obj.answer("⬇️ Управление статьёй:", reply_markup=kb)


@router.callback_query(F.data.startswith("article:"))
async def cb_article_view(call: CallbackQuery, state: FSMContext):
    await state.clear()
    article_id = int(call.data.split(":")[1])
    await send_article(call, article_id, call.from_user.id, edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("article_back:"))
async def cb_article_back(call: CallbackQuery):
    article_id = int(call.data.split(":")[1])
    article = db.get_article(article_id)
    if not article:
        await nav.show_my_articles(call)
        return
    back_cb = _article_back_cb(article)
    if back_cb.startswith("group:"):
        gid = int(back_cb.split(":")[1])
        await nav.show_group(call, gid)
    elif back_cb.startswith("folder:"):
        fid = int(back_cb.split(":")[1])
        await nav.show_folder(call, fid)
    else:
        await nav.show_my_articles(call)


# ─── Edit Article ─────────────────────────────────────────────────────────────

async def _show_editor(call: CallbackQuery, article_id: int):
    """Render the editor view — blocks list + actions."""
    article = db.get_article(article_id)
    if not article or not _can_edit(article, call.from_user.id):
        await call.answer("Нет прав для редактирования.", show_alert=True)
        return
    blocks = db.get_article_blocks(article_id)
    status = "📝 Черновик" if article['is_draft'] else "✅ Опубликована"
    header = (
        f"✏️ <b>Редактор: {escape_html(article['title'])}</b>\n"
        f"Статус: {status} · Блоков: {len(blocks)}\n"
    )
    if blocks:
        lines = [header, ""]
        for i, b in enumerate(blocks, 1):
            if b['block_type'] == 'text':
                preview = (b['content'] or '').replace('\n', ' ')[:60]
                lines.append(f"<b>{i}.</b> 📝 {escape_html(preview)}{'…' if len(b['content'] or '') > 60 else ''}")
            elif b['block_type'] == 'photo':
                lines.append(f"<b>{i}.</b> 🖼 Фото")
            elif b['block_type'] == 'link':
                preview = (b['content'] or '')[:50]
                lines.append(f"<b>{i}.</b> 🔗 Ссылка")
        text = "\n".join(lines)
        kb = article_blocks_editor_kb(article_id, blocks)
    else:
        text = header + "\n<i>Статья пока пустая. Добавьте первый блок:</i>"
        kb = article_edit_kb(article_id)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("edit_article:"))
async def cb_edit_article(call: CallbackQuery, state: FSMContext):
    await state.clear()
    article_id = int(call.data.split(":")[1])
    await _show_editor(call, article_id)


# ─── Add Text Block ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("add_text:"))
async def cb_add_text_start(call: CallbackQuery, state: FSMContext):
    article_id = int(call.data.split(":")[1])
    await state.set_state(ArticleStates.waiting_text)
    await state.update_data(article_id=article_id)
    await call.message.edit_text(
        "📝 Введите текст блока.\n\n"
        "Поддерживается <b>жирный</b>, <i>курсив</i>, <u>подчёркивание</u>, <code>код</code>.\n"
        "Используйте HTML-теги: &lt;b&gt;, &lt;i&gt;, &lt;u&gt;, &lt;code&gt;, &lt;a href=\"...\"&gt;\n\n"
        "Текст любой длины — автоматически разобьётся на сообщения.",
        parse_mode="HTML",
        reply_markup=cancel_kb(f"edit_article:{article_id}"),
    )
    await call.answer()


@router.message(ArticleStates.waiting_text)
async def msg_add_text(message: Message, state: FSMContext):
    data = await state.get_data()
    article_id = data['article_id']
    text = message.html_text or message.text or ""
    if not text.strip():
        await message.answer("❗ Текст не может быть пустым:")
        return
    db.add_block(article_id, 'text', content=text)
    await state.clear()
    blocks = db.get_article_blocks(article_id)
    article = db.get_article(article_id)
    status = "📝 Черновик" if article['is_draft'] else "✅ Опубликована"
    header = f"✏️ <b>Редактор: {escape_html(article['title'])}</b>\n Статус: {status} · Блоков: {len(blocks)}\n"
    lines = [header, "✅ Текстовый блок добавлен!\n"]
    for i, b in enumerate(blocks, 1):
        if b['block_type'] == 'text':
            preview = (b['content'] or '').replace('\n', ' ')[:60]
            lines.append(f"<b>{i}.</b> 📝 {escape_html(preview)}{'…' if len(b['content'] or '') > 60 else ''}")
        elif b['block_type'] == 'photo':
            lines.append(f"<b>{i}.</b> 🖼 Фото")
        elif b['block_type'] == 'link':
            lines.append(f"<b>{i}.</b> 🔗 Ссылка")
    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=article_blocks_editor_kb(article_id, blocks),
    )


# ─── Add Photo Block ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("add_photo:"))
async def cb_add_photo_start(call: CallbackQuery, state: FSMContext):
    article_id = int(call.data.split(":")[1])
    await state.set_state(ArticleStates.waiting_photo)
    await state.update_data(article_id=article_id)
    await call.message.edit_text(
        "🖼 Отправьте фото для добавления в статью:",
        reply_markup=cancel_kb(f"edit_article:{article_id}"),
    )
    await call.answer()


@router.message(ArticleStates.waiting_photo, F.photo)
async def msg_add_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    article_id = data['article_id']
    file_id = message.photo[-1].file_id
    db.add_block(article_id, 'photo', file_id=file_id)
    await state.clear()
    await message.answer(
        "✅ Фото добавлено в статью!",
        reply_markup=article_edit_kb(article_id),
    )


@router.message(ArticleStates.waiting_photo)
async def msg_add_photo_wrong(message: Message, state: FSMContext):
    await message.answer("❗ Пожалуйста, отправьте фото (не файл, не текст).")


# ─── Add Link Block ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("add_link:"))
async def cb_add_link_start(call: CallbackQuery, state: FSMContext):
    article_id = int(call.data.split(":")[1])
    await state.set_state(ArticleStates.waiting_link_text)
    await state.update_data(article_id=article_id)
    await call.message.edit_text(
        "🔗 Введите текст ссылки и URL в формате:\n\n"
        "<code>Текст|https://example.com</code>\n\n"
        "Или просто URL:",
        parse_mode="HTML",
        reply_markup=cancel_kb(f"edit_article:{article_id}"),
    )
    await call.answer()


@router.message(ArticleStates.waiting_link_text)
async def msg_add_link(message: Message, state: FSMContext):
    data = await state.get_data()
    article_id = data['article_id']
    text = (message.text or "").strip()
    if '|' in text:
        label, url = text.split('|', 1)
        content = f'<a href="{url.strip()}">{escape_html(label.strip())}</a>'
    else:
        content = f'<a href="{text}">{text}</a>'
    db.add_block(article_id, 'link', content=content)
    await state.clear()
    await message.answer(
        "✅ Ссылка добавлена!",
        reply_markup=article_edit_kb(article_id),
    )


# ─── Edit Existing Block ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("block_preview:"))
async def cb_block_preview(call: CallbackQuery):
    """Tapping the block label in the editor — just acknowledge, no action."""
    await call.answer("Нажмите ✏️ чтобы изменить или 🗑 чтобы удалить.")


@router.callback_query(F.data.startswith("edit_block:"))
async def cb_edit_block_start(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    block_id = int(parts[1])
    article_id = int(parts[2])

    # Load block content to show current text
    import database as db_mod
    with db_mod.db_conn() as conn:
        block = conn.execute("SELECT * FROM article_blocks WHERE id=?", (block_id,)).fetchone()

    if not block:
        await call.answer("Блок не найден.", show_alert=True)
        return
    if block['block_type'] not in ('text', 'link'):
        await call.answer("Фото нельзя редактировать текстом. Удалите и добавьте новое.", show_alert=True)
        return

    current = block['content'] or ""
    await state.set_state(ArticleStates.editing_block_text)
    await state.update_data(block_id=block_id, article_id=article_id, block_type=block['block_type'])

    hint = (
        "📝 <b>Редактирование текстового блока</b>\n\n"
        "Текущее содержимое:\n"
        f"<blockquote>{escape_html(current[:300])}{'…' if len(current) > 300 else ''}</blockquote>\n\n"
        "Отправьте новый текст — он полностью заменит старый.\n"
        "Поддерживается <b>жирный</b>, <i>курсив</i>, <u>подчёркивание</u>, <code>код</code>, ссылки."
    ) if block['block_type'] == 'text' else (
        "🔗 <b>Редактирование ссылки</b>\n\n"
        f"Текущая: {current[:200]}\n\n"
        "Введите новое значение в формате <code>Текст|https://url</code> или просто URL:"
    )

    await call.message.edit_text(hint, parse_mode="HTML", reply_markup=cancel_kb(f"edit_article:{article_id}"))
    await call.answer()


@router.message(ArticleStates.editing_block_text)
async def msg_edit_block_text(message: Message, state: FSMContext):
    data = await state.get_data()
    block_id = data['block_id']
    article_id = data['article_id']
    block_type = data.get('block_type', 'text')

    if block_type == 'text':
        new_content = message.html_text or message.text or ""
    else:
        raw = (message.text or "").strip()
        if '|' in raw:
            label, url = raw.split('|', 1)
            new_content = f'<a href="{url.strip()}">{escape_html(label.strip())}</a>'
        else:
            new_content = f'<a href="{raw}">{raw}</a>'

    if not new_content.strip():
        await message.answer("❗ Текст не может быть пустым:")
        return

    with db.db_conn() as conn:
        conn.execute("UPDATE article_blocks SET content=? WHERE id=?", (new_content, block_id))
        conn.execute("UPDATE articles SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (article_id,))

    await state.clear()
    blocks = db.get_article_blocks(article_id)
    article = db.get_article(article_id)
    status = "📝 Черновик" if article['is_draft'] else "✅ Опубликована"
    header = f"✏️ <b>Редактор: {escape_html(article['title'])}</b>\nСтатус: {status} · Блоков: {len(blocks)}\n"
    lines = [header, "✅ Блок обновлён!\n"]
    for i, b in enumerate(blocks, 1):
        if b['block_type'] == 'text':
            preview = (b['content'] or '').replace('\n', ' ')[:60]
            lines.append(f"<b>{i}.</b> 📝 {escape_html(preview)}{'…' if len(b['content'] or '') > 60 else ''}")
        elif b['block_type'] == 'photo':
            lines.append(f"<b>{i}.</b> 🖼 Фото")
        elif b['block_type'] == 'link':
            lines.append(f"<b>{i}.</b> 🔗 Ссылка")
    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=article_blocks_editor_kb(article_id, blocks),
    )


# ─── Delete Block ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("delete_block:"))
async def cb_delete_block_list(call: CallbackQuery):
    """Legacy entry — now blocks are deleted directly from the editor view."""
    article_id = int(call.data.split(":")[1])
    await _show_editor(call, article_id)


@router.callback_query(F.data.startswith("confirm_del_block:"))
async def cb_confirm_del_block(call: CallbackQuery):
    parts = call.data.split(":")
    block_id = int(parts[1])
    article_id = int(parts[2])
    db.delete_block(block_id)
    await call.answer("✅ Блок удалён.")
    await _show_editor(call, article_id)


# ─── Rename Article ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("rename_article:"))
async def cb_rename_article_start(call: CallbackQuery, state: FSMContext):
    article_id = int(call.data.split(":")[1])
    await state.set_state(ArticleStates.renaming)
    await state.update_data(article_id=article_id)
    await call.message.edit_text(
        "✏️ Введите новое название статьи:",
        reply_markup=cancel_kb(f"edit_article:{article_id}"),
    )
    await call.answer()


@router.message(ArticleStates.renaming)
async def msg_rename_article(message: Message, state: FSMContext):
    data = await state.get_data()
    article_id = data['article_id']
    title = message.text.strip()
    if not title:
        await message.answer("❗ Название не может быть пустым:")
        return
    db.update_article(article_id, title=title)
    await state.clear()
    await message.answer(
        f"✅ Статья переименована в <b>{escape_html(title)}</b>",
        parse_mode="HTML",
        reply_markup=article_edit_kb(article_id),
    )


# ─── Publish / Draft ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("publish_article:"))
async def cb_publish_article(call: CallbackQuery):
    article_id = int(call.data.split(":")[1])
    article = db.get_article(article_id)
    if not article or not _can_edit(article, call.from_user.id):
        await call.answer("Нет прав.", show_alert=True)
        return
    new_draft = 0 if article['is_draft'] else 1
    db.update_article(article_id, is_draft=new_draft)
    status = "опубликована ✅" if new_draft == 0 else "переведена в черновик 📝"
    await call.answer(f"Статья {status}", show_alert=True)
    article = db.get_article(article_id)
    await call.message.edit_reply_markup(
        reply_markup=article_view_kb(
            article_id, True, db.has_liked(article_id, call.from_user.id),
            article['access'], bool(article['is_draft'])
        )
    )


# ─── Article Settings ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("article_settings:"))
async def cb_article_settings(call: CallbackQuery):
    article_id = int(call.data.split(":")[1])
    article = db.get_article(article_id)
    if not article or not _can_edit(article, call.from_user.id):
        await call.answer("Нет прав.", show_alert=True)
        return
    await call.message.edit_text(
        f"⚙️ <b>Настройки статьи «{escape_html(article['title'])}»</b>\n\n"
        f"Текущий доступ: {format_access(article['access'])}",
        parse_mode="HTML",
        reply_markup=article_settings_kb(article_id, article['access']),
    )
    await call.answer()


@router.callback_query(F.data.startswith("article_access:"))
async def cb_article_access(call: CallbackQuery):
    parts = call.data.split(":")
    article_id = int(parts[1])
    access = parts[2]
    article = db.get_article(article_id)
    if not article or not _can_edit(article, call.from_user.id):
        await call.answer("Нет прав.", show_alert=True)
        return
    if access == 'link' and not article['invite_token']:
        db.update_article(article_id, invite_token=generate_token())
    db.update_article(article_id, access=access)
    article = db.get_article(article_id)
    await call.message.edit_text(
        f"⚙️ <b>Настройки статьи «{escape_html(article['title'])}»</b>\n\n"
        f"Доступ изменён: {format_access(access)}",
        parse_mode="HTML",
        reply_markup=article_settings_kb(article_id, access),
    )
    await call.answer(f"Доступ: {format_access(access)}")


@router.callback_query(F.data.startswith("get_article_link:"))
async def cb_get_article_link(call: CallbackQuery):
    article_id = int(call.data.split(":")[1])
    article = db.get_article(article_id)
    if not article or not article['invite_token']:
        await call.answer("Сначала включите доступ по ссылке.", show_alert=True)
        return
    me = await call.bot.get_me()
    link = f"https://t.me/{me.username}?start=article_{article['invite_token']}"
    await call.answer(f"Ссылка: {link}", show_alert=True)


@router.callback_query(F.data.startswith("share_article:"))
async def cb_share_article(call: CallbackQuery):
    article_id = int(call.data.split(":")[1])
    article = db.get_article(article_id)
    if not article:
        await call.answer("Не найдено.", show_alert=True)
        return
    me = await call.bot.get_me()
    if article['access'] == 'link' and article['invite_token']:
        link = f"https://t.me/{me.username}?start=article_{article['invite_token']}"
    elif article['access'] == 'public':
        link = f"https://t.me/{me.username}?start=article_id_{article_id}"
    else:
        link = "🔒 Статья приватная. Измените доступ для публикации ссылки."
    await call.answer(link, show_alert=True)


@router.callback_query(F.data.startswith("delete_article:"))
async def cb_delete_article_confirm(call: CallbackQuery):
    article_id = int(call.data.split(":")[1])
    article = db.get_article(article_id)
    user = db.get_user(call.from_user.id)
    if not user or not article or article['owner_id'] != user['id']:
        await call.answer("Только владелец может удалить статью.", show_alert=True)
        return
    await call.message.edit_text(
        f"🗑 Удалить статью <b>{escape_html(article['title'])}</b>?",
        parse_mode="HTML",
        reply_markup=confirm_kb(f"delete_article_yes:{article_id}", f"article_settings:{article_id}"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("delete_article_yes:"))
async def cb_delete_article_yes(call: CallbackQuery):
    article_id = int(call.data.split(":")[1])
    article = db.get_article(article_id)
    user = db.get_user(call.from_user.id)
    if not user or not article or article['owner_id'] != user['id']:
        await call.answer("Нет прав.", show_alert=True)
        return
    back = _article_back_cb(article)
    db.delete_article(article_id)
    await call.message.edit_text("✅ Статья удалена.", reply_markup=main_menu_kb())
    await call.answer()


# ─── My Articles ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_articles")
async def cb_my_articles(call: CallbackQuery, state: FSMContext):
    await state.clear()
    articles = db.get_user_articles(call.from_user.id)
    from keyboards import article_list_kb
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


@router.callback_query(F.data.startswith("article_page:"))
async def cb_article_page(call: CallbackQuery):
    parts = call.data.split(":")
    back_cb = parts[1]
    page = int(parts[2])
    if back_cb == "my_articles" or back_cb == "main_menu":
        articles = db.get_user_articles(call.from_user.id)
    elif back_cb.startswith("folder:"):
        folder_id = int(back_cb.split(":")[1])
        articles = db.get_folder_articles(folder_id)
    elif back_cb.startswith("group:"):
        group_id = int(back_cb.split(":")[1])
        articles = db.get_group_articles(group_id)
    else:
        articles = []
    from keyboards import article_list_kb
    await call.message.edit_reply_markup(
        reply_markup=article_list_kb(articles, back_cb=back_cb, page=page)
    )
    await call.answer()


# ─── Like ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("like:"))
async def cb_like(call: CallbackQuery):
    article_id = int(call.data.split(":")[1])
    article = db.get_article(article_id)
    if not article:
        await call.answer("Не найдено.", show_alert=True)
        return
    if not _can_view(article, call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return
    liked = db.toggle_like(article_id, call.from_user.id)
    article = db.get_article(article_id)
    msg = "❤️ Лайк поставлен!" if liked else "💔 Лайк убран."
    await call.answer(msg)
    try:
        await call.message.edit_reply_markup(
            reply_markup=article_view_kb(
                article_id,
                _can_edit(article, call.from_user.id),
                liked,
                article['access'],
                bool(article['is_draft'])
            )
        )
    except Exception:
        pass


# ─── Comments ─────────────────────────────────────────────────────────────────

async def _render_comments(call: CallbackQuery, article_id: int, offset: int):
    """Shared helper — renders the comments view into call.message."""
    from keyboards import comments_kb
    article = db.get_article(article_id)
    if not article:
        await call.answer("Статья не найдена.", show_alert=True)
        return

    comments = db.get_comments(article_id, limit=10, offset=offset)
    total_next = db.get_comments(article_id, limit=1, offset=offset + 10)

    user = db.get_user(call.from_user.id)
    deletable = []
    if user:
        for c in comments:
            if c['user_id'] == user['id'] or article['owner_id'] == user['id']:
                deletable.append(c['id'])

    if comments:
        lines = []
        for c in comments:
            name = f"@{c['username']}" if c['username'] else c['first_name']
            lines.append(f"<b>{escape_html(name)}</b>: {escape_html(c['text'])}")
        text = f"💬 <b>Комментарии к «{escape_html(article['title'])}»</b>\n\n" + "\n\n".join(lines)
    else:
        text = f"💬 <b>Комментарии к «{escape_html(article['title'])}»</b>\n\nКомментариев пока нет."

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=comments_kb(article_id, offset, bool(total_next), deletable),
    )
    await call.answer()


@router.callback_query(F.data.startswith("comments:"))
async def cb_comments(call: CallbackQuery):
    parts = call.data.split(":")
    article_id = int(parts[1])
    offset = int(parts[2])
    await _render_comments(call, article_id, offset)


@router.callback_query(F.data.startswith("write_comment:"))
async def cb_write_comment_start(call: CallbackQuery, state: FSMContext):
    article_id = int(call.data.split(":")[1])
    await state.set_state(ArticleStates.waiting_comment)
    await state.update_data(article_id=article_id)
    await call.message.edit_text(
        "✍️ Введите ваш комментарий:",
        reply_markup=cancel_kb(f"comments:{article_id}:0"),
    )
    await call.answer()


@router.message(ArticleStates.waiting_comment)
async def msg_add_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    article_id = data['article_id']
    text = (message.text or "").strip()
    if not text:
        await message.answer("❗ Комментарий не может быть пустым:")
        return
    db.add_comment(article_id, message.from_user.id, text)
    await state.clear()
    await message.answer(
        "✅ Комментарий добавлен!",
        reply_markup=InlineKeyboardBuilder()
            .button(text="💬 К комментариям", callback_data=f"comments:{article_id}:0")
            .button(text="📄 К статье", callback_data=f"article:{article_id}")
            .adjust(1).as_markup(),
    )


@router.callback_query(F.data.startswith("del_comment:"))
async def cb_del_comment(call: CallbackQuery):
    parts = call.data.split(":")
    comment_id = int(parts[1])
    article_id = int(parts[2])
    db.delete_comment(comment_id)
    await call.answer("Комментарий удалён.")
    await _render_comments(call, article_id, 0)


# ─── Search ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "search_start")
async def cb_search_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(ArticleStates.waiting_search)
    await call.message.edit_text(
        "🔍 Введите поисковый запрос:\n\n(Ищет среди публичных статей и папок)",
        reply_markup=cancel_kb("main_menu"),
    )
    await call.answer()


@router.message(ArticleStates.waiting_search)
async def msg_search(message: Message, state: FSMContext):
    query = (message.text or "").strip()
    if not query:
        await message.answer("❗ Запрос не может быть пустым:")
        return
    await state.clear()

    articles = db.search_articles(query)
    folders = db.search_folders(query)

    if not articles and not folders:
        await message.answer(
            f"🔍 По запросу «{escape_html(query)}» ничего не найдено.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        return

    builder = InlineKeyboardBuilder()
    text_parts = [f"🔍 <b>Результаты по «{escape_html(query)}»</b>\n"]

    if folders:
        text_parts.append(f"\n📁 <b>Папки ({len(folders)}):</b>")
        for f in folders:
            text_parts.append(f"• {escape_html(f['title'])}")
            builder.button(text=f"📁 {f['title']}", callback_data=f"folder:{f['id']}")

    if articles:
        text_parts.append(f"\n📄 <b>Статьи ({len(articles)}):</b>")
        for a in articles:
            draft = " [черновик]" if a['is_draft'] else ""
            text_parts.append(f"• {escape_html(a['title'])}{draft}")
            builder.button(text=f"📄 {a['title']}", callback_data=f"article:{a['id']}")

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    await message.answer(
        "\n".join(text_parts),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
