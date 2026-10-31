import base64
import html
import os
import sys
import subprocess
from pathlib import Path
import webbrowser
import pandas as pd


def _encode_image_base64(png_path: Path) -> str:
    if not png_path.exists():
        return ""
    with open(png_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def open_file_cross_platform(filepath: Path):
    target = str(filepath) if str(filepath).startswith("http") else filepath.resolve().as_uri()
    try:
        if sys.platform.startswith("linux"):
            arg = str(filepath) if str(filepath).startswith("http") else str(filepath.resolve())
            subprocess.Popen(
                ["xdg-open", arg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        elif sys.platform == "darwin":
            arg = str(filepath) if str(filepath).startswith("http") else str(filepath.resolve())
            subprocess.Popen(["open", arg])
            return
        elif sys.platform.startswith("win"):
            arg = str(filepath) if str(filepath).startswith("http") else str(filepath.resolve())
            os.startfile(arg)  # type: ignore[attr-defined]
            return
    except Exception:
        pass

    webbrowser.open(target)


SHARED_CODEX_CSS_AND_JS = """
<style>
    :root {
        --bg-outer: #1b1612;
        --bg-page: #f3e8d2;
        --bg-card: #efe0c4;
        --bg-bar: #e5d2af;
        --text-main: #2b1d0e;
        --text-muted: #5e472d;
        --accent-gold: #8c581c;
        --border-ornate: #9b7646;
        --badge-ghost: #8b1e1e;
        --badge-bound: #8f570d;
        --badge-known: #1f5c3a;
        --reader-font: 'EB Garamond', Georgia, serif;
        --font-size: 20px;
        --line-height: 1.75;
        --page-max-width: 980px;
        --page-padding: 50px;
    }

    body.theme-illuminated {
        --bg-outer: #261c14; --bg-page: #fbf6ec; --bg-card: #f5ebd6;
        --bg-bar: #ead8b8; --text-main: #1f140a; --text-muted: #5a4228;
        --accent-gold: #9a6b1f; --border-ornate: #b58938;
    }

    body.theme-obsidian {
        --bg-outer: #0b0c10; --bg-page: #16181d; --bg-card: #1e2129;
        --bg-bar: #262a34; --text-main: #e6dcc8; --text-muted: #a89f8d;
        --accent-gold: #d4a359; --border-ornate: #6e552f;
    }

    body.theme-academic {
        --bg-outer: #e5e7eb; --bg-page: #ffffff; --bg-card: #f9fafb;
        --bg-bar: #f3f4f6; --text-main: #111827; --text-muted: #4b5563;
        --accent-gold: #1e3a8a; --border-ornate: #d1d5db;
    }

    * { box-sizing: border-box; }

    body {
        margin: 0; padding: 0;
        background-color: var(--bg-outer);
        color: var(--text-main);
        font-family: var(--reader-font);
        transition: background-color 0.2s ease, color 0.2s ease;
    }

    /* Streamlined Top Navigation Bar */
    .codex-toolbar {
        position: sticky; top: 0; z-index: 200;
        background: #14100d; color: #e8dcc4;
        border-bottom: 2px solid #6b4e2b;
        padding: 10px 24px;
        display: flex; flex-wrap: wrap; gap: 14px;
        align-items: center; justify-content: space-between;
        font-family: 'Cinzel', Georgia, serif; font-size: 13px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.45);
    }

    .toolbar-group { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

    .nav-btn {
        background: #261e17; color: #f3e8d2;
        text-decoration: none; padding: 7px 13px;
        border-radius: 4px; border: 1px solid #7a5a32;
        font-family: 'Cinzel', serif; font-weight: 700; font-size: 12.5px;
        cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
        transition: all 0.15s ease;
    }
    .nav-btn:hover, .nav-btn.active-nav {
        background: #8c581c; color: #fff; border-color: #d4a359;
    }
    .nav-btn.exit-btn {
        background: #5e1919; border-color: #b85d43;
    }
    .nav-btn.exit-btn:hover { background: #8b1e1e; }

    /* Bundled Appearance Settings Dropdown Popover */
    .settings-dropdown { position: relative; display: inline-block; }

    .settings-popover {
        display: none;
        position: absolute; right: 0; top: calc(100% + 8px);
        width: 320px; background: #1c1611; color: #f3e8d2;
        border: 2px solid #9b7646; border-radius: 6px;
        padding: 16px 18px; z-index: 300;
        box-shadow: 0 12px 32px rgba(0,0,0,0.75);
        font-family: 'Cinzel', serif; font-size: 12.5px;
    }
    .settings-popover.open { display: block; }

    .setting-row {
        display: flex; flex-direction: column; gap: 5px;
        margin-bottom: 13px;
    }
    .setting-row:last-child { margin-bottom: 0; }
    .setting-row label { color: #d4a359; font-weight: 700; display: flex; justify-content: space-between; }

    .settings-popover select, .settings-popover input[type="range"] {
        width: 100%; background: #2b221a; color: #f3e8d2;
        border: 1px solid #8c683b; padding: 6px 8px;
        border-radius: 4px; font-family: inherit; cursor: pointer;
    }

    /* Main Parchment Tome Container */
    .tome-page {
        max-width: var(--page-max-width);
        margin: 32px auto 64px auto;
        padding: var(--page-padding);
        background-color: var(--bg-page);
        background-image:
            radial-gradient(rgba(139, 98, 43, 0.07) 1px, transparent 0),
            linear-gradient(to right, rgba(90, 58, 24, 0.12) 0%, rgba(0,0,0,0) 6%, rgba(0,0,0,0) 94%, rgba(90, 58, 24, 0.12) 100%);
        background-size: 24px 24px, 100% 100%;
        border: 3px double var(--border-ornate);
        outline: 8px solid var(--bg-page);
        box-shadow: 0 18px 50px rgba(0, 0, 0, 0.65), inset 0 0 60px rgba(120, 82, 34, 0.14);
        transition: all 0.2s ease;
    }
    body.border-ornate .tome-page { border: 6px double var(--border-ornate); }
    body.border-minimal .tome-page {
        border: 1px solid var(--border-ornate);
        background-image: none;
        box-shadow: 0 6px 20px rgba(0,0,0,0.2);
    }

    .tome-header {
        text-align: center;
        border-bottom: 3px double var(--border-ornate);
        padding-bottom: 22px; margin-bottom: 26px;
    }
    .tome-super {
        font-family: 'Cinzel', serif; letter-spacing: 3px;
        text-transform: uppercase; font-size: 13px;
        color: var(--accent-gold); margin-bottom: 8px;
    }
    .tome-title {
        font-family: 'Cinzel Decorative', 'Cinzel', serif;
        font-size: 34px; margin: 6px 0 12px 0; color: var(--text-main);
    }
    .tome-stats {
        display: flex; justify-content: center; gap: 22px; flex-wrap: wrap;
        font-family: 'Cinzel', serif; font-size: 14px; color: var(--text-muted);
    }
    .help-link {
        color: var(--accent-gold); text-decoration: underline; font-weight: 700; cursor: pointer;
    }

    /* Candidate Tome Cards */
    .tome-card {
        background: var(--bg-card);
        border: 2px solid var(--border-ornate);
        margin-bottom: 28px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.12);
    }
    .card-header {
        background: var(--bg-bar); padding: 12px 20px;
        border-bottom: 1px solid var(--border-ornate);
        display: flex; justify-content: space-between; align-items: center;
        flex-wrap: wrap; gap: 10px; font-family: 'Cinzel', serif;
    }
    .passage-ref { font-size: 18px; font-weight: 700; margin-right: 12px; }
    .badge {
        font-size: 11px; padding: 3px 9px; border-radius: 3px;
        color: #fff; font-family: 'Cinzel', serif; letter-spacing: 0.6px;
    }
    .badge-ghost { background: var(--badge-ghost); }
    .badge-bound { background: var(--badge-bound); }
    .badge-known { background: var(--badge-known); }
    .snr-pill { font-weight: 700; color: var(--accent-gold); font-size: 15px; }

    .attribution-bar {
        padding: 12px 20px; border-bottom: 1px dashed var(--border-ornate);
        font-size: 15px; line-height: 1.5; color: var(--text-muted);
    }
    .metrics-row { margin-top: 6px; font-size: 14px; }

    .parchment-passage {
        padding: 24px 28px;
        font-size: var(--font-size); line-height: var(--line-height);
        text-align: justify;
    }
    .parchment-passage p { margin: 0; }
    .drop-cap::first-letter {
        float: left; font-family: 'Cinzel Decorative', 'Cinzel', serif;
        font-size: 3.1em; line-height: 0.82;
        padding-right: 10px; padding-top: 4px;
        color: var(--accent-gold); font-weight: 700;
    }

    .card-footer {
        padding: 10px 20px; border-top: 1px solid var(--border-ornate);
        display: flex; justify-content: space-between; align-items: center;
        flex-wrap: wrap; gap: 10px; background: var(--bg-bar);
    }
    .context-btn {
        font-family: 'Cinzel', serif; font-size: 12.5px;
        background: transparent; color: var(--accent-gold);
        border: 1px solid var(--accent-gold); padding: 6px 12px;
        cursor: pointer; font-weight: 700; border-radius: 3px;
    }
    .context-btn:hover { background: var(--accent-gold); color: #fff; }

    /* Inline Bookmark Drawer */
    .bookmark-drawer {
        display: none; padding: 14px 20px;
        background: var(--bg-page); border-top: 1px dashed var(--border-ornate);
        font-family: 'Cinzel', serif; font-size: 13px;
    }
    .bookmark-drawer.open { display: block; }
    .bm-form-row {
        display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
    }
    .bm-input, .bm-select {
        padding: 6px 10px; border: 1px solid var(--border-ornate);
        background: var(--bg-card); color: var(--text-main);
        font-family: var(--reader-font); font-size: 15px; border-radius: 3px;
    }
    .bm-input { flex: 1; min-width: 220px; }
    .bm-save-btn {
        background: var(--accent-gold); color: #fff; border: none;
        padding: 7px 14px; font-family: 'Cinzel', serif; font-weight: 700;
        cursor: pointer; border-radius: 3px;
    }
    mark.search-highlight {
        background-color: rgba(212, 163, 89, 0.45);
        color: inherit;
        padding: 1px 4px;
        border-bottom: 2px solid var(--accent-gold);
        border-radius: 2px;
        font-weight: 600;
    }
</style>

<script>
    function toggleSettingsMenu(e) {
        e.stopPropagation();
        document.getElementById('settingsPopover').classList.toggle('open');
    }
    document.addEventListener('click', function(e) {
        const pop = document.getElementById('settingsPopover');
        if (pop && !pop.contains(e.target)) pop.classList.remove('open');
    });

    function updateTheme(themeClass) {
        document.body.classList.remove('theme-illuminated', 'theme-obsidian', 'theme-academic');
        if (themeClass !== 'default') document.body.classList.add(themeClass);
        localStorage.setItem('codex_theme', themeClass);
        const sel = document.getElementById('themeSelect');
        if (sel) sel.value = themeClass;
    }

    function updateBorder(borderClass) {
        document.body.classList.remove('border-ornate', 'border-standard', 'border-minimal');
        document.body.classList.add(borderClass);
        localStorage.setItem('codex_border', borderClass);
        const sel = document.getElementById('borderSelect');
        if (sel) sel.value = borderClass;
    }

    function updateFont(fontFamily) {
        document.documentElement.style.setProperty('--reader-font', fontFamily);
        localStorage.setItem('codex_font', fontFamily);
        const sel = document.getElementById('fontSelect');
        if (sel) sel.value = fontFamily;
    }

    function updateSize(px) {
        document.documentElement.style.setProperty('--font-size', px + 'px');
        localStorage.setItem('codex_size', px);
        const lbl = document.getElementById('sizeValLabel');
        if (lbl) lbl.textContent = px + 'px';
        const rng = document.getElementById('sizeRange');
        if (rng) rng.value = px;
    }

    function updateWidth(px) {
        document.documentElement.style.setProperty('--page-max-width', px + 'px');
        localStorage.setItem('codex_width', px);
        const lbl = document.getElementById('widthValLabel');
        if (lbl) lbl.textContent = px + 'px';
        const rng = document.getElementById('widthRange');
        if (rng) rng.value = px;
    }

    window.addEventListener('DOMContentLoaded', () => {
        const t = localStorage.getItem('codex_theme');
        if (t) updateTheme(t);
        const b = localStorage.getItem('codex_border');
        if (b) updateBorder(b);
        const f = localStorage.getItem('codex_font');
        if (f) updateFont(f);
        const s = localStorage.getItem('codex_size');
        if (s) updateSize(s);
        const w = localStorage.getItem('codex_width');
        if (w) updateWidth(w);
    });

    function toggleBookmarkDrawer(drawerId) {
        const el = document.getElementById(drawerId);
        if (el) el.classList.toggle('open');
    }

    async function saveBookmark(btnEl, payload, drawerId) {
        const drawer = document.getElementById(drawerId);
        const tag = drawer.querySelector('.bm-select').value;
        const note = drawer.querySelector('.bm-input').value;
        payload.folder_tag = tag;
        payload.personal_note = note;

        btnEl.textContent = 'Saving...';
        try {
            const resp = await fetch('/api/bookmark', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            if (resp.ok) {
                btnEl.textContent = 'Saved to Bookmarks';
                btnEl.style.background = '#1f5c3a';
                setTimeout(() => drawer.classList.remove('open'), 700);
            }
        } catch (err) {
            btnEl.textContent = 'Error Saving';
        }
    }
</script>
"""


def render_top_navbar(active_page: str = "", extra_controls_html: str = "") -> str:
    """Renders the unified Top Bar with bundled Appearance Popover across all pages."""
    return f"""
    <nav class="codex-toolbar">
        <div class="toolbar-group">
            <a href="/" class="nav-btn {'active-nav' if active_page == 'archive' else ''}">Grand Archive</a>
            <a href="/bookmarks" class="nav-btn {'active-nav' if active_page == 'bookmarks' else ''}">My Bookmarks</a>
            <a href="/public-db" class="nav-btn {'active-nav' if active_page == 'public' else ''}">Discovery Archive</a>
            <a href="/guide" class="nav-btn {'active-nav' if active_page == 'guide' else ''}">Field Guide</a>
        </div>
        <div class="toolbar-group">
            {extra_controls_html}
            <div class="settings-dropdown">
                <button class="nav-btn" onclick="toggleSettingsMenu(event)">Appearance ▾</button>
                <div id="settingsPopover" class="settings-popover" onclick="event.stopPropagation()">
                    <div class="setting-row">
                        <label>Surface Theme</label>
                        <select id="themeSelect" onchange="updateTheme(this.value)">
                            <option value="default">Aged Parchment Tome</option>
                            <option value="theme-illuminated">Illuminated Vellum (Cream &amp; Gold)</option>
                            <option value="theme-obsidian">Alexandria Night (Obsidian &amp; Brass)</option>
                            <option value="theme-academic">Modern Academic Press</option>
                        </select>
                    </div>
                    <div class="setting-row">
                        <label>Typeface</label>
                        <select id="fontSelect" onchange="updateFont(this.value)">
                            <option value="'EB Garamond', Georgia, serif">EB Garamond (Classical Aldine)</option>
                            <option value="'Cormorant Garamond', Georgia, serif">Cormorant (Manuscript)</option>
                            <option value="'Cinzel', Georgia, serif">Cinzel (Roman Inscription)</option>
                            <option value="Georgia, 'Times New Roman', serif">Classic Serif</option>
                            <option value="'Inter', system-ui, sans-serif">Clean Sans-Serif</option>
                        </select>
                    </div>
                    <div class="setting-row">
                        <label>Borders &amp; Frame</label>
                        <select id="borderSelect" onchange="updateBorder(this.value)">
                            <option value="border-ornate">Double-Rule Ornate Tome</option>
                            <option value="border-standard">Single Rule Frame</option>
                            <option value="border-minimal">Minimalist Flat Page</option>
                        </select>
                    </div>
                    <div class="setting-row">
                        <label><span>Font Size</span> <span id="sizeValLabel">20px</span></label>
                        <input id="sizeRange" type="range" min="16" max="26" value="20" oninput="updateSize(this.value)">
                    </div>
                    <div class="setting-row">
                        <label><span>Page Width / Margins</span> <span id="widthValLabel">980px</span></label>
                        <input id="widthRange" type="range" min="720" max="1280" step="40" value="980" oninput="updateWidth(this.value)">
                    </div>
                </div>
            </div>
            <a href="/shutdown" class="nav-btn exit-btn" title="Shut down Python server and exit">Exit</a>
        </div>
    </nav>
    """


def generate_codex_html(
    df_sec: pd.DataFrame,
    wdf: pd.DataFrame,
    ghost_df: pd.DataFrame,
    bound_df: pd.DataFrame,
    known_df: pd.DataFrame,
    suspect_sections: dict,
    plot_path: Path,
    output_html_path: Path,
    snr_threshold: float = 2.8,
    window_size: int = 180,
) -> Path:
    sector_id = str(df_sec.loc[0, "sector_id"])
    work_title = str(df_sec.loc[0, "work_title"])
    lang = str(df_sec.loc[0, "language"])
    max_snr = float(wdf["peak_snr"].max()) if not wdf.empty else 0.0

    img_b64 = _encode_image_base64(plot_path)
    img_html = (
        f'<img src="data:image/png;base64,{img_b64}" class="scan-chart" alt="3-Channel SNR Scan"/>'
        if img_b64
        else ""
    )

    card_counter = 0

    def render_cards(sub_df: pd.DataFrame, badge_class: str) -> str:
        nonlocal card_counter
        if sub_df.empty:
            return f'<div class="empty-notice">No passages detected in this category above the {snr_threshold:.1f}σ sensitivity cutoff.</div>'

        cards = []
        for _, hit in sub_df.iterrows():
            card_counter += 1
            drawer_id = f"bm-drawer-{card_counter}"
            span = html.escape(str(hit["cts_span"]))
            snr_num = float(hit["peak_snr"])
            snr = f"{snr_num:.2f}σ"
            chan = html.escape(str(hit["dominant_channel"]).replace("_", " "))
            status = html.escape(str(hit["novelty_status"]))
            match1 = html.escape(str(hit["primary_attribution"]))
            match2 = html.escape(str(hit["secondary_attribution"]))
            hiatus = f"{hit['hiatus_rate'] * 100:.1f}%"
            jsd = f"{hit['jsd']:.3f}"
            perip = f"{hit['periplus_density']:.1f}"
            eng_text = html.escape(str(hit["english_text"]))
            first_ref = span.split("–")[0]

            # Safe JSON payload for bookmark button
            import json
            bm_payload = html.escape(json.dumps({
                "sector_id": sector_id,
                "work_title": work_title,
                "cts_span": str(hit["cts_span"]),
                "peak_snr": snr_num,
                "dominant_channel": str(hit["dominant_channel"]),
                "primary_attribution": str(hit["primary_attribution"]),
                "english_text": str(hit["english_text"]),
            }))

            cards.append(f"""
            <article class="tome-card">
                <header class="card-header">
                    <div>
                        <span class="passage-ref">Book.Chap.Sec: {span}</span>
                        <span class="badge {badge_class}">{status}</span>
                    </div>
                    <div class="snr-pill" title="Signal strength in standard deviations above background noise">
                        Anomaly Strength: {snr} · {chan}
                    </div>
                </header>
                <div class="attribution-bar">
                    <div><strong>1st Suspect Attribution:</strong> {match1}</div>
                    <div><strong>2nd Suspect Attribution:</strong> {match2}</div>
                    <div class="metrics-row">
                        <span>Vowel Hiatus: <strong>{hiatus}</strong></span> ·
                        <span>Particle JSD: <strong>{jsd}</strong></span> ·
                        <span>Periplus Index: <strong>{perip}</strong></span>
                        (<a href="/guide" class="help-link">What do these mean?</a>)
                    </div>
                </div>
                <div class="parchment-passage">
                    <p class="drop-cap">{eng_text}</p>
                </div>
                <footer class="card-footer">
                    <button class="context-btn" onclick="toggleBookmarkDrawer('{drawer_id}')">
                        Bookmark Passage (Local Only)
                    </button>
                    <button class="context-btn" onclick="jumpToFullText('{first_ref}')">
                        Read in Full Book Context ({first_ref})
                    </button>
                </footer>
                <div id="{drawer_id}" class="bookmark-drawer">
                    <div class="bm-form-row">
                        <select class="bm-select">
                            <option value="General Interest">General Interest</option>
                            <option value="Nostoi & Mythic Lore">Nostoi &amp; Mythic Lore</option>
                            <option value="Sea-Voyage Periploi">Sea-Voyage Periploi</option>
                            <option value="Lost Historians">Lost Historians</option>
                            <option value="High-Priority Follow-Up">High-Priority Follow-Up</option>
                        </select>
                        <input type="text" class="bm-input" placeholder="Add a private note (optional)...">
                        <button class="bm-save-btn" onclick='saveBookmark(this, {bm_payload}, "{drawer_id}")'>
                            Save to My Bookmarks
                        </button>
                    </div>
                </div>
            </article>
            """)
        return "\n".join(cards)

    suspect_cards = []
    for s_label, sec_indices in suspect_sections.items():
        refs = [str(df_sec.loc[i, "cts_ref"]) for i in sec_indices]
        sample_blocks = []
        for i in sec_indices[:4]:
            r_id = html.escape(str(df_sec.loc[i, "cts_ref"]))
            r_txt = html.escape(str(df_sec.loc[i, "english_text"]))
            sample_blocks.append(f'<div class="suspect-sample"><strong>[{r_id}]</strong> {r_txt}</div>')
        suspect_cards.append(f"""
        <article class="tome-card">
            <header class="card-header">
                <span class="passage-ref">{html.escape(s_label)}</span>
                <span class="snr-pill">{len(refs)} Named Reference Sections</span>
            </header>
            <div class="attribution-bar">
                <strong>Cited in Sections:</strong> {", ".join(refs[:12])}
            </div>
            <div class="parchment-passage">
                {"".join(sample_blocks)}
            </div>
        </article>
        """)
    suspects_html = "\n".join(suspect_cards) if suspect_cards else '<div class="empty-notice">No explicitly named suspect authors in this book.</div>'

    ghost_secs = set(ghost_df["sec_center_idx"].astype(int).tolist()) if not ghost_df.empty else set()
    bound_secs = set(bound_df["sec_center_idx"].astype(int).tolist()) if not bound_df.empty else set()
    known_secs = set(known_df["sec_center_idx"].astype(int).tolist()) if not known_df.empty else set()

    import json
    full_book_rows = []
    for idx, row in df_sec.iterrows():
        ref = html.escape(str(row["cts_ref"]))
        eng = html.escape(str(row["english_text"]))
        grc = html.escape(str(row["source_text"]))
        sec_drawer_id = f"sec-bm-{idx}"

        sec_class = ""
        tag_html = ""
        if idx in ghost_secs:
            sec_class = "highlight-ghost"
            tag_html = '<span class="inline-flag ghost-flag">Uncredited Anomaly</span>'
        elif idx in bound_secs:
            sec_class = "highlight-bound"
            tag_html = '<span class="inline-flag bound-flag">Extended Borrowing</span>'
        elif idx in known_secs:
            sec_class = "highlight-known"
            tag_html = '<span class="inline-flag known-flag">Explicit Citation</span>'

        sec_payload = html.escape(json.dumps({
            "sector_id": sector_id,
            "work_title": work_title,
            "cts_span": str(row["cts_ref"]),
            "peak_snr": 0.0,
            "dominant_channel": "FULL_TEXT_EXCERPT",
            "primary_attribution": "Direct Book Section",
            "english_text": str(row["english_text"]),
        }))

        full_book_rows.append(f"""
        <section id="sec-{ref}" class="book-section {sec_class}">
            <div class="sec-margin">
                <span class="sec-num">{ref}</span>
                {tag_html}
                <button class="context-btn" style="font-size:11px;padding:3px 7px;" onclick="toggleBookmarkDrawer('{sec_drawer_id}')">
                    Bookmark
                </button>
            </div>
            <div class="sec-body">
                <p class="eng-para">{eng}</p>
                <details class="orig-toggle">
                    <summary>View Original {lang.title()} Text</summary>
                    <p class="orig-para">{grc}</p>
                </details>
                <div id="{sec_drawer_id}" class="bookmark-drawer" style="margin-top:10px;">
                    <div class="bm-form-row">
                        <select class="bm-select">
                            <option value="General Interest">General Interest</option>
                            <option value="Nostoi & Mythic Lore">Nostoi &amp; Mythic Lore</option>
                            <option value="Sea-Voyage Periploi">Sea-Voyage Periploi</option>
                            <option value="Lost Historians">Lost Historians</option>
                        </select>
                        <input type="text" class="bm-input" placeholder="Private note on section {ref}...">
                        <button class="bm-save-btn" onclick='saveBookmark(this, {sec_payload}, "{sec_drawer_id}")'>Save</button>
                    </div>
                </div>
            </div>
        </section>
        """)

    navbar_html = render_top_navbar(active_page="")

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(work_title)} ({sector_id}) — Codex Reader</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&family=Cinzel:wght@500;700&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=EB+Garamond:ital,wght@0,400;0,600;1,400&family=Inter:wght@400;600&display=swap" rel="stylesheet">
{SHARED_CODEX_CSS_AND_JS}
<style>
    .codex-tabs {{
        display: flex; flex-wrap: wrap; gap: 8px;
        margin-bottom: 28px; border-bottom: 2px solid var(--border-ornate);
        padding-bottom: 12px;
    }}
    .tab-btn {{
        font-family: 'Cinzel', serif; font-size: 14px; font-weight: 700;
        padding: 9px 16px; background: var(--bg-card); color: var(--text-main);
        border: 1px solid var(--border-ornate); cursor: pointer;
        border-radius: 3px; transition: all 0.15s ease;
    }}
    .tab-btn:hover, .tab-btn.active {{
        background: var(--accent-gold); color: #fff9ee; border-color: var(--accent-gold);
    }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    .book-section {{
        display: grid; grid-template-columns: 140px 1fr; gap: 20px;
        padding: 18px 16px; border-bottom: 1px dashed var(--border-ornate);
        font-size: var(--font-size); line-height: var(--line-height);
    }}
    .sec-margin {{
        font-family: 'Cinzel', serif; font-size: 15px; font-weight: 700;
        color: var(--accent-gold); display: flex; flex-direction: column; gap: 6px;
    }}
    .inline-flag {{
        font-size: 11px; padding: 3px 6px; border-radius: 3px;
        color: #fff; display: inline-block; width: fit-content;
    }}
    .ghost-flag {{ background: var(--badge-ghost); }}
    .bound-flag {{ background: var(--badge-bound); }}
    .known-flag {{ background: var(--badge-known); }}
    .highlight-ghost {{ background: rgba(139, 30, 30, 0.09); border-left: 4px solid var(--badge-ghost); }}
    .highlight-bound {{ background: rgba(143, 87, 13, 0.09); border-left: 4px solid var(--badge-bound); }}
    .highlight-known {{ background: rgba(31, 92, 58, 0.07); border-left: 4px solid var(--badge-known); }}
    .eng-para {{ margin: 0 0 8px 0; text-align: justify; }}
    .orig-toggle summary {{
        font-family: 'Cinzel', serif; font-size: 13px; color: var(--text-muted); cursor: pointer;
    }}
    .orig-para {{
        font-size: 0.9em; color: var(--text-muted); margin-top: 8px;
        padding: 10px; background: var(--bg-bar); border-left: 2px solid var(--border-ornate);
    }}
    .scan-chart {{ width: 100%; height: auto; border: 2px solid var(--border-ornate); margin-top: 12px; }}
    .suspect-sample {{ margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px dotted var(--border-ornate); }}
    .empty-notice {{ padding: 36px; text-align: center; font-style: italic; color: var(--text-muted); border: 1px dashed var(--border-ornate); }}
</style>
</head>
<body class="border-ornate">

{navbar_html}

<main class="tome-page">
    <header class="tome-header">
        <div class="tome-super">Codex Philologica · Stylometric Source Recovery</div>
        <h1 class="tome-title">{html.escape(work_title)}</h1>
        <div class="tome-stats">
            <span>Sector: <strong>{html.escape(sector_id)}</strong></span>
            <span>Language: <strong>{html.escape(lang)}</strong></span>
            <span>Peak Anomaly Strength: <strong>{max_snr:.2f}σ</strong></span>
            <span>Scan Settings: <strong>{window_size}-Word Window ({snr_threshold:.1f}σ Sensitivity Cutoff)</strong></span>
            <span><a href="/guide" class="help-link">What do these metrics mean?</a></span>
        </div>
    </header>

    <div class="codex-tabs">
        <button class="tab-btn active" onclick="showTab('tab-ghosts', this)">
            Uncredited Passages ({len(ghost_df)})
        </button>
        <button class="tab-btn" onclick="showTab('tab-bounds', this)">
            Extended Borrowings ({len(bound_df)})
        </button>
        <button class="tab-btn" onclick="showTab('tab-known', this)">
            Explicit Citations ({len(known_df)})
        </button>
        <button class="tab-btn" onclick="showTab('tab-suspects', this)">
            Suspect Lineup ({len(suspect_sections)})
        </button>
        <button class="tab-btn" onclick="showTab('tab-chart', this)">
            3-Channel Signal Curve
        </button>
        <button id="fullBookTabBtn" class="tab-btn" onclick="showTab('tab-fullbook', this)">
            Full Book Reader ({len(df_sec)} Sections)
        </button>
    </div>

    <section id="tab-ghosts" class="tab-panel active">
        {render_cards(ghost_df, "badge-ghost")}
    </section>

    <section id="tab-bounds" class="tab-panel">
        {render_cards(bound_df, "badge-bound")}
    </section>

    <section id="tab-known" class="tab-panel">
        {render_cards(known_df, "badge-known")}
    </section>

    <section id="tab-suspects" class="tab-panel">
        {suspects_html}
    </section>

    <section id="tab-chart" class="tab-panel">
        <div class="tome-card" style="padding: 20px;">
            <h3 style="font-family: 'Cinzel', serif; margin-top: 0;">Multi-Channel Stylometric Signal Trace</h3>
            {img_html}
        </div>
    </section>

    <section id="tab-fullbook" class="tab-panel">
        {"".join(full_book_rows)}
    </section>
</main>

<script>
    function showTab(tabId, btnEl) {{
        document.querySelectorAll('.tab-panel').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');
        if (btnEl) btnEl.classList.add('active');
    }}

    function jumpToFullText(refId) {{
        const btn = document.getElementById('fullBookTabBtn');
        showTab('tab-fullbook', btn);
        const target = document.getElementById('sec-' + refId);
        if (target) {{
            target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            target.style.outline = '3px solid var(--accent-gold)';
            setTimeout(() => target.style.outline = 'none', 3000);
        }}
    }}
</script>
</body>
</html>
"""

    output_html_path.parent.mkdir(parents=True, exist_ok=True)
    output_html_path.write_text(html_doc, encoding="utf-8")
    return output_html_path