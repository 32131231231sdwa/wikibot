import secrets
import html
from typing import List

CHUNK_SIZE = 4000


def generate_token() -> str:
    return secrets.token_urlsafe(16)


def escape_html(text: str) -> str:
    return html.escape(text or "")


def split_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """Split long text into chunks preserving word boundaries."""
    if not text:
        return [""]
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    while len(text) > chunk_size:
        split_at = text.rfind('\n', 0, chunk_size)
        if split_at == -1:
            split_at = text.rfind(' ', 0, chunk_size)
        if split_at == -1:
            split_at = chunk_size
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    if text:
        chunks.append(text)
    return chunks


def format_access(access: str) -> str:
    mapping = {
        'private': '🔒 Приватная',
        'link': '🔗 По ссылке',
        'public': '🌍 Публичная',
    }
    return mapping.get(access, access)


def user_display(row) -> str:
    if row['username']:
        return f"@{row['username']}"
    return row['first_name'] or f"id:{row['tg_id']}"
