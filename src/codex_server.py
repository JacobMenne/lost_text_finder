import html
import json
import os
import random
import threading
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import pandas as pd

from catalog import CORPUS_REGISTRY, SCAN_LOG_PATH
from ingest import ingest_target_book
from scanner import scan_and_attribute
from codex_reader import (
    open_file_cross_platform,
    SHARED_CODEX_CSS_AND_JS,
    render_top_navbar,
)
from archive_db import (
    init_databases,
    get_all_public_candidates,
    add_personal_bookmark,
    get_personal_bookmarks,
    delete_personal_bookmark,
)


def _load_history_map() -> dict:
    if not os.path.exists(SCAN_LOG_PATH):
        return {}
    df = pd.read_csv(SCAN_LOG_PATH)
    out = {}
    for _, row in df.iterrows():
        out[str(row["sector_id"])] = {
            "ghosts": int(row["ghost_count"]),
            "bounds": int(row["boundary_count"]),
            "max_snr": float(row["max_snr"]),
        }
    return out


def render_grand_archive_html() -> str:
    history = _load_history_map()
    total_books = sum(len(w["books"]) for w in CORPUS_REGISTRY)
    scanned_books = len(history)
    total_ghosts = sum(v["ghosts"] for v in history.values())
    total_bounds = sum(v["bounds"] for v in history.values())

    genres = {}
    for work in CORPUS_REGISTRY:
        genres.setdefault(work["genre"], []).append(work)

    genre_sections = []
    for genre_title, works in genres.items():
        work_cards = []
        for work in works:
            wid = work["id"]
            wtitle = html.escape(work["title"])
            lang = html.escape(work["lang"])
            done_cnt = sum(1 for b in work["books"] if f"{wid.upper()}_{b.zfill(2)}" in history)

            book_buttons = []
            for b in work["books"]:
                sec_id = f"{wid.upper()}_{b.zfill(2)}"
                codex_file = Path("candidates") / f"{sec_id.lower()}_codex.html"
                if sec_id in history and codex_file.exists():
                    info = history[sec_id]
                    badge_txt = f"✓ Book {b} · {info['ghosts']}U / {info['bounds']}E ({info['max_snr']:.1f}σ)"
                    book_buttons.append(
                        f'<div class="book-btn-group">'
                        f'<a href="/codex/{sec_id.lower()}" class="book-btn scanned" title="Open Cached Codex">{badge_txt}</a>'
                        f'<button onclick="triggerScan(\'{wid}\', \'{b}\', \'{wtitle} — Book {b}\')" class="rescan-btn" title="Re-Scan with current parameters">↻</button>'
                        f'</div>'
                    )
                else:
                    book_buttons.append(
                        f'<button onclick="triggerScan(\'{wid}\', \'{b}\', \'{wtitle} — Book {b}\')" class="book-btn unscanned">'
                        f'Book {b}'
                        f'</button>'
                    )

            work_cards.append(f"""
            <article class="work-card">
                <header class="work-header">
                    <div>
                        <span class="work-title">{wtitle}</span>
                        <span class="lang-pill">{lang}</span>
                    </div>
                    <span class="progress-pill">{done_cnt} / {len(work["books"])} Scanned</span>
                </header>
                <div class="book-grid">
                    {"".join(book_buttons)}
                </div>
            </article>
            """)

        genre_sections.append(f"""
        <section class="genre-block">
            <h2 class="genre-heading">{html.escape(genre_title)}</h2>
            {"".join(work_cards)}
        </section>
        """)

    # Bundled Scanner Parameters Popover + Random Survey Button in Top Bar
    scan_controls_html = """
    <div class="settings-dropdown">
        <button class="nav-btn" onclick="toggleScanParams(event)">Scan Parameters ▾</button>
        <div id="scanParamsPopover" class="settings-popover" onclick="event.stopPropagation()">
            <div class="setting-row">
                <label>Sliding Window Size</label>
                <select id="winSizeSelect">
                    <option value="100">100 Words (Short Texts / Epitomes)</option>
                    <option value="140">140 Words (High Resolution)</option>
                    <option value="180" selected>180 Words (Standard Balance)</option>
                    <option value="240">240 Words (Broad Chapters)</option>
                </select>
            </div>
            <div class="setting-row">
                <label>Detection Sensitivity (Anomaly Cutoff)</label>
                <select id="snrSelect">
                    <option value="2.2">High Sensitivity (2.2σ — More Candidates)</option>
                    <option value="2.5">Moderate-High (2.5σ)</option>
                    <option value="2.8" selected>Standard Balanced (2.8σ Recommended)</option>
                    <option value="3.2">Strict / Conservative (3.2σ — Strongest Only)</option>
                </select>
            </div>
            <div style="font-size:11.5px;color:#c9b79c;line-height:1.4;">
                Not sure what Window Size or σ Sensitivity means?
                <a href="/guide" style="color:#d4a359;">Read the Field Guide →</a>
            </div>
        </div>
    </div>
    """

    navbar_html = render_top_navbar(active_page="archive", extra_controls_html=scan_controls_html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lost Text Finder — Grand Archive</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&family=Cinzel:wght@500;700&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=EB+Garamond:ital,wght@0,400;0,600;1,400&family=Inter:wght@400;600&display=swap" rel="stylesheet">
{SHARED_CODEX_CSS_AND_JS}
<style>
    .tome-sub {{
        font-size: 19px; font-style: italic;
        color: var(--text-muted); max-width: 740px; margin: 0 auto 18px auto;
    }}
    .genre-heading {{
        font-family: 'Cinzel', serif; font-size: 20px;
        color: var(--accent-gold);
        border-bottom: 2px solid var(--border-ornate);
        padding-bottom: 6px; margin: 30px 0 16px 0;
    }}
    .work-card {{
        background: var(--bg-card);
        border: 2px solid var(--border-ornate);
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }}
    .work-header {{
        background: var(--bg-bar); padding: 10px 18px;
        border-bottom: 1px solid var(--border-ornate);
        display: flex; justify-content: space-between; align-items: center;
        font-family: 'Cinzel', serif;
    }}
    .work-title {{ font-size: 18px; font-weight: 700; margin-right: 10px; }}
    .lang-pill {{
        font-size: 11px; padding: 2px 8px;
        background: var(--accent-gold); color: #fff; border-radius: 3px;
    }}
    .progress-pill {{ font-size: 13px; color: var(--text-muted); font-weight: 700; }}
    .book-grid {{ padding: 16px 18px; display: flex; flex-wrap: wrap; gap: 10px; }}
    .book-btn-group {{ display: inline-flex; align-items: stretch; }}
    .book-btn {{
        font-family: 'Cinzel', serif; font-size: 13px; font-weight: 700;
        padding: 7px 13px; border-radius: 3px; cursor: pointer;
        text-decoration: none; transition: all 0.15s ease;
        border: 1px solid var(--border-ornate);
    }}
    .book-btn.unscanned {{ background: var(--bg-page); color: var(--text-main); }}
    .book-btn.unscanned:hover {{ background: var(--accent-gold); color: #fff; border-color: var(--accent-gold); }}
    .book-btn.scanned {{
        background: var(--accent-gold); color: #fff9ee; border-color: var(--accent-gold);
        border-top-right-radius: 0; border-bottom-right-radius: 0;
    }}
    .book-btn.scanned:hover {{ filter: brightness(1.12); }}
    .rescan-btn {{
        background: var(--bg-bar); color: var(--text-main);
        border: 1px solid var(--accent-gold); border-left: none;
        padding: 0 8px; cursor: pointer; font-weight: 700;
        border-top-right-radius: 3px; border-bottom-right-radius: 3px;
    }}
    .rescan-btn:hover {{ background: #8b1e1e; color: #fff; }}

    #scanOverlay {{
        display: none; position: fixed; inset: 0; z-index: 999;
        background: rgba(18, 13, 9, 0.88);
        color: #f3e8d2; text-align: center;
        flex-direction: column; align-items: center; justify-content: center;
        font-family: 'Cinzel', serif;
    }}
    .spinner-seal {{
        width: 68px; height: 68px;
        border: 4px double #d4a359; border-top-color: transparent;
        border-radius: 50%; animation: spin 1.1s linear infinite;
        margin-bottom: 20px;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body class="border-ornate">

<div id="scanOverlay">
    <div class="spinner-seal"></div>
    <h2 id="overlayTitle" style="margin: 0 0 8px 0; color: #d4a359;">Scanning Ancient Manuscript...</h2>
    <p style="font-family: 'EB Garamond', serif; font-size: 19px; max-width: 520px; color: #d6c6ac;">
        Aligning Perseus TEI-XML sections, computing 3-channel stylometric divergence, and updating the Discovery Archive...
    </p>
</div>

{navbar_html}

<main class="tome-page">
    <header class="tome-header">
        <div class="tome-super">Perseus Greco-Roman Digital Library · Computational Philology</div>
        <h1 class="tome-title">Lost Text Finder</h1>
        <p class="tome-sub">
            Select any surviving Greek or Latin compilation book below to scan for uncredited fragments of lost histories, sea-voyage manuals (periploi), and embedded verse.
        </p>
        <div class="tome-stats">
            <span>Archive Progress: <strong>{scanned_books} / {total_books} Books Scanned</strong></span>
            <span>Uncredited Passages: <strong>{total_ghosts}</strong></span>
            <span>Extended Borrowings: <strong>{total_bounds}</strong></span>
            <a href="/guide" class="context-btn" style="text-decoration:none;">
                Read the Field Guide &amp; Glossary
            </a>
            <button class="context-btn" onclick="triggerRandomScan()">
                Scan Random Unanalyzed Book
            </button>
        </div>
    </header>

    {"".join(genre_sections)}
</main>

<script>
    function toggleScanParams(e) {{
        e.stopPropagation();
        document.getElementById('scanParamsPopover').classList.toggle('open');
    }}
    document.addEventListener('click', function(e) {{
        const pop = document.getElementById('scanParamsPopover');
        if (pop && !pop.contains(e.target)) pop.classList.remove('open');
    }});

    function triggerScan(workId, bookNum, label) {{
        const winSize = document.getElementById('winSizeSelect').value;
        const snr = document.getElementById('snrSelect').value;
        document.getElementById('overlayTitle').textContent = 'Scanning ' + label + '...';
        document.getElementById('scanOverlay').style.display = 'flex';
        window.location.href = `/scan?work=${{encodeURIComponent(workId)}}&book=${{encodeURIComponent(bookNum)}}&win=${{winSize}}&snr=${{snr}}`;
    }}

    function triggerRandomScan() {{
        const winSize = document.getElementById('winSizeSelect').value;
        const snr = document.getElementById('snrSelect').value;
        document.getElementById('overlayTitle').textContent = 'Selecting Random Unanalyzed Book...';
        document.getElementById('scanOverlay').style.display = 'flex';
        window.location.href = `/random?win=${{winSize}}&snr=${{snr}}`;
    }}
</script>
</body>
</html>
"""


def render_bookmarks_page_html() -> str:
    bookmarks = get_personal_bookmarks()
    navbar_html = render_top_navbar(active_page="bookmarks")

    # Group bookmarks by folder_tag
    grouped = {}
    for bm in bookmarks:
        grouped.setdefault(bm["folder_tag"], []).append(bm)

    groups_html = []
    for folder, items in grouped.items():
        cards = []
        for item in items:
            b_id = item["bookmark_id"]
            wtitle = html.escape(str(item["work_title"]))
            span = html.escape(str(item["cts_span"]))
            sec_low = str(item["sector_id"]).lower()
            snr_str = f"{item['peak_snr']:.2f}σ" if item["peak_snr"] > 0 else "Direct Excerpt"
            attr = html.escape(str(item["primary_attribution"]))
            note = html.escape(str(item["personal_note"]))
            eng = html.escape(str(item["english_text"]))
            saved_at = html.escape(str(item["saved_at"]))

            note_block = f'<div style="background:var(--bg-page);padding:10px 16px;border-left:3px solid var(--accent-gold);margin-bottom:12px;font-style:italic;"><strong>Personal Note:</strong> {note}</div>' if note else ""

            cards.append(f"""
            <article class="tome-card" id="bm-card-{b_id}">
                <header class="card-header">
                    <div>
                        <span class="passage-ref">{wtitle} — {span}</span>
                        <span class="badge badge-known">{html.escape(folder)}</span>
                    </div>
                    <div class="snr-pill">{snr_str} · Saved {saved_at}</div>
                </header>
                <div class="attribution-bar">
                    <strong>Attribution / Context:</strong> {attr}
                </div>
                <div class="parchment-passage">
                    {note_block}
                    <p class="drop-cap">{eng}</p>
                </div>
                <footer class="card-footer">
                    <a href="/codex/{sec_low}" class="context-btn" style="text-decoration:none;">
                        Open Source Book Codex ({item['sector_id']}) →
                    </a>
                    <button class="context-btn" style="color:#8b1e1e;border-color:#8b1e1e;" onclick="deleteBookmark({b_id})">
                        ✕ Remove Bookmark
                    </button>
                </footer>
            </article>
            """)

        groups_html.append(f"""
        <h2 style="font-family:'Cinzel',serif;color:var(--accent-gold);border-bottom:2px solid var(--border-ornate);padding-bottom:6px;margin-top:32px;">
            {html.escape(folder)} ({len(items)})
        </h2>
        {"".join(cards)}
        """)

    body_content = "".join(groups_html) if groups_html else (
        '<div style="padding:48px;text-align:center;border:1px dashed var(--border-ornate);font-style:italic;">'
        'You have not saved any personal bookmarks yet. Click <strong>"Bookmark Passage"</strong> on any discovery card or book section to save it to your local Florilegium.'
        '</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>My Personal Bookmarks — Lost Text Finder</title>
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&family=Cinzel:wght@500;700&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=EB+Garamond:ital,wght@0,400;0,600;1,400&family=Inter:wght@400;600&display=swap" rel="stylesheet">
{SHARED_CODEX_CSS_AND_JS}
</head>
<body class="border-ornate">
{navbar_html}
<main class="tome-page">
    <header class="tome-header">
        <div class="tome-super">Private Local Florilegium · Stored in data/personal_bookmarks.db</div>
        <h1 class="tome-title">My Saved Bookmarks</h1>
        <div class="tome-stats">
            <span>Total Saved Passages: <strong>{len(bookmarks)}</strong></span>
            <span>Privacy Status: <strong>100% Local &amp; Git-Ignored (Never Publicly Shared)</strong></span>
        </div>
    </header>
    {body_content}
</main>
<script>
    async function deleteBookmark(id) {{
        const resp = await fetch('/api/bookmark/delete?id=' + id, {{ method: 'POST' }});
        if (resp.ok) {{
            const card = document.getElementById('bm-card-' + id);
            if (card) card.remove();
        }}
    }}
</script>
</body>
</html>
"""

def _highlight_text(escaped_text: str, query: str) -> str:
    """Wraps case-insensitive matches of query in <mark class='search-highlight'> tags."""
    q_clean = query.strip()
    if not q_clean:
        return escaped_text
    pattern = re.compile(f"({re.escape(html.escape(q_clean))})", re.IGNORECASE)
    return pattern.sub(r'<mark class="search-highlight">\1</mark>', escaped_text)

def render_public_db_page_html(search_q: str = "", channel_f: str = "", tier: str = "extreme") -> str:
    if tier not in ("extreme", "moderate"):
        tier = "extreme"

    candidates, ext_cnt, mod_cnt = get_all_public_candidates(
        search_query=search_q,
        channel_filter=channel_f,
        tier=tier,
    )
    navbar_html = render_top_navbar(active_page="public")

    cards = []
    for idx, hit in enumerate(candidates, start=1):
        drawer_id = f"pub-bm-{idx}"
        sec_id = html.escape(str(hit["sector_id"]))
        sec_low = sec_id.lower()
        wtitle = _highlight_text(html.escape(str(hit["work_title"])), search_q)
        span = html.escape(str(hit["cts_span"]))
        snr = f"{hit['peak_snr']:.2f}σ"
        chan = html.escape(str(hit["dominant_channel"]).replace("_", " "))
        status = html.escape(str(hit["novelty_status"]))
        badge_cls = "badge-ghost" if status.startswith("UNCREDITED") else "badge-bound"
        match1 = _highlight_text(html.escape(str(hit["primary_attribution"])), search_q)
        match2 = _highlight_text(html.escape(str(hit["secondary_attribution"])), search_q)
        hiatus = f"{hit['hiatus_rate'] * 100:.1f}%"
        jsd = f"{hit['jsd']:.3f}"
        perip = f"{hit['periplus_density']:.1f}"
        eng = _highlight_text(html.escape(str(hit["english_text"])), search_q)

        bm_payload = html.escape(json.dumps({
            "sector_id": str(hit["sector_id"]),
            "work_title": str(hit["work_title"]),
            "cts_span": str(hit["cts_span"]),
            "peak_snr": float(hit["peak_snr"]),
            "dominant_channel": str(hit["dominant_channel"]),
            "primary_attribution": str(hit["primary_attribution"]),
            "english_text": str(hit["english_text"]),
        }))

        cards.append(f"""
        <article class="tome-card">
            <header class="card-header">
                <div>
                    <span class="passage-ref">{wtitle} ({span})</span>
                    <span class="badge {badge_cls}">{status}</span>
                </div>
                <div class="snr-pill">Anomaly Strength: {snr} · {chan}</div>
            </header>
            <div class="attribution-bar">
                <div><strong>1st Suspect Attribution:</strong> {match1} &nbsp;|&nbsp; <strong>2nd:</strong> {match2}</div>
                <div class="metrics-row">
                    <span>Vowel Hiatus: <strong>{hiatus}</strong></span> ·
                    <span>Particle JSD: <strong>{jsd}</strong></span> ·
                    <span>Periplus Index: <strong>{perip}</strong></span>
                </div>
            </div>
            <div class="parchment-passage">
                <p class="drop-cap">{eng}</p>
            </div>
            <footer class="card-footer">
                <button class="context-btn" onclick="toggleBookmarkDrawer('{drawer_id}')">Bookmark Passage</button>
                <a href="/codex/{sec_low}" class="context-btn" style="text-decoration:none;">Open Book Codex ({sec_id}) →</a>
            </footer>
            <div id="{drawer_id}" class="bookmark-drawer">
                <div class="bm-form-row">
                    <select class="bm-select">
                        <option value="General Interest">General Interest</option>
                        <option value="Nostoi & Mythic Lore">Nostoi &amp; Mythic Lore</option>
                        <option value="Sea-Voyage Periploi">Sea-Voyage Periploi</option>
                        <option value="Lost Historians">Lost Historians</option>
                    </select>
                    <input type="text" class="bm-input" placeholder="Private note...">
                    <button class="bm-save-btn" onclick='saveBookmark(this, {bm_payload}, "{drawer_id}")'>Save</button>
                </div>
            </div>
        </article>
        """)

    tier_label = (
        "3.0σ – 8.0σ+ (Extreme Statistical Anomalies)"
        if tier == "extreme"
        else "2.5σ – 3.0σ (Moderate Stylistic Shifts)"
    )
    cards_html = "\n".join(cards) if cards else (
        f'<div style="padding:40px;text-align:center;border:1px dashed var(--border-ornate);font-style:italic;">'
        f'No candidates found in tier <strong>{tier_label}</strong> matching your current filters.'
        f'</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Discovery Archive — Lost Text Finder</title>
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&family=Cinzel:wght@500;700&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=EB+Garamond:ital,wght@0,400;0,600;1,400&family=Inter:wght@400;600&display=swap" rel="stylesheet">
{SHARED_CODEX_CSS_AND_JS}
<style>
    .tier-radio-group {{
        display: flex;
        justify-content: center;
        gap: 14px;
        flex-wrap: wrap;
        margin-top: 20px;
    }}
    .tier-radio-label {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 18px;
        background: var(--bg-card);
        border: 2px solid var(--border-ornate);
        font-family: 'Cinzel', serif;
        font-size: 13.5px;
        font-weight: 700;
        cursor: pointer;
        border-radius: 4px;
        transition: all 0.15s ease;
    }}
    .tier-radio-label.active-tier {{
        background: var(--accent-gold);
        color: #fff9ee;
        border-color: var(--accent-gold);
    }}
    .tier-radio-label input[type="radio"] {{
        accent-color: #fff9ee;
        cursor: pointer;
    }}
</style>
</head>
<body class="border-ornate">
{navbar_html}
<main class="tome-page">
    <header class="tome-header">
        <div class="tome-super">Shared Open SQLite Registry · data/public_candidates.db</div>
        <h1 class="tome-title">Discovery Archive</h1>
        <div class="tome-stats">
            <span>Extreme Anomalies (3.0σ+): <strong>{ext_cnt}</strong></span>
            <span>Moderate Shifts (2.5σ–3.0σ): <strong>{mod_cnt}</strong></span>
            <span>Showing: <strong>{len(candidates)} Passages</strong></span>
        </div>

        <form id="pubFilterForm" method="GET" action="/public-db">
            <!-- Two-Option Radio Toggle for Anomaly Tier -->
            <div class="tier-radio-group">
                <label class="tier-radio-label {'active-tier' if tier == 'extreme' else ''}">
                    <input type="radio" name="tier" value="extreme" {'checked' if tier == 'extreme' else ''} onchange="document.getElementById('pubFilterForm').submit()">
                    1. 3.0σ – 8.0σ+: Extreme Statistical Anomalies ({ext_cnt})
                </label>
                <label class="tier-radio-label {'active-tier' if tier == 'moderate' else ''}">
                    <input type="radio" name="tier" value="moderate" {'checked' if tier == 'moderate' else ''} onchange="document.getElementById('pubFilterForm').submit()">
                    2. 2.5σ – 3.0σ: Moderate Stylistic Shift — Worth Inspecting ({mod_cnt})
                </label>
            </div>

            <div style="margin-top:16px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
                <input type="text" name="q" value="{html.escape(search_q)}" placeholder="Search keywords, authors, or passages (e.g. 'Cyprus', 'pirates', 'Ephorus')..." class="bm-input" style="max-width:420px;">
                <select name="channel" class="bm-select" onchange="document.getElementById('pubFilterForm').submit()">
                    <option value="">All Discovery Channels</option>
                    <option value="LOST_HISTORIAN" {'selected' if channel_f == 'LOST_HISTORIAN' else ''}>Lost Historian Channel</option>
                    <option value="LOST_PERIPLUS" {'selected' if channel_f == 'LOST_PERIPLUS' else ''}>Lost Periplus (Sea-Voyage) Channel</option>
                    <option value="LOST_VERSE_MYTH" {'selected' if channel_f == 'LOST_VERSE_MYTH' else ''}>Lost Verse / Mythic Channel</option>
                </select>
                <button type="submit" class="bm-save-btn">Search Database</button>
                <a href="/public-db" class="context-btn" style="text-decoration:none;display:inline-flex;align-items:center;">Reset</a>
            </div>
        </form>
    </header>
    {cards_html}
</main>
</body>
</html>
"""


def render_field_guide_html() -> str:
    navbar_html = render_top_navbar(active_page="guide")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Field Guide &amp; Manual — Lost Text Finder</title>
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&family=Cinzel:wght@500;700&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=EB+Garamond:ital,wght@0,400;0,600;1,400&family=Inter:wght@400;600&display=swap" rel="stylesheet">
{SHARED_CODEX_CSS_AND_JS}
<style>
    .guide-section {{
        background: var(--bg-card);
        border: 2px solid var(--border-ornate);
        padding: 24px 30px;
        margin-bottom: 26px;
        font-size: var(--font-size);
        line-height: var(--line-height);
    }}
    .guide-section h2 {{
        font-family: 'Cinzel', serif;
        color: var(--accent-gold);
        margin-top: 0;
        border-bottom: 1px solid var(--border-ornate);
        padding-bottom: 8px;
    }}
    .term-grid {{
        display: grid;
        grid-template-columns: 230px 1fr;
        gap: 14px 20px;
        margin-top: 14px;
    }}
    .term-key {{
        font-family: 'Cinzel', serif;
        font-weight: 700;
        color: var(--accent-gold);
    }}
</style>
</head>
<body class="border-ornate">
{navbar_html}
<main class="tome-page">
    <header class="tome-header">
        <div class="tome-super">Codex Philologica · User Manual &amp; Forensic Glossary</div>
        <h1 class="tome-title">Field Guide &amp; Reference Manual</h1>
        <div class="tome-stats">
            <span>How Computational Stylometry Recovers Lost Ancient Literature</span>
        </div>
    </header>

    <section class="guide-section">
        <h2>1. How the Scanner Works </h2>
        <p>
            Over 90% of ancient Greek and Roman literature has been lost. However, surviving encyclopedic writers—such as <strong>Strabo</strong>, <strong>Diodorus Siculus</strong>, <strong>Pausanias</strong>, <strong>Athenaeus</strong>, and <strong>Pliny the Elder</strong>—sat in ancient libraries with hundreds of now-vanished scrolls and copied long passages from them directly into their own chapters.
        </p>
        <p>
            Because ancient manuscripts lacked modern quotation marks and footnotes, compilers frequently copied or closely paraphrased a lost source for pages without crediting it. While a human reader focuses on <em>what</em> the words mean, this pipeline measures <strong>subconscious mechanical habits</strong> in the original Greek and Latin text to detect the exact paragraphs where a different author's voice takes over.
        </p>
    </section>

    <section class="guide-section">
        <h2>2. Understanding the Three Finding Types</h2>
        <div class="term-grid">
            <div class="term-key">★ Uncredited Passage</div>
            <div>
                <strong>Highest Discovery Priority.</strong> The Greek or Latin text inside this passage exhibits a strong statistical shift away from the book's host author, yet <em>no lost source or author is named anywhere nearby</em>. These are prime candidates for unrecognized borrowings from lost works.
            </div>
            <div class="term-key">◆ Extended Borrowing</div>
            <div>
                <strong>Unmarked Continuation Past a Quote.</strong> The compiler explicitly named a lost author (e.g., <em>"As Artemidorus says..."</em>) one to three sections earlier, and modern translators closed the quotation marks—but our scanner proves the foreign author's statistical fingerprint continues into these subsequent paragraphs.
            </div>
            <div class="term-key">● Explicit Citation</div>
            <div>
                <strong>Known Reference Quote.</strong> The compiler explicitly names a source right inside this section. The scanner uses these known quotes to calibrate its <strong>Suspect Lineup</strong> so it can identify who wrote the Uncredited Passages.
            </div>
        </div>
    </section>

    <section class="guide-section">
        <h2>3. Glossary of Scanner Controls &amp; Metrics</h2>
        <div class="term-grid">
            <div class="term-key">Peak Anomaly Strength (σ / Sigma)</div>
            <div>
                Measures how strongly a passage stands out from the host author's normal baseline, expressed in <strong>standard deviations (σ)</strong> above background noise.
                <ul>
                    <li><strong>0.0σ – 2.0σ:</strong> Normal host author writing style.</li>
                    <li><strong>2.5σ – 3.0σ:</strong> Moderate stylistic shift (worth inspecting).</li>
                    <li><strong>3.0σ – 8.0σ+:</strong> Extreme statistical anomaly—almost certainly copied from a foreign scroll or specialized logbook.</li>
                </ul>
            </div>
            <div class="term-key">Detection Sensitivity (Cutoff, e.g. 2.8σ)</div>
            <div>
                The minimum Anomaly Strength (σ) required for the scanner to flag a passage. Lowering the cutoff to <strong>2.2σ (High Sensitivity)</strong> surfaces more subtle borrowings; raising it to <strong>3.2σ (Strict)</strong> shows only the most extreme outliers.
            </div>
            <div class="term-key">Sliding Window (e.g. 180w)</div>
            <div>
                The scanner reads the book through a moving magnifying glass that is <strong>180 words wide</strong>, stepping forward 45 words at a time. Smaller windows (100w) spot brief mythic quotes; larger windows (240w) spot multi-page historical excerpts.
            </div>
            <div class="term-key">Vowel Hiatus (%)</div>
            <div>
                The percentage of adjacent Greek or Latin words where one word ends with a vowel and the next word starts with a vowel. Normal prose has a <strong>10%–15%</strong> vowel collision rate. However, certain lost 4th-century BCE historians (like <strong>Ephorus</strong> and <strong>Theopompus</strong>) strictly avoided vowel collisions. When Hiatus plunges below <strong>3%–5%</strong>, the compiler is copying a hiatus-averse historian verbatim.
            </div>
            <div class="term-key">Particle JSD (0.000 – 1.000)</div>
            <div>
                <strong>Jensen-Shannon Divergence</strong> on subconscious "glue words" (Greek <em>de, men, gar, oun, te</em>; Latin <em>autem, enim, igitur, atque</em>). Every writer has an involuntary habit of how often they use each connector. A high JSD score means the glue-word ratio in this passage belongs to a different writer.
            </div>
            <div class="term-key">Periplus Index</div>
            <div>
                Measures the density of ancient navigator logbook vocabulary per 100 words: sailing distances in <em>stadia</em> or <em>Roman miles</em>, harbors (<em>limen/portus</em>), headlands, anchorages, and sequential coastal markers (<em>"next in order", "from X to Y"</em>).
            </div>
            <div class="term-key">3-Channel Signal Curve</div>
            <div>
                The three-panel chart plotting <strong>Channel 1 (Lost Historian)</strong>, <strong>Channel 2 (Lost Periplus Sea-Log)</strong>, and <strong>Channel 3 (Embedded Verse / Mythic Meter)</strong> across the entire book from start to finish.
            </div>
        </div>
    </section>
</main>
</body>
</html>
"""


class CodexRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_html(self, html_str: str, status: int = 200):
        data = html_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send_html(render_grand_archive_html())
            return

        if path == "/bookmarks":
            self._send_html(render_bookmarks_page_html())
            return

        if path == "/public-db":
            q = params.get("q", [""])[0]
            ch = params.get("channel", [""])[0]
            tier = params.get("tier", ["extreme"])[0]
            self._send_html(render_public_db_page_html(search_q=q, channel_f=ch, tier=tier))
            return

        if path == "/guide":
            self._send_html(render_field_guide_html())
            return

        if path == "/shutdown":
            bye_html = """<!DOCTYPE html>
            <html><head><meta charset="UTF-8"><title>Archive Closed</title>
            <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@700&family=EB+Garamond&display=swap" rel="stylesheet">
            </head><body style="background:#1b1612;color:#f3e8d2;font-family:'EB Garamond',serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="background:#261e17;border:4px double #9b7646;padding:48px 64px;text-align:center;max-width:560px;">
                <h1 style="font-family:'Cinzel',serif;color:#d4a359;margin-top:0;">Grand Archive Closed</h1>
                <p style="font-size:20px;line-height:1.6;">The Python Codex Server has shut down cleanly and released its port. You may now close this browser tab.</p>
            </div></body></html>"""
            self._send_html(bye_html)
            print("\n[*] Exit button clicked in browser — shutting down Grand Archive Server cleanly.")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        if path.startswith("/codex/"):
            sec_low = path.replace("/codex/", "").strip().lower()
            codex_file = Path("candidates") / f"{sec_low}_codex.html"
            if codex_file.exists():
                html_text = codex_file.read_text(encoding="utf-8")
                # Upgrade older cached files if they lack the new bundled navbar
                if "toggleSettingsMenu" not in html_text:
                    work_part, book_part = sec_low.rsplit("_", 1)
                    self.send_response(302)
                    self.send_header("Location", f"/scan?work={work_part}&book={int(book_part)}&win=180&snr=2.8")
                    self.end_headers()
                    return
                self._send_html(html_text)
                return

        if path == "/random":
            history = _load_history_map()
            unscanned = []
            for w in CORPUS_REGISTRY:
                for b in w["books"]:
                    if f"{w['id'].upper()}_{b.zfill(2)}" not in history:
                        unscanned.append((w["id"], b))
            if not unscanned:
                w = random.choice(CORPUS_REGISTRY)
                work_id, book_num = w["id"], random.choice(w["books"])
            else:
                work_id, book_num = random.choice(unscanned)

            win = params.get("win", ["180"])[0]
            snr = params.get("snr", ["2.8"])[0]
            self.send_response(302)
            self.send_header("Location", f"/scan?work={work_id}&book={book_num}&win={win}&snr={snr}")
            self.end_headers()
            return

        if path == "/scan":
            work_id = params.get("work", ["strabo"])[0]
            book_num = params.get("book", ["14"])[0]
            win_size = int(params.get("win", ["180"])[0])
            snr_thresh = float(params.get("snr", ["2.8"])[0])

            work = next((w for w in CORPUS_REGISTRY if w["id"] == work_id), CORPUS_REGISTRY[0])
            sec_id = f"{work['id'].upper()}_{book_num.zfill(2)}"
            target = {**work, "selected_book": book_num, "sector_id": sec_id}

            try:
                aligned_csv = ingest_target_book(target)
                scan_and_attribute(
                    aligned_csv,
                    window_size=win_size,
                    snr_threshold=snr_thresh,
                    headless=True,
                )
                self.send_response(302)
                self.send_header("Location", f"/codex/{sec_id.lower()}")
                self.end_headers()
            except Exception as exc:
                err_msg = f"<h2>Error scanning {sec_id}</h2><pre>{html.escape(str(exc))}</pre><p><a href='/'>Return to Grand Archive</a></p>"
                self._send_html(err_msg, status=500)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/api/bookmark":
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8")
            data = json.loads(raw_body)
            add_personal_bookmark(
                sector_id=str(data.get("sector_id", "")),
                work_title=str(data.get("work_title", "")),
                cts_span=str(data.get("cts_span", "")),
                peak_snr=float(data.get("peak_snr", 0.0)),
                dominant_channel=str(data.get("dominant_channel", "")),
                primary_attribution=str(data.get("primary_attribution", "")),
                folder_tag=str(data.get("folder_tag", "General Interest")),
                personal_note=str(data.get("personal_note", "")),
                english_text=str(data.get("english_text", "")),
            )
            self._send_html('{"status":"ok"}', status=200)
            return

        if path == "/api/bookmark/delete":
            bm_id = int(params.get("id", ["0"])[0])
            delete_personal_bookmark(bm_id)
            self._send_html('{"status":"deleted"}', status=200)
            return

        self.send_response(404)
        self.end_headers()


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


def launch_codex_app(port: int = 8765):
    init_databases()
    server = None
    for candidate_port in range(port, port + 15):
        try:
            server = ReusableHTTPServer(("127.0.0.1", candidate_port), CodexRequestHandler)
            port = candidate_port
            break
        except OSError:
            continue

    if server is None:
        raise RuntimeError("Could not bind local server on ports 8765–8779.")

    url = f"http://127.0.0.1:{port}/"
    print("\n" + "═" * 78)
    print(" LOST TEXT FINDER — GRAND ARCHIVE CODEX SERVER ACTIVE")
    print(f"    URL: {url}")
    print("    (Click '⏻ Exit' in the browser or press Ctrl+C here to quit)")
    print("═" * 78)
    open_file_cross_platform(Path(url))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down Grand Archive Codex Server.")
    finally:
        server.server_close()