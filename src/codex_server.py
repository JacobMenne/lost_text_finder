import html
import os
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import pandas as pd

from catalog import CORPUS_REGISTRY, SCAN_LOG_PATH
from ingest import ingest_target_book
from scanner import scan_and_attribute
from codex_reader import open_file_cross_platform


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

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lost Text Finder — Grand Archive</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&family=Cinzel:wght@500;700&family=EB+Garamond:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
    :root {{
        --bg-outer: #1b1612;
        --bg-page: #f3e8d2;
        --bg-card: #efe0c4;
        --bg-bar: #e5d2af;
        --text-main: #2b1d0e;
        --text-muted: #5e472d;
        --accent-gold: #8c581c;
        --border-ornate: #9b7646;
    }}
    body.theme-illuminated {{
        --bg-outer: #261c14; --bg-page: #fbf6ec; --bg-card: #f5ebd6;
        --bg-bar: #ead8b8; --text-main: #1f140a; --text-muted: #5a4228;
        --accent-gold: #9a6b1f; --border-ornate: #b58938;
    }}
    body.theme-obsidian {{
        --bg-outer: #0b0c10; --bg-page: #16181d; --bg-card: #1e2129;
        --bg-bar: #262a34; --text-main: #e6dcc8; --text-muted: #a89f8d;
        --accent-gold: #d4a359; --border-ornate: #6e552f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0; padding: 0;
        background-color: var(--bg-outer);
        color: var(--text-main);
        font-family: 'EB Garamond', Georgia, serif;
    }}
    .codex-toolbar {{
        position: sticky; top: 0; z-index: 100;
        background: #14100d; color: #e8dcc4;
        border-bottom: 2px solid #6b4e2b;
        padding: 12px 24px;
        display: flex; flex-wrap: wrap; gap: 18px;
        align-items: center; justify-content: space-between;
        font-family: 'Cinzel', serif; font-size: 13px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.45);
    }}
    .toolbar-group {{ display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }}
    .codex-toolbar select {{
        background: #261e17; color: #f3e8d2;
        border: 1px solid #8c683b; padding: 5px 9px;
        border-radius: 4px; font-family: inherit; cursor: pointer;
    }}
    .random-survey-btn {{
        background: #8c581c; color: #fff8eb;
        border: 1px solid #e09f5a; padding: 7px 15px;
        border-radius: 4px; font-family: 'Cinzel', serif;
        font-weight: 700; cursor: pointer; font-size: 13px;
        transition: all 0.15s ease;
    }}
    .random-survey-btn:hover {{ background: #a86b24; transform: translateY(-1px); }}

    .exit-server-btn {{
        background: #6e1a1a; color: #fff8eb;
        border: 1px solid #d47a59; padding: 7px 14px;
        border-radius: 4px; font-family: 'Cinzel', serif;
        font-weight: 700; cursor: pointer; font-size: 13px;
        text-decoration: none; transition: all 0.15s ease;
    }}
    .exit-server-btn:hover {{ background: #942222; }}

    .tome-page {{
        max-width: 1060px;
        margin: 34px auto 64px auto;
        padding: 48px 54px;
        background-color: var(--bg-page);
        background-image:
            radial-gradient(rgba(139, 98, 43, 0.07) 1px, transparent 0),
            linear-gradient(to right, rgba(90, 58, 24, 0.12) 0%, rgba(0,0,0,0) 6%, rgba(0,0,0,0) 94%, rgba(90, 58, 24, 0.12) 100%);
        background-size: 24px 24px, 100% 100%;
        border: 6px double var(--border-ornate);
        outline: 8px solid var(--bg-page);
        box-shadow: 0 18px 50px rgba(0, 0, 0, 0.65), inset 0 0 60px rgba(120, 82, 34, 0.14);
    }}
    .tome-header {{
        text-align: center;
        border-bottom: 3px double var(--border-ornate);
        padding-bottom: 24px; margin-bottom: 32px;
    }}
    .tome-super {{
        font-family: 'Cinzel', serif; letter-spacing: 3px;
        text-transform: uppercase; font-size: 13px;
        color: var(--accent-gold); margin-bottom: 8px;
    }}
    .tome-title {{
        font-family: 'Cinzel Decorative', 'Cinzel', serif;
        font-size: 38px; margin: 6px 0 10px 0;
    }}
    .tome-sub {{
        font-size: 19px; font-style: italic;
        color: var(--text-muted); max-width: 740px; margin: 0 auto 18px auto;
    }}
    .tome-stats {{
        display: flex; justify-content: center; gap: 28px; flex-wrap: wrap;
        font-family: 'Cinzel', serif; font-size: 14px;
        background: var(--bg-bar); padding: 10px 20px;
        border: 1px solid var(--border-ornate);
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
        background: var(--bg-bar);
        padding: 10px 18px;
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
    .book-grid {{
        padding: 16px 18px;
        display: flex; flex-wrap: wrap; gap: 10px;
    }}
    .book-btn-group {{ display: inline-flex; align-items: stretch; }}
    .book-btn {{
        font-family: 'Cinzel', serif; font-size: 13px; font-weight: 700;
        padding: 7px 13px; border-radius: 3px; cursor: pointer;
        text-decoration: none; transition: all 0.15s ease;
        border: 1px solid var(--border-ornate);
    }}
    .book-btn.unscanned {{
        background: var(--bg-page); color: var(--text-main);
    }}
    .book-btn.unscanned:hover {{
        background: var(--accent-gold); color: #fff; border-color: var(--accent-gold);
    }}
    .book-btn.scanned {{
        background: var(--accent-gold); color: #fff9ee;
        border-color: var(--accent-gold);
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
<body>

<div id="scanOverlay">
    <div class="spinner-seal"></div>
    <h2 id="overlayTitle" style="margin: 0 0 8px 0; color: #d4a359;">Scanning Ancient Manuscript...</h2>
    <p style="font-family: 'EB Garamond', serif; font-size: 19px; max-width: 520px; color: #d6c6ac;">
        Aligning Perseus TEI-XML sections, computing 3-channel stylometric divergence (JSD, vowel hiatus, &amp; metrical wave), and matching Suspect Lineup via Burrows' Delta...
    </p>
</div>

<nav class="codex-toolbar">
    <div class="toolbar-group">
        <strong>🏛 GRAND ARCHIVE</strong>
        <label>Surface:
            <select onchange="updateTheme(this.value)">
                <option value="default">Aged Parchment Tome</option>
                <option value="theme-illuminated">Illuminated Vellum</option>
                <option value="theme-obsidian">Alexandria Night</option>
            </select>
        </label>
        <label>Window Size:
            <select id="winSizeSelect">
                <option value="100">100 Words (Short Texts / Epitomes)</option>
                <option value="140">140 Words (High Res)</option>
                <option value="180" selected>180 Words (Standard)</option>
                <option value="240">240 Words (Broad)</option>
            </select>
        </label>
        <label>SNR Cutoff:
            <select id="snrSelect">
                <option value="2.2">2.2σ (Deep Probe)</option>
                <option value="2.5">2.5σ (Sensitive)</option>
                <option value="2.8" selected>2.8σ (Balanced)</option>
                <option value="3.2">3.2σ (Strict)</option>
            </select>
        </label>
    </div>
    <div class="toolbar-group">
        <button class="random-survey-btn" onclick="triggerRandomScan()">
            🎲 Scan Random Unanalyzed Book
        </button>
        <a href="/shutdown" class="exit-server-btn" title="Shut down Python server and exit cleanly">
            ⏻ Exit Program
        </a>
    </div>
</nav>

<main class="tome-page">
    <header class="tome-header">
        <div class="tome-super">Perseus Greco-Roman Digital Library · Computational Philology</div>
        <h1 class="tome-title">Lost Text Finder</h1>
        <p class="tome-sub">
            Select any surviving Greek or Latin compilation book below to run a 3-channel stylometric anomaly scan for uncredited fragments of lost histories, sea-voyage manuals (periploi), and embedded verse.
        </p>
        <div class="tome-stats">
            <span>Archive Progress: <strong>{scanned_books} / {total_books} Books Scanned</strong></span>
            <span>Uncredited Passages Cataloged: <strong>{total_ghosts}</strong></span>
            <span>Extended Borrowings Cataloged: <strong>{total_bounds}</strong></span>
        </div>
    </header>

    {"".join(genre_sections)}
</main>

<script>
    function updateTheme(cls) {{
        document.body.classList.remove('theme-illuminated', 'theme-obsidian');
        if (cls !== 'default') document.body.classList.add(cls);
    }}

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
        document.getElementById('overlayTitle').textContent = 'Selecting Random Unanalyzed Sector...';
        document.getElementById('scanOverlay').style.display = 'flex';
        window.location.href = `/random?win=${{winSize}}&snr=${{snr}}`;
    }}
</script>
</body>
</html>
"""


class CodexRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            html_bytes = render_grand_archive_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)
            return

        if path == "/shutdown":
            bye_html = """<!DOCTYPE html>
            <html><head><meta charset="UTF-8"><title>Archive Closed</title>
            <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@700&family=EB+Garamond&display=swap" rel="stylesheet">
            </head><body style="background:#1b1612;color:#f3e8d2;font-family:'EB Garamond',serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="background:#261e17;border:4px double #9b7646;padding:48px 64px;text-align:center;max-width:560px;">
                <h1 style="font-family:'Cinzel',serif;color:#d4a359;margin-top:0;">🏛 Grand Archive Closed</h1>
                <p style="font-size:20px;line-height:1.6;">The Python Codex Server has shut down cleanly and released its port. You may now close this browser tab.</p>
            </div></body></html>""".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(bye_html)))
            self.end_headers()
            self.wfile.write(bye_html)
            print("\n[*] Exit button clicked in browser — shutting down Grand Archive Server cleanly.")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        if path.startswith("/codex/"):
            sec_low = path.replace("/codex/", "").strip().lower()
            codex_file = Path("candidates") / f"{sec_low}_codex.html"
            if codex_file.exists():
                html_text = codex_file.read_text(encoding="utf-8")
                if 'class="archive-home-btn"' not in html_text:
                    html_text = html_text.replace(
                        "<strong>📜 CODEX STYLING:</strong>",
                        '<a href="/" style="background:#8c581c;color:#fff8eb;text-decoration:none;padding:6px 14px;border-radius:4px;border:1px solid #d4a359;font-weight:700;">🏛 Grand Archive</a>',
                    )
                data = html_text.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
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
                data = err_msg.encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(data)
            return

        self.send_response(404)
        self.end_headers()


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


def launch_codex_app(port: int = 8765):
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
    print(" 📜 LOST TEXT FINDER — GRAND ARCHIVE CODEX SERVER ACTIVE")
    print(f"    URL: {url}")
    print("    (Click '⏻ Exit Program' in the browser or press Ctrl+C here to quit)")
    print("═" * 78)
    open_file_cross_platform(Path(url))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down Grand Archive Codex Server.")
    finally:
        server.server_close()