import base64
import html
import json
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
    """
    Opens the generated HTML Codex in the user's default browser across
    Windows, macOS, and Linux (including Ubuntu/VirtualBox environments).
    """
    abs_url = filepath.resolve().as_uri()
    try:
        # Suppress noisy browser stderr logs in Linux terminals
        if sys.platform.startswith("linux"):
            subprocess.Popen(
                ["xdg-open", str(filepath.resolve())],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(filepath.resolve())])
            return
        elif sys.platform.startswith("win"):
            os.startfile(str(filepath.resolve()))  # type: ignore[attr-defined]
            return
    except Exception:
        pass

    webbrowser.open(abs_url)


def generate_codex_html(
    df_sec: pd.DataFrame,
    wdf: pd.DataFrame,
    ghost_df: pd.DataFrame,
    bound_df: pd.DataFrame,
    known_df: pd.DataFrame,
    suspect_sections: dict,
    plot_path: Path,
    output_html_path: Path,
) -> Path:
    """
    Generates a standalone, interactive Ancient Tome / Parchment Codex HTML reader
    with live font, margin, border, and theme controls.
    """
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

    def render_cards(sub_df: pd.DataFrame, badge_class: str) -> str:
        if sub_df.empty:
            return '<div class="empty-notice">No passages detected in this category above the 2.8σ threshold.</div>'

        cards = []
        for _, hit in sub_df.iterrows():
            span = html.escape(str(hit["cts_span"]))
            snr = f"{hit['peak_snr']:.2f}σ"
            chan = html.escape(str(hit["dominant_channel"]).replace("_", " "))
            status = html.escape(str(hit["novelty_status"]))
            match1 = html.escape(str(hit["primary_attribution"]))
            match2 = html.escape(str(hit["secondary_attribution"]))
            hiatus = f"{hit['hiatus_rate'] * 100:.1f}%"
            jsd = f"{hit['jsd']:.3f}"
            perip = f"{hit['periplus_density']:.1f}"
            eng_text = html.escape(str(hit["english_text"]))
            first_ref = span.split("–")[0]

            cards.append(f"""
            <article class="tome-card">
                <header class="card-header">
                    <div>
                        <span class="passage-ref">Book.Chap.Sec: {span}</span>
                        <span class="badge {badge_class}">{status}</span>
                    </div>
                    <div class="snr-pill">Peak SNR: {snr} · {chan}</div>
                </header>
                <div class="attribution-bar">
                    <div><strong>1st Suspect Attribution:</strong> {match1}</div>
                    <div><strong>2nd Suspect Attribution:</strong> {match2}</div>
                    <div class="metrics-row">
                        <span>Vowel Hiatus: <strong>{hiatus}</strong></span> ·
                        <span>Particle JSD: <strong>{jsd}</strong></span> ·
                        <span>Periplus Index: <strong>{perip}</strong></span>
                    </div>
                </div>
                <div class="parchment-passage">
                    <p class="drop-cap">{eng_text}</p>
                </div>
                <footer class="card-footer">
                    <button class="context-btn" onclick="jumpToFullText('{first_ref}')">
                        Read in Full Book Context ({first_ref}) →
                    </button>
                </footer>
            </article>
            """)
        return "\n".join(cards)

    # Render Suspect Lineup Evidence cards
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

    # Map high-SNR section indices so the Full Book Reader highlights flagged sections
    ghost_secs = set(ghost_df["sec_center_idx"].astype(int).tolist()) if not ghost_df.empty else set()
    bound_secs = set(bound_df["sec_center_idx"].astype(int).tolist()) if not bound_df.empty else set()
    known_secs = set(known_df["sec_center_idx"].astype(int).tolist()) if not known_df.empty else set()

    full_book_rows = []
    for idx, row in df_sec.iterrows():
        ref = html.escape(str(row["cts_ref"]))
        eng = html.escape(str(row["english_text"]))
        grc = html.escape(str(row["source_text"]))

        sec_class = ""
        tag_html = ""
        if idx in ghost_secs:
            sec_class = "highlight-ghost"
            tag_html = '<span class="inline-flag ghost-flag">★ Uncredited Anomaly</span>'
        elif idx in bound_secs:
            sec_class = "highlight-bound"
            tag_html = '<span class="inline-flag bound-flag">◆ Extended Borrowing</span>'
        elif idx in known_secs:
            sec_class = "highlight-known"
            tag_html = '<span class="inline-flag known-flag">● Explicit Citation</span>'

        full_book_rows.append(f"""
        <section id="sec-{ref}" class="book-section {sec_class}">
            <div class="sec-margin">
                <span class="sec-num">{ref}</span>
                {tag_html}
            </div>
            <div class="sec-body">
                <p class="eng-para">{eng}</p>
                <details class="orig-toggle">
                    <summary>View Original {lang.title()} Text</summary>
                    <p class="orig-para">{grc}</p>
                </details>
            </div>
        </section>
        """)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(work_title)} ({sector_id}) — Codex Reader</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&family=Cinzel:wght@500;700&family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=EB+Garamond:ital,wght@0,400;0,600;1,400&family=Inter:wght@400;600&display=swap" rel="stylesheet">
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
        --badge-ghost: #8b1e1e;
        --badge-bound: #8f570d;
        --badge-known: #1f5c3a;
        --reader-font: 'EB Garamond', Georgia, serif;
        --font-size: 20px;
        --line-height: 1.75;
        --page-max-width: 960px;
        --page-padding: 52px;
    }}

    body.theme-illuminated {{
        --bg-outer: #261c14;
        --bg-page: #fbf6ec;
        --bg-card: #f5ebd6;
        --bg-bar: #ead8b8;
        --text-main: #1f140a;
        --text-muted: #5a4228;
        --accent-gold: #9a6b1f;
        --border-ornate: #b58938;
    }}

    body.theme-obsidian {{
        --bg-outer: #0b0c10;
        --bg-page: #16181d;
        --bg-card: #1e2129;
        --bg-bar: #262a34;
        --text-main: #e6dcc8;
        --text-muted: #a89f8d;
        --accent-gold: #d4a359;
        --border-ornate: #6e552f;
    }}

    body.theme-academic {{
        --bg-outer: #e5e7eb;
        --bg-page: #ffffff;
        --bg-card: #f9fafb;
        --bg-bar: #f3f4f6;
        --text-main: #111827;
        --text-muted: #4b5563;
        --accent-gold: #1e3a8a;
        --border-ornate: #d1d5db;
    }}

    * {{ box-sizing: border-box; }}

    body {{
        margin: 0;
        padding: 0;
        background-color: var(--bg-outer);
        color: var(--text-main);
        font-family: var(--reader-font);
        transition: background-color 0.25s ease, color 0.25s ease;
    }}

    /* Top Control Toolbar */
    .codex-toolbar {{
        position: sticky;
        top: 0;
        z-index: 100;
        background: #14100d;
        color: #e8dcc4;
        border-bottom: 2px solid #6b4e2b;
        padding: 10px 24px;
        display: flex;
        flex-wrap: wrap;
        gap: 18px;
        align-items: center;
        justify-content: space-between;
        font-family: 'Cinzel', Georgia, serif;
        font-size: 13px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.45);
    }}

    .toolbar-group {{
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }}

    .codex-toolbar select, .codex-toolbar input[type="range"] {{
        background: #261e17;
        color: #f3e8d2;
        border: 1px solid #8c683b;
        padding: 4px 8px;
        border-radius: 4px;
        font-family: inherit;
        cursor: pointer;
    }}

    /* Main Parchment Tome Container */
    .tome-page {{
        max-width: var(--page-max-width);
        margin: 34px auto 64px auto;
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
    }}

    body.border-ornate .tome-page {{
        border: 6px double var(--border-ornate);
    }}

    body.border-minimal .tome-page {{
        border: 1px solid var(--border-ornate);
        background-image: none;
        box-shadow: 0 6px 20px rgba(0,0,0,0.2);
    }}

    .tome-header {{
        text-align: center;
        border-bottom: 3px double var(--border-ornate);
        padding-bottom: 24px;
        margin-bottom: 28px;
    }}

    .tome-super {{
        font-family: 'Cinzel', serif;
        letter-spacing: 3px;
        text-transform: uppercase;
        font-size: 13px;
        color: var(--accent-gold);
        margin-bottom: 8px;
    }}

    .tome-title {{
        font-family: 'Cinzel Decorative', 'Cinzel', serif;
        font-size: 34px;
        margin: 6px 0 12px 0;
        color: var(--text-main);
    }}

    .tome-stats {{
        display: flex;
        justify-content: center;
        gap: 24px;
        flex-wrap: wrap;
        font-family: 'Cinzel', serif;
        font-size: 14px;
        color: var(--text-muted);
    }}

    /* Navigation Tabs */
    .codex-tabs {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 28px;
        border-bottom: 2px solid var(--border-ornate);
        padding-bottom: 12px;
    }}

    .tab-btn {{
        font-family: 'Cinzel', serif;
        font-size: 14px;
        font-weight: 700;
        padding: 9px 16px;
        background: var(--bg-card);
        color: var(--text-main);
        border: 1px solid var(--border-ornate);
        cursor: pointer;
        border-radius: 3px;
        transition: all 0.15s ease;
    }}

    .tab-btn:hover, .tab-btn.active {{
        background: var(--accent-gold);
        color: #fff9ee;
        border-color: var(--accent-gold);
    }}

    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}

    /* Candidate Tome Cards */
    .tome-card {{
        background: var(--bg-card);
        border: 2px solid var(--border-ornate);
        margin-bottom: 32px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.12);
    }}

    .card-header {{
        background: var(--bg-bar);
        padding: 12px 20px;
        border-bottom: 1px solid var(--border-ornate);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
        font-family: 'Cinzel', serif;
    }}

    .passage-ref {{
        font-size: 18px;
        font-weight: 700;
        margin-right: 12px;
    }}

    .badge {{
        font-size: 11px;
        padding: 3px 9px;
        border-radius: 3px;
        color: #fff;
        font-family: 'Cinzel', serif;
        letter-spacing: 0.6px;
    }}
    .badge-ghost {{ background: var(--badge-ghost); }}
    .badge-bound {{ background: var(--badge-bound); }}
    .badge-known {{ background: var(--badge-known); }}

    .snr-pill {{
        font-weight: 700;
        color: var(--accent-gold);
        font-size: 15px;
    }}

    .attribution-bar {{
        padding: 12px 20px;
        border-bottom: 1px dashed var(--border-ornate);
        font-size: 15px;
        line-height: 1.5;
        color: var(--text-muted);
    }}

    .metrics-row {{
        margin-top: 6px;
        font-size: 14px;
    }}

    .parchment-passage {{
        padding: 24px 28px;
        font-size: var(--font-size);
        line-height: var(--line-height);
        text-align: justify;
    }}

    .parchment-passage p {{
        margin: 0;
    }}

    .drop-cap::first-letter {{
        float: left;
        font-family: 'Cinzel Decorative', 'Cinzel', serif;
        font-size: 3.1em;
        line-height: 0.82;
        padding-right: 10px;
        padding-top: 4px;
        color: var(--accent-gold);
        font-weight: 700;
    }}

    .card-footer {{
        padding: 10px 20px;
        border-top: 1px solid var(--border-ornate);
        text-align: right;
        background: var(--bg-bar);
    }}

    .context-btn {{
        font-family: 'Cinzel', serif;
        font-size: 13px;
        background: transparent;
        color: var(--accent-gold);
        border: 1px solid var(--accent-gold);
        padding: 5px 12px;
        cursor: pointer;
        font-weight: 700;
    }}
    .context-btn:hover {{
        background: var(--accent-gold);
        color: #fff;
    }}

    /* Full Book Reader Mode */
    .book-section {{
        display: grid;
        grid-template-columns: 140px 1fr;
        gap: 20px;
        padding: 18px 16px;
        border-bottom: 1px dashed var(--border-ornate);
        font-size: var(--font-size);
        line-height: var(--line-height);
    }}

    .sec-margin {{
        font-family: 'Cinzel', serif;
        font-size: 15px;
        font-weight: 700;
        color: var(--accent-gold);
        display: flex;
        flex-direction: column;
        gap: 6px;
    }}

    .inline-flag {{
        font-size: 11px;
        padding: 3px 6px;
        border-radius: 3px;
        color: #fff;
        display: inline-block;
        width: fit-content;
    }}
    .ghost-flag {{ background: var(--badge-ghost); }}
    .bound-flag {{ background: var(--badge-bound); }}
    .known-flag {{ background: var(--badge-known); }}

    .highlight-ghost {{ background: rgba(139, 30, 30, 0.09); border-left: 4px solid var(--badge-ghost); }}
    .highlight-bound {{ background: rgba(143, 87, 13, 0.09); border-left: 4px solid var(--badge-bound); }}
    .highlight-known {{ background: rgba(31, 92, 58, 0.07); border-left: 4px solid var(--badge-known); }}

    .eng-para {{ margin: 0 0 8px 0; text-align: justify; }}

    .orig-toggle summary {{
        font-family: 'Cinzel', serif;
        font-size: 13px;
        color: var(--text-muted);
        cursor: pointer;
    }}
    .orig-para {{
        font-size: 0.9em;
        color: var(--text-muted);
        margin-top: 8px;
        padding: 10px;
        background: var(--bg-bar);
        border-left: 2px solid var(--border-ornate);
    }}

    .scan-chart {{
        width: 100%;
        height: auto;
        border: 2px solid var(--border-ornate);
        margin-top: 12px;
    }}

    .suspect-sample {{
        margin-bottom: 14px;
        padding-bottom: 12px;
        border-bottom: 1px dotted var(--border-ornate);
    }}

    .empty-notice {{
        padding: 36px;
        text-align: center;
        font-style: italic;
        color: var(--text-muted);
        border: 1px dashed var(--border-ornate);
    }}

    @media (max-width: 720px) {{
        .book-section {{ grid-template-columns: 1fr; }}
        .tome-page {{ padding: 20px; margin: 12px; }}
    }}
</style>
</head>
<body class="border-ornate">

<!-- Interactive Styling Toolbar -->
<nav class="codex-toolbar">
    <div class="toolbar-group">
        <strong>📜 CODEX STYLING:</strong>
        <label>Surface:
            <select id="themeSelect" onchange="updateTheme(this.value)">
                <option value="default">Aged Parchment Tome</option>
                <option value="theme-illuminated">Illuminated Vellum (Cream & Gold)</option>
                <option value="theme-obsidian">Alexandria Night (Obsidian & Brass)</option>
                <option value="theme-academic">Modern Academic Press</option>
            </select>
        </label>
        <label>Typeface:
            <select id="fontSelect" onchange="updateFont(this.value)">
                <option value="'EB Garamond', Georgia, serif">EB Garamond (Classical Aldine)</option>
                <option value="'Cormorant Garamond', Georgia, serif">Cormorant (High-Contrast Manuscript)</option>
                <option value="'Cinzel', Georgia, serif">Cinzel (Roman Inscription)</option>
                <option value="Georgia, 'Times New Roman', serif">Classic Serif</option>
                <option value="'Inter', system-ui, sans-serif">Clean Sans-Serif</option>
            </select>
        </label>
        <label>Borders:
            <select id="borderSelect" onchange="updateBorder(this.value)">
                <option value="border-ornate">Double-Rule Ornate Tome</option>
                <option value="border-standard">Single Rule</option>
                <option value="border-minimal">Minimalist Flat</option>
            </select>
        </label>
    </div>
    <div class="toolbar-group">
        <label>Font Size:
            <input type="range" min="16" max="26" value="20" oninput="updateSize(this.value)">
        </label>
        <label>Margins:
            <input type="range" min="720" max="1240" step="40" value="960" oninput="updateWidth(this.value)">
        </label>
    </div>
</nav>

<main class="tome-page">
    <header class="tome-header">
        <div class="tome-super">Codex Philologica · Stylometric Source Recovery</div>
        <h1 class="tome-title">{html.escape(work_title)}</h1>
        <div class="tome-stats">
            <span>Sector: <strong>{html.escape(sector_id)}</strong></span>
            <span>Original Language: <strong>{html.escape(lang)}</strong></span>
            <span>Peak Anomaly: <strong>{max_snr:.2f}σ</strong></span>
            <span>Sections Aligned: <strong>{len(df_sec)}</strong></span>
        </div>
    </header>

    <div class="codex-tabs">
        <button class="tab-btn active" onclick="showTab('tab-ghosts', this)">
            ★ Uncredited Passages ({len(ghost_df)})
        </button>
        <button class="tab-btn" onclick="showTab('tab-bounds', this)">
            ◆ Extended Borrowings ({len(bound_df)})
        </button>
        <button class="tab-btn" onclick="showTab('tab-known', this)">
            ● Explicit Citations ({len(known_df)})
        </button>
        <button class="tab-btn" onclick="showTab('tab-suspects', this)">
            ⚖ Suspect Lineup ({len(suspect_sections)})
        </button>
        <button class="tab-btn" onclick="showTab('tab-chart', this)">
            📈 3-Channel Signal Curve
        </button>
        <button id="fullBookTabBtn" class="tab-btn" onclick="showTab('tab-fullbook', this)">
            📖 Full Book Reader ({len(df_sec)} Sections)
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

    function updateTheme(themeClass) {{
        document.body.classList.remove('theme-illuminated', 'theme-obsidian', 'theme-academic');
        if (themeClass !== 'default') document.body.classList.add(themeClass);
    }}

    function updateBorder(borderClass) {{
        document.body.classList.remove('border-ornate', 'border-standard', 'border-minimal');
        document.body.classList.add(borderClass);
    }}

    function updateFont(fontFamily) {{
        document.documentElement.style.setProperty('--reader-font', fontFamily);
    }}

    function updateSize(px) {{
        document.documentElement.style.setProperty('--font-size', px + 'px');
    }}

    function updateWidth(px) {{
        document.documentElement.style.setProperty('--page-max-width', px + 'px');
    }}
</script>
</body>
</html>
"""

    output_html_path.parent.mkdir(parents=True, exist_ok=True)
    output_html_path.write_text(html_doc, encoding="utf-8")
    return output_html_path