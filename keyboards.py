from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ─── Main Menu ────────────────────────────────────────────────────────────────

def main_menu_kb(s: dict | None = None) -> InlineKeyboardMarkup:
    """
    s — strings dict from i18n.get_strings(lang).
    Falls back to Russian labels if s is None.
    """
    if s is None:
        s = {}
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=s.get('btn_my_folders', '📁 Мои папки'), callback_data="my_folders"),
        InlineKeyboardButton(text=s.get('btn_my_articles', '📄 Мои статьи'), callback_data="my_articles"),
    )
    builder.row(
        InlineKeyboardButton(text=s.get('btn_public', '🌍 Выложенное'), callback_data="public:new:0"),
        InlineKeyboardButton(text=s.get('btn_search', '🔍 Поиск'), callback_data="search_start"),
    )
    builder.row(
        InlineKeyboardButton(text=s.get('btn_profile', '👤 Профиль'), callback_data="profile"),
        InlineKeyboardButton(text=s.get('btn_settings', '⚙️ Настройки'), callback_data="settings"),
    )
    builder.row(
        InlineKeyboardButton(text=s.get('btn_create_folder', '➕ Папку'), callback_data="create_folder"),
        InlineKeyboardButton(text=s.get('btn_create_article', '➕ Статью'), callback_data="create_article_solo"),
    )
    return builder.as_markup()


def back_main_kb(s: dict | None = None) -> InlineKeyboardMarkup:
    if s is None:
        s = {}
    builder = InlineKeyboardBuilder()
    builder.button(text=s.get('btn_back_main', '◀️ Главное меню'), callback_data="main_menu")
    return builder.as_markup()


# ─── Settings ─────────────────────────────────────────────────────────────────

def settings_kb(s: dict, lang: str, view_mode: str) -> InlineKeyboardMarkup:
    from i18n import TRANSLATIONS
    lang_name = TRANSLATIONS.get(lang, {}).get('lang_name', lang)
    mode_key = 'mode_full' if view_mode == 'full' else 'mode_compact'
    mode_name = s.get(mode_key, view_mode)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"{s.get('settings_lang_label', '🌐 Язык')}: {lang_name}",
        callback_data="settings_language",
    ))
    builder.row(InlineKeyboardButton(
        text=f"{s.get('settings_mode_label', '👁 Режим')}: {mode_name}",
        callback_data="settings_mode",
    ))
    builder.row(InlineKeyboardButton(
        text=s.get('btn_back_main', '◀️ Главное меню'),
        callback_data="main_menu",
    ))
    return builder.as_markup()


def language_select_kb(current_lang: str, s: dict) -> InlineKeyboardMarkup:
    from i18n import LANGUAGES, TRANSLATIONS
    builder = InlineKeyboardBuilder()
    for code in LANGUAGES:
        name = TRANSLATIONS.get(code, {}).get('lang_name', code)
        check = "✅ " if code == current_lang else ""
        builder.row(InlineKeyboardButton(
            text=f"{check}{name}",
            callback_data=f"set_language:{code}",
        ))
    builder.row(InlineKeyboardButton(
        text=s.get('btn_back', '◀️ Назад'),
        callback_data="settings",
    ))
    return builder.as_markup()


def view_mode_select_kb(current_mode: str, s: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for mode, key in [('full', 'mode_full'), ('compact', 'mode_compact')]:
        check = "✅ " if current_mode == mode else ""
        builder.row(InlineKeyboardButton(
            text=f"{check}{s.get(key, mode)}",
            callback_data=f"set_view_mode:{mode}",
        ))
    builder.row(InlineKeyboardButton(
        text=s.get('btn_back', '◀️ Назад'),
        callback_data="settings",
    ))
    return builder.as_markup()


# ─── Lists ────────────────────────────────────────────────────────────────────

def folder_list_kb(folders, page=0, page_size=8) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * page_size
    chunk = folders[start:start + page_size]
    for f in chunk:
        builder.row(InlineKeyboardButton(text=f"📁  {f['title']}", callback_data=f"folder:{f['id']}"))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Пред.", callback_data=f"my_folders_page:{page-1}"))
    if start + page_size < len(folders):
        nav.append(InlineKeyboardButton(text="След. ▶️", callback_data=f"my_folders_page:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def article_list_kb(articles, back_cb="main_menu", page=0, page_size=8) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * page_size
    chunk = articles[start:start + page_size]
    for a in chunk:
        draft = "  📝" if a['is_draft'] else "  ✅"
        builder.row(InlineKeyboardButton(text=f"📄  {a['title']}{draft}", callback_data=f"article:{a['id']}"))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Пред.", callback_data=f"article_page:{back_cb}:{page-1}"))
    if start + page_size < len(articles):
        nav.append(InlineKeyboardButton(text="След. ▶️", callback_data=f"article_page:{back_cb}:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_cb))
    return builder.as_markup()


# ─── Folder ───────────────────────────────────────────────────────────────────

def folder_view_kb(folder_id: int, is_owner: bool, access: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📂 Группы", callback_data=f"folder_groups:{folder_id}"),
        InlineKeyboardButton(text="📜 Статьи", callback_data=f"folder_articles:{folder_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="➕ Группу", callback_data=f"create_group:folder:{folder_id}"),
        InlineKeyboardButton(text="➕ Статью", callback_data=f"create_article:folder:{folder_id}"),
    )
    if is_owner:
        builder.row(InlineKeyboardButton(text="⚙️ Настройки папки", callback_data=f"folder_settings:{folder_id}"))
    if access == 'link':
        builder.row(InlineKeyboardButton(text="🔗 Получить ссылку доступа", callback_data=f"get_folder_link:{folder_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Мои папки", callback_data="my_folders"))
    return builder.as_markup()


def folder_settings_kb(folder_id: int, access: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    accesses = [('private', '🔒 Приватная'), ('link', '🔗 По ссылке'), ('public', '🌍 Публичная')]
    for key, label in accesses:
        prefix = "✅ " if access == key else ""
        builder.row(InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"folder_access:{folder_id}:{key}"))
    builder.row(
        InlineKeyboardButton(text="👥 Редакторы", callback_data=f"editors:folder:{folder_id}"),
        InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename_folder:{folder_id}"),
    )
    builder.row(InlineKeyboardButton(text="🗑 Удалить папку", callback_data=f"delete_folder:{folder_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к папке", callback_data=f"folder:{folder_id}"))
    return builder.as_markup()


# ─── Group ────────────────────────────────────────────────────────────────────

def group_view_kb(group_id: int, is_owner_or_editor: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📂 Подгруппы", callback_data=f"group_subgroups:{group_id}"),
        InlineKeyboardButton(text="📜 Статьи", callback_data=f"group_articles:{group_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="➕ Подгруппу", callback_data=f"create_group:group:{group_id}"),
        InlineKeyboardButton(text="➕ Статью", callback_data=f"create_article:group:{group_id}"),
    )
    if is_owner_or_editor:
        builder.row(InlineKeyboardButton(text="⚙️ Настройки группы", callback_data=f"group_settings:{group_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"group_back:{group_id}"))
    return builder.as_markup()


def group_settings_kb(group_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Редакторы", callback_data=f"editors:group:{group_id}"),
        InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename_group:{group_id}"),
    )
    builder.row(InlineKeyboardButton(text="🗑 Удалить группу", callback_data=f"delete_group:{group_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к группе", callback_data=f"group:{group_id}"))
    return builder.as_markup()


# ─── Article view ─────────────────────────────────────────────────────────────

def article_view_kb(article_id: int, can_edit: bool, liked: bool, access: str, is_draft: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    like_text = "❤️ Лайк" if not liked else "💔 Убрать лайк"
    builder.row(
        InlineKeyboardButton(text=like_text, callback_data=f"like:{article_id}"),
        InlineKeyboardButton(text="💬 Комментарии", callback_data=f"comments:{article_id}:0"),
    )
    if can_edit:
        builder.row(
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_article:{article_id}"),
            InlineKeyboardButton(text="🔗 Поделиться", callback_data=f"share_article:{article_id}"),
        )
    else:
        builder.row(InlineKeyboardButton(text="🔗 Поделиться", callback_data=f"share_article:{article_id}"))
    if can_edit and is_draft:
        builder.row(InlineKeyboardButton(text="✅ Опубликовать черновик", callback_data=f"publish_article:{article_id}"))
    if can_edit and not is_draft:
        builder.row(InlineKeyboardButton(text="⚙️ Настройки статьи", callback_data=f"article_settings:{article_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"article_back:{article_id}"))
    return builder.as_markup()


# ─── Article editor ───────────────────────────────────────────────────────────

def article_edit_kb(article_id: int) -> InlineKeyboardMarkup:
    """Main editor menu — shown when no blocks to display or as fallback."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Добавить текст", callback_data=f"add_text:{article_id}"),
        InlineKeyboardButton(text="🖼 Добавить фото", callback_data=f"add_photo:{article_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Добавить ссылку", callback_data=f"add_link:{article_id}"),
        InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename_article:{article_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"publish_article:{article_id}"),
        InlineKeyboardButton(text="👁 Просмотр", callback_data=f"article:{article_id}"),
    )
    builder.row(InlineKeyboardButton(text="⚙️ Настройки доступа", callback_data=f"article_settings:{article_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"article_back:{article_id}"))
    return builder.as_markup()


def article_blocks_editor_kb(article_id: int, blocks) -> InlineKeyboardMarkup:
    """
    Editor with inline blocks — each text/link block has ✏️ edit + 🗑 delete,
    photo blocks have only 🗑 delete. Add buttons below.
    """
    builder = InlineKeyboardBuilder()
    for b in blocks:
        bid = b['id']
        if b['block_type'] == 'text':
            preview = (b['content'] or '').replace('\n', ' ')[:28]
            builder.row(
                InlineKeyboardButton(text=f"📝 {preview}…", callback_data=f"block_preview:{bid}"),
            )
            builder.row(
                InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"edit_block:{bid}:{article_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"confirm_del_block:{bid}:{article_id}"),
            )
        elif b['block_type'] == 'photo':
            builder.row(
                InlineKeyboardButton(text=f"🖼 Фото #{bid}", callback_data=f"block_preview:{bid}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"confirm_del_block:{bid}:{article_id}"),
            )
        elif b['block_type'] == 'link':
            preview = (b['content'] or '').replace('\n', ' ')[:28]
            builder.row(
                InlineKeyboardButton(text=f"🔗 {preview}…", callback_data=f"block_preview:{bid}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"confirm_del_block:{bid}:{article_id}"),
            )
    # Divider — add actions
    builder.row(
        InlineKeyboardButton(text="➕ Текст", callback_data=f"add_text:{article_id}"),
        InlineKeyboardButton(text="➕ Фото", callback_data=f"add_photo:{article_id}"),
        InlineKeyboardButton(text="➕ Ссылку", callback_data=f"add_link:{article_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename_article:{article_id}"),
        InlineKeyboardButton(text="⚙️ Доступ", callback_data=f"article_settings:{article_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"publish_article:{article_id}"),
        InlineKeyboardButton(text="👁 Просмотр", callback_data=f"article:{article_id}"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"article_back:{article_id}"))
    return builder.as_markup()


def article_settings_kb(article_id: int, access: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    accesses = [('private', '🔒 Приватная'), ('link', '🔗 По ссылке'), ('public', '🌍 Публичная')]
    for key, label in accesses:
        prefix = "✅ " if access == key else ""
        builder.row(InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"article_access:{article_id}:{key}"))
    builder.row(
        InlineKeyboardButton(text="👥 Редакторы", callback_data=f"editors:article:{article_id}"),
    )
    if access == 'link':
        builder.row(InlineKeyboardButton(text="🔗 Получить ссылку доступа", callback_data=f"get_article_link:{article_id}"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить статью", callback_data=f"delete_article:{article_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к редактору", callback_data=f"edit_article:{article_id}"))
    return builder.as_markup()


# ─── Editors ─────────────────────────────────────────────────────────────────

def editors_kb(entity_type: str, entity_id: int, editors) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ed in editors:
        name = f"@{ed['username']}" if ed['username'] else ed['first_name']
        builder.row(InlineKeyboardButton(text=f"❌ Убрать {name}", callback_data=f"remove_editor:{entity_type}:{entity_id}:{ed['id']}"))
    builder.row(InlineKeyboardButton(text="➕ Добавить редактора", callback_data=f"add_editor:{entity_type}:{entity_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_from_editors:{entity_type}:{entity_id}"))
    return builder.as_markup()


# ─── Public feed ──────────────────────────────────────────────────────────────

def public_feed_kb(sort: str, offset: int, has_more: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=("✅ Новое" if sort == 'new' else "🆕 Новое"),
            callback_data="public:new:0"
        ),
        InlineKeyboardButton(
            text=("✅ Залайканное" if sort == 'liked' else "❤️ Залайканное"),
            callback_data="public:liked:0"
        ),
    )
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀️ Пред.", callback_data=f"public:{sort}:{max(0,offset-10)}"))
    if has_more:
        nav.append(InlineKeyboardButton(text="След. ▶️", callback_data=f"public:{sort}:{offset+10}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


# ─── Comments ────────────────────────────────────────────────────────────────

def comments_kb(article_id: int, offset: int, has_more: bool, can_delete_ids=None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_delete_ids:
        for cid in can_delete_ids:
            builder.row(InlineKeyboardButton(text=f"🗑 Удалить комментарий #{cid}", callback_data=f"del_comment:{cid}:{article_id}"))
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀️ Пред.", callback_data=f"comments:{article_id}:{max(0,offset-10)}"))
    if has_more:
        nav.append(InlineKeyboardButton(text="След. ▶️", callback_data=f"comments:{article_id}:{offset+10}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="✍️ Написать комментарий", callback_data=f"write_comment:{article_id}"))
    builder.row(InlineKeyboardButton(text="◀️ К статье", callback_data=f"article:{article_id}"))
    return builder.as_markup()


# ─── Misc ────────────────────────────────────────────────────────────────────

def confirm_kb(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=yes_cb),
        InlineKeyboardButton(text="❌ Отмена", callback_data=no_cb),
    )
    return builder.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📁 Мои папки", callback_data="my_folders"),
        InlineKeyboardButton(text="📄 Мои статьи", callback_data="my_articles"),
    )
    builder.row(InlineKeyboardButton(text="❤️ Мои лайки", callback_data="my_likes"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))
    return builder.as_markup()


def cancel_kb(back_cb: str = "main_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data=back_cb)
    return builder.as_markup()


def blocks_list_kb(article_id: int, blocks) -> InlineKeyboardMarkup:
    """Legacy — used only by old delete flow, replaced by article_blocks_editor_kb."""
    builder = InlineKeyboardBuilder()
    for b in blocks:
        if b['block_type'] == 'text':
            preview = (b['content'] or '')[:30].replace('\n', ' ')
            label = f"📝 #{b['id']}: {preview}…"
        elif b['block_type'] == 'photo':
            label = f"🖼 #{b['id']}: фото"
        else:
            label = f"🔗 #{b['id']}: ссылка"
        builder.row(InlineKeyboardButton(text=label, callback_data=f"confirm_del_block:{b['id']}:{article_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_article:{article_id}"))
    return builder.as_markup()
