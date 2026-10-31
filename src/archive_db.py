import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

DISCOVERY_DB_PATH = Path("data/public_candidates.db")
PRIVATE_BOOKMARKS_DB_PATH = Path("data/personal_bookmarks.db")


def init_databases():
    DISCOVERY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 1. Discovery Archive Database (All statistical anomalies >= 2.5 sigma across scanned books)
    with sqlite3.connect(DISCOVERY_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS public_candidates (
                candidate_id TEXT PRIMARY KEY,
                sector_id TEXT,
                work_title TEXT,
                language TEXT,
                cts_span TEXT,
                peak_snr REAL,
                dominant_channel TEXT,
                novelty_status TEXT,
                primary_attribution TEXT,
                secondary_attribution TEXT,
                hiatus_rate REAL,
                jsd REAL,
                periplus_density REAL,
                english_text TEXT,
                discovered_at TEXT
            )
        """)
        conn.commit()

    # 2. Private Personal Bookmarks Database (Strictly local, git-ignored)
    with sqlite3.connect(PRIVATE_BOOKMARKS_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS personal_bookmarks (
                bookmark_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sector_id TEXT,
                work_title TEXT,
                cts_span TEXT,
                peak_snr REAL,
                dominant_channel TEXT,
                primary_attribution TEXT,
                folder_tag TEXT DEFAULT 'General Interest',
                personal_note TEXT DEFAULT '',
                english_text TEXT,
                saved_at TEXT
            )
        """)
        conn.commit()


def record_public_candidates(work_title: str, lang: str, ghost_df: pd.DataFrame, bound_df: pd.DataFrame):
    """
    Upserts Uncredited Passages and Extended Borrowings with peak_snr >= 2.5
    into the local Discovery Archive SQLite database.
    """
    init_databases()
    combined = pd.concat([ghost_df, bound_df], ignore_index=True)
    if combined.empty:
        return

    combined = combined[combined["peak_snr"] >= 2.5]
    if combined.empty:
        return

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows_to_upsert = []
    for _, hit in combined.iterrows():
        sec_id = str(hit["sector_id"])
        span = str(hit["cts_span"])
        cid = f"{sec_id}_{span}"
        rows_to_upsert.append((
            cid,
            sec_id,
            work_title,
            lang,
            span,
            float(hit["peak_snr"]),
            str(hit["dominant_channel"]),
            str(hit["novelty_status"]),
            str(hit["primary_attribution"]),
            str(hit["secondary_attribution"]),
            float(hit["hiatus_rate"]),
            float(hit["jsd"]),
            float(hit["periplus_density"]),
            str(hit["english_text"]),
            now_str,
        ))

    with sqlite3.connect(DISCOVERY_DB_PATH) as conn:
        conn.execute("DELETE FROM public_candidates WHERE peak_snr < 2.5")
        conn.executemany("""
            INSERT INTO public_candidates (
                candidate_id, sector_id, work_title, language, cts_span,
                peak_snr, dominant_channel, novelty_status,
                primary_attribution, secondary_attribution,
                hiatus_rate, jsd, periplus_density, english_text, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                peak_snr = excluded.peak_snr,
                dominant_channel = excluded.dominant_channel,
                novelty_status = excluded.novelty_status,
                primary_attribution = excluded.primary_attribution,
                secondary_attribution = excluded.secondary_attribution,
                english_text = excluded.english_text,
                discovered_at = excluded.discovered_at
        """, rows_to_upsert)
        conn.commit()


def get_all_public_candidates(
    search_query: str = "",
    channel_filter: str = "",
    tier: str = "extreme",
) -> tuple[list[dict], int, int]:
    """
    Returns (filtered_candidates_list, extreme_count, moderate_count).
    tier = 'extreme'  -> peak_snr >= 3.0
    tier = 'moderate' -> 2.5 <= peak_snr < 3.0
    """
    init_databases()
    base_where = " WHERE 1=1"
    params = []

    if search_query:
        base_where += " AND (english_text LIKE ? OR work_title LIKE ? OR primary_attribution LIKE ? OR cts_span LIKE ?)"
        q_like = f"%{search_query}%"
        params.extend([q_like, q_like, q_like, q_like])

    if channel_filter:
        base_where += " AND dominant_channel = ?"
        params.append(channel_filter)

    with sqlite3.connect(DISCOVERY_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        ext_cnt = conn.execute(
            f"SELECT COUNT(*) FROM public_candidates {base_where} AND peak_snr >= 3.0",
            params,
        ).fetchone()[0]
        mod_cnt = conn.execute(
            f"SELECT COUNT(*) FROM public_candidates {base_where} AND peak_snr >= 2.5 AND peak_snr < 3.0",
            params,
        ).fetchone()[0]

        if tier == "moderate":
            tier_sql = " AND peak_snr >= 2.5 AND peak_snr < 3.0"
        else:
            tier_sql = " AND peak_snr >= 3.0"

        rows = conn.execute(
            f"SELECT * FROM public_candidates {base_where} {tier_sql} ORDER BY peak_snr DESC",
            params,
        ).fetchall()
        return [dict(r) for r in rows], int(ext_cnt), int(mod_cnt)


def add_personal_bookmark(
    sector_id: str,
    work_title: str,
    cts_span: str,
    peak_snr: float,
    dominant_channel: str,
    primary_attribution: str,
    folder_tag: str,
    personal_note: str,
    english_text: str,
):
    init_databases()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    with sqlite3.connect(PRIVATE_BOOKMARKS_DB_PATH) as conn:
        conn.execute("""
            INSERT INTO personal_bookmarks (
                sector_id, work_title, cts_span, peak_snr, dominant_channel,
                primary_attribution, folder_tag, personal_note, english_text, saved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sector_id,
            work_title,
            cts_span,
            float(peak_snr),
            dominant_channel,
            primary_attribution,
            folder_tag.strip() or "General Interest",
            personal_note.strip(),
            english_text,
            now_str,
        ))
        conn.commit()


def get_personal_bookmarks() -> list[dict]:
    init_databases()
    with sqlite3.connect(PRIVATE_BOOKMARKS_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM personal_bookmarks ORDER BY folder_tag ASC, bookmark_id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_personal_bookmark(bookmark_id: int):
    init_databases()
    with sqlite3.connect(PRIVATE_BOOKMARKS_DB_PATH) as conn:
        conn.execute("DELETE FROM personal_bookmarks WHERE bookmark_id = ?", (int(bookmark_id),))
        conn.commit()