import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from typing import Optional

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не задан!")

def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

@contextmanager
def db_conn():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def fetchall(conn, query, params=()):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()

def fetchone(conn, query, params=()):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchone()

def execute(conn, query, params=()):
    cur = conn.cursor()
    cur.execute(query, params)
    return cur

def init_db():
    with db_conn() as conn:
        execute(conn, """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            tg_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            language TEXT NOT NULL DEFAULT 'ru',
            view_mode TEXT NOT NULL DEFAULT 'full',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        execute(conn, """
        CREATE TABLE IF NOT EXISTS folders (
            id BIGSERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            owner_id BIGINT NOT NULL REFERENCES users(id),
            access TEXT NOT NULL DEFAULT 'private',
            invite_token TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        execute(conn, """
        CREATE TABLE IF NOT EXISTS groups (
            id BIGSERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            folder_id BIGINT REFERENCES folders(id) ON DELETE CASCADE,
            parent_group_id BIGINT REFERENCES groups(id) ON DELETE CASCADE,
            owner_id BIGINT NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        execute(conn, """
        CREATE TABLE IF NOT EXISTS articles (
            id BIGSERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            owner_id BIGINT NOT NULL REFERENCES users(id),
            folder_id BIGINT REFERENCES folders(id) ON DELETE SET NULL,
            group_id BIGINT REFERENCES groups(id) ON DELETE SET NULL,
            access TEXT NOT NULL DEFAULT 'private',
            invite_token TEXT UNIQUE,
            is_draft INTEGER NOT NULL DEFAULT 1,
            like_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        execute(conn, """
        CREATE TABLE IF NOT EXISTS article_blocks (
            id BIGSERIAL PRIMARY KEY,
            article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            block_order INTEGER NOT NULL DEFAULT 0,
            block_type TEXT NOT NULL DEFAULT 'text',
            content TEXT,
            file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        execute(conn, """
        CREATE TABLE IF NOT EXISTS editors (
            id BIGSERIAL PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL REFERENCES users(id),
            UNIQUE(entity_type, entity_id, user_id)
        )
        """)
        execute(conn, """
        CREATE TABLE IF NOT EXISTS likes (
            id BIGSERIAL PRIMARY KEY,
            article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(article_id, user_id)
        )
        """)
        execute(conn, """
        CREATE TABLE IF NOT EXISTS comments (
            id BIGSERIAL PRIMARY KEY,
            article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL REFERENCES users(id),
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # Indexes
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_folders_owner ON folders(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_groups_folder ON groups(folder_id)",
            "CREATE INDEX IF NOT EXISTS idx_groups_parent ON groups(parent_group_id)",
            "CREATE INDEX IF NOT EXISTS idx_articles_folder ON articles(folder_id)",
            "CREATE INDEX IF NOT EXISTS idx_articles_group ON articles(group_id)",
            "CREATE INDEX IF NOT EXISTS idx_articles_owner ON articles(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_article_blocks_article ON article_blocks(article_id)",
            "CREATE INDEX IF NOT EXISTS idx_editors_entity ON editors(entity_type, entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_likes_article ON likes(article_id)",
            "CREATE INDEX IF NOT EXISTS idx_comments_article ON comments(article_id)",
        ]:
            execute(conn, idx_sql)
    print("Database initialized.")


# ─── Users ───────────────────────────────────────────────────────────────────

def upsert_user(tg_id: int, username: Optional[str], first_name: Optional[str]):
    with db_conn() as conn:
        execute(conn, """
            INSERT INTO users(tg_id, username, first_name)
            VALUES(%s,%s,%s)
            ON CONFLICT(tg_id) DO UPDATE SET username=EXCLUDED.username, first_name=EXCLUDED.first_name
        """, (tg_id, username, first_name))

def get_user(tg_id: int):
    with db_conn() as conn:
        return fetchone(conn, "SELECT * FROM users WHERE tg_id=%s", (tg_id,))

def get_user_by_id(user_id: int):
    with db_conn() as conn:
        return fetchone(conn, "SELECT * FROM users WHERE id=%s", (user_id,))

def get_user_by_username(username: str):
    with db_conn() as conn:
        return fetchone(conn, "SELECT * FROM users WHERE username=%s", (username.lstrip('@'),))

def get_user_language(tg_id: int) -> str:
    with db_conn() as conn:
        row = fetchone(conn, "SELECT language FROM users WHERE tg_id=%s", (tg_id,))
        return (row['language'] if row and row['language'] else 'ru')

def set_user_language(tg_id: int, lang: str):
    with db_conn() as conn:
        execute(conn, "UPDATE users SET language=%s WHERE tg_id=%s", (lang, tg_id))

def get_user_view_mode(tg_id: int) -> str:
    with db_conn() as conn:
        row = fetchone(conn, "SELECT view_mode FROM users WHERE tg_id=%s", (tg_id,))
        return (row['view_mode'] if row and row['view_mode'] else 'full')

def set_user_view_mode(tg_id: int, mode: str):
    with db_conn() as conn:
        execute(conn, "UPDATE users SET view_mode=%s WHERE tg_id=%s", (mode, tg_id))


# ─── Folders ─────────────────────────────────────────────────────────────────

def create_folder(title: str, owner_tg_id: int) -> int:
    user = get_user(owner_tg_id)
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO folders(title, owner_id) VALUES(%s,%s) RETURNING id", (title, user['id']))
            row = cur.fetchone()
        return row[0]

def get_folder(folder_id: int):
    with db_conn() as conn:
        return fetchone(conn, "SELECT * FROM folders WHERE id=%s", (folder_id,))

def get_user_folders(tg_id: int):
    user = get_user(tg_id)
    if not user:
        return []
    with db_conn() as conn:
        owned = fetchall(conn, "SELECT f.* FROM folders f WHERE f.owner_id=%s ORDER BY f.updated_at DESC", (user['id'],))
        edited = fetchall(conn, """
            SELECT f.* FROM folders f
            JOIN editors e ON e.entity_type='folder' AND e.entity_id=f.id AND e.user_id=%s
            ORDER BY f.updated_at DESC
        """, (user['id'],))
        seen = {r['id'] for r in owned}
        result = list(owned)
        for r in edited:
            if r['id'] not in seen:
                result.append(r)
        return result

def update_folder(folder_id: int, title: str = None, access: str = None, invite_token: str = None):
    with db_conn() as conn:
        if title is not None:
            execute(conn, "UPDATE folders SET title=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (title, folder_id))
        if access is not None:
            execute(conn, "UPDATE folders SET access=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (access, folder_id))
        if invite_token is not None:
            execute(conn, "UPDATE folders SET invite_token=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (invite_token, folder_id))

def delete_folder(folder_id: int):
    with db_conn() as conn:
        execute(conn, "DELETE FROM folders WHERE id=%s", (folder_id,))

def get_public_folders(sort='new', limit=20, offset=0):
    with db_conn() as conn:
        order = "f.created_at DESC" if sort == 'new' else "(SELECT COUNT(*) FROM articles a WHERE a.folder_id=f.id) DESC"
        return fetchall(conn, f"""
            SELECT f.*, u.first_name as owner_name, u.username as owner_username
            FROM folders f JOIN users u ON u.id=f.owner_id
            WHERE f.access='public'
            ORDER BY {order}
            LIMIT %s OFFSET %s
        """, (limit, offset))

def get_folder_by_token(token: str):
    with db_conn() as conn:
        return fetchone(conn, "SELECT * FROM folders WHERE invite_token=%s", (token,))


# ─── Groups ───────────────────────────────────────────────────────────────────

def create_group(title: str, owner_tg_id: int, folder_id: int = None, parent_group_id: int = None) -> int:
    user = get_user(owner_tg_id)
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO groups(title, owner_id, folder_id, parent_group_id) VALUES(%s,%s,%s,%s) RETURNING id",
                (title, user['id'], folder_id, parent_group_id)
            )
            row = cur.fetchone()
        return row[0]

def get_group(group_id: int):
    with db_conn() as conn:
        return fetchone(conn, "SELECT * FROM groups WHERE id=%s", (group_id,))

def get_folder_groups(folder_id: int):
    with db_conn() as conn:
        return fetchall(conn,
            "SELECT * FROM groups WHERE folder_id=%s AND parent_group_id IS NULL ORDER BY created_at DESC",
            (folder_id,)
        )

def get_subgroups(group_id: int):
    with db_conn() as conn:
        return fetchall(conn,
            "SELECT * FROM groups WHERE parent_group_id=%s ORDER BY created_at DESC",
            (group_id,)
        )

def delete_group(group_id: int):
    with db_conn() as conn:
        execute(conn, "DELETE FROM groups WHERE id=%s", (group_id,))

def update_group_title(group_id: int, title: str):
    with db_conn() as conn:
        execute(conn, "UPDATE groups SET title=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (title, group_id))


# ─── Articles ─────────────────────────────────────────────────────────────────

def create_article(title: str, owner_tg_id: int, folder_id: int = None, group_id: int = None) -> int:
    user = get_user(owner_tg_id)
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO articles(title, owner_id, folder_id, group_id) VALUES(%s,%s,%s,%s) RETURNING id",
                (title, user['id'], folder_id, group_id)
            )
            row = cur.fetchone()
        return row[0]

def get_article(article_id: int):
    with db_conn() as conn:
        return fetchone(conn, "SELECT * FROM articles WHERE id=%s", (article_id,))

def get_folder_articles(folder_id: int):
    with db_conn() as conn:
        return fetchall(conn,
            "SELECT * FROM articles WHERE folder_id=%s AND group_id IS NULL ORDER BY created_at DESC",
            (folder_id,)
        )

def get_group_articles(group_id: int):
    with db_conn() as conn:
        return fetchall(conn,
            "SELECT * FROM articles WHERE group_id=%s ORDER BY created_at DESC",
            (group_id,)
        )

def get_user_articles(tg_id: int):
    user = get_user(tg_id)
    if not user:
        return []
    with db_conn() as conn:
        owned = fetchall(conn,
            "SELECT a.* FROM articles a WHERE a.owner_id=%s ORDER BY a.updated_at DESC",
            (user['id'],)
        )
        edited = fetchall(conn, """
            SELECT a.* FROM articles a
            JOIN editors e ON e.entity_type='article' AND e.entity_id=a.id AND e.user_id=%s
            ORDER BY a.updated_at DESC
        """, (user['id'],))
        seen = {r['id'] for r in owned}
        result = list(owned)
        for r in edited:
            if r['id'] not in seen:
                result.append(r)
        return result

def update_article(article_id: int, title: str = None, access: str = None,
                   invite_token: str = None, is_draft: int = None):
    with db_conn() as conn:
        if title is not None:
            execute(conn, "UPDATE articles SET title=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (title, article_id))
        if access is not None:
            execute(conn, "UPDATE articles SET access=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (access, article_id))
        if invite_token is not None:
            execute(conn, "UPDATE articles SET invite_token=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (invite_token, article_id))
        if is_draft is not None:
            execute(conn, "UPDATE articles SET is_draft=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (is_draft, article_id))

def delete_article(article_id: int):
    with db_conn() as conn:
        execute(conn, "DELETE FROM articles WHERE id=%s", (article_id,))

def get_public_articles(sort='new', limit=20, offset=0):
    with db_conn() as conn:
        order = "a.created_at DESC" if sort == 'new' else "a.like_count DESC"
        return fetchall(conn, f"""
            SELECT a.*, u.first_name as owner_name, u.username as owner_username
            FROM articles a JOIN users u ON u.id=a.owner_id
            WHERE a.access='public' AND a.is_draft=0
            ORDER BY {order}
            LIMIT %s OFFSET %s
        """, (limit, offset))

def get_article_by_token(token: str):
    with db_conn() as conn:
        return fetchone(conn, "SELECT * FROM articles WHERE invite_token=%s", (token,))

def search_articles(query: str, limit=20):
    with db_conn() as conn:
        pattern = f"%{query}%"
        return fetchall(conn, """
            SELECT a.*, u.first_name as owner_name
            FROM articles a JOIN users u ON u.id=a.owner_id
            WHERE a.access='public' AND a.is_draft=0
              AND (a.title ILIKE %s OR EXISTS (
                SELECT 1 FROM article_blocks ab
                WHERE ab.article_id=a.id AND ab.block_type='text' AND ab.content ILIKE %s
              ))
            ORDER BY a.like_count DESC
            LIMIT %s
        """, (pattern, pattern, limit))

def search_folders(query: str, limit=10):
    with db_conn() as conn:
        pattern = f"%{query}%"
        return fetchall(conn, """
            SELECT f.*, u.first_name as owner_name
            FROM folders f JOIN users u ON u.id=f.owner_id
            WHERE f.access='public' AND f.title ILIKE %s
            ORDER BY f.updated_at DESC LIMIT %s
        """, (pattern, limit))


# ─── Article Blocks ───────────────────────────────────────────────────────────

def add_block(article_id: int, block_type: str, content: str = None, file_id: str = None) -> int:
    with db_conn() as conn:
        row = fetchone(conn,
            "SELECT COALESCE(MAX(block_order),0) as mo FROM article_blocks WHERE article_id=%s",
            (article_id,)
        )
        max_order = row['mo']
        cur = execute(conn,
            "INSERT INTO article_blocks(article_id, block_order, block_type, content, file_id) VALUES(%s,%s,%s,%s,%s) RETURNING id",
            (article_id, max_order + 1, block_type, content, file_id)
        )
        new_id = cur.fetchone()[0]
        cur.close()
        execute(conn, "UPDATE articles SET updated_at=CURRENT_TIMESTAMP WHERE id=%s", (article_id,))
        return new_id

def get_article_blocks(article_id: int):
    with db_conn() as conn:
        return fetchall(conn,
            "SELECT * FROM article_blocks WHERE article_id=%s ORDER BY block_order",
            (article_id,)
        )

def delete_block(block_id: int):
    with db_conn() as conn:
        row = fetchone(conn, "SELECT article_id FROM article_blocks WHERE id=%s", (block_id,))
        execute(conn, "DELETE FROM article_blocks WHERE id=%s", (block_id,))
        if row:
            execute(conn, "UPDATE articles SET updated_at=CURRENT_TIMESTAMP WHERE id=%s", (row['article_id'],))

def clear_article_blocks(article_id: int):
    with db_conn() as conn:
        execute(conn, "DELETE FROM article_blocks WHERE article_id=%s", (article_id,))


# ─── Editors ─────────────────────────────────────────────────────────────────

def add_editor(entity_type: str, entity_id: int, user_id: int):
    with db_conn() as conn:
        execute(conn,
            "INSERT INTO editors(entity_type, entity_id, user_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
            (entity_type, entity_id, user_id)
        )

def remove_editor(entity_type: str, entity_id: int, user_id: int):
    with db_conn() as conn:
        execute(conn,
            "DELETE FROM editors WHERE entity_type=%s AND entity_id=%s AND user_id=%s",
            (entity_type, entity_id, user_id)
        )

def get_editors(entity_type: str, entity_id: int):
    with db_conn() as conn:
        return fetchall(conn, """
            SELECT u.* FROM editors e
            JOIN users u ON u.id=e.user_id
            WHERE e.entity_type=%s AND e.entity_id=%s
        """, (entity_type, entity_id))

def is_editor(entity_type: str, entity_id: int, tg_id: int):
    user = get_user(tg_id)
    if not user:
        return False
    with db_conn() as conn:
        row = fetchone(conn,
            "SELECT 1 FROM editors WHERE entity_type=%s AND entity_id=%s AND user_id=%s",
            (entity_type, entity_id, user['id'])
        )
        return row is not None


# ─── Likes ────────────────────────────────────────────────────────────────────

def toggle_like(article_id: int, tg_id: int) -> bool:
    user = get_user(tg_id)
    with db_conn() as conn:
        existing = fetchone(conn,
            "SELECT 1 FROM likes WHERE article_id=%s AND user_id=%s",
            (article_id, user['id'])
        )
        if existing:
            execute(conn, "DELETE FROM likes WHERE article_id=%s AND user_id=%s", (article_id, user['id']))
            execute(conn, "UPDATE articles SET like_count=like_count-1 WHERE id=%s", (article_id,))
            return False
        else:
            execute(conn, "INSERT INTO likes(article_id, user_id) VALUES(%s,%s)", (article_id, user['id']))
            execute(conn, "UPDATE articles SET like_count=like_count+1 WHERE id=%s", (article_id,))
            return True

def has_liked(article_id: int, tg_id: int) -> bool:
    user = get_user(tg_id)
    if not user:
        return False
    with db_conn() as conn:
        return fetchone(conn,
            "SELECT 1 FROM likes WHERE article_id=%s AND user_id=%s",
            (article_id, user['id'])
        ) is not None

def get_user_liked_articles(tg_id: int):
    user = get_user(tg_id)
    if not user:
        return []
    with db_conn() as conn:
        return fetchall(conn, """
            SELECT a.*, u.first_name as owner_name FROM articles a
            JOIN likes l ON l.article_id=a.id AND l.user_id=%s
            JOIN users u ON u.id=a.owner_id
            ORDER BY l.created_at DESC
        """, (user['id'],))


# ─── Comments ─────────────────────────────────────────────────────────────────

def add_comment(article_id: int, tg_id: int, text: str) -> int:
    user = get_user(tg_id)
    with db_conn() as conn:
        cur = execute(conn,
            "INSERT INTO comments(article_id, user_id, text) VALUES(%s,%s,%s) RETURNING id",
            (article_id, user['id'], text)
        )
        new_id = cur.fetchone()[0]
        cur.close()
        return new_id

def get_comments(article_id: int, limit=20, offset=0):
    with db_conn() as conn:
        return fetchall(conn, """
            SELECT c.*, u.first_name, u.username FROM comments c
            JOIN users u ON u.id=c.user_id
            WHERE c.article_id=%s
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
        """, (article_id, limit, offset))

def delete_comment(comment_id: int):
    with db_conn() as conn:
        execute(conn, "DELETE FROM comments WHERE id=%s", (comment_id,))
