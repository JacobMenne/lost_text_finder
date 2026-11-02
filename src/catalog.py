import os
import random
import pandas as pd
import json
from pathlib import Path

SCAN_LOG_PATH = "data/scan_history.csv"

# Master Registry of Open-Access Greco-Roman Compilations (Perseus Digital Library)
# Uses directory paths so ingest.py dynamically resolves exact .perseus-grc/lat/eng filenames.
CORPUS_REGISTRY = [
    {
        "id": "diodorus",
        "genre": "1. Universal & Hellenistic History",
        "title": "Diodorus Siculus, Library of History",
        "lang": "GREEK",
        "books": [str(b) for b in list(range(1, 6)) + list(range(11, 21))],
        "book_label": "Books 1–5, 11–20 (15 Books)",
        "repo": "PerseusDL/canonical-greekLit",
        "dir_path": "data/tlg0060/tlg001",
    },
    {
        "id": "appian",
        "genre": "1. Universal & Hellenistic History",
        "title": "Appian, Civil Wars",
        "lang": "GREEK",
        "books": [str(b) for b in range(1, 6)],
        "book_label": "Books 1–5 (5 Books)",
        "repo": "PerseusDL/canonical-greekLit",
        "dir_path": "data/tlg0551/tlg017",
    },
    {
        "id": "polybius",
        "genre": "1. Universal & Hellenistic History",
        "title": "Polybius, Histories",
        "lang": "GREEK",
        "books": [str(b) for b in range(1, 40)],
        "book_label": "Books 1–39 (39 Books)",
        "repo": "PerseusDL/canonical-greekLit",
        "dir_path": "data/tlg0543/tlg001",
    },
    {
        "id": "strabo",
        "genre": "2. Ancient Geography & Periploi",
        "title": "Strabo, Geography",
        "lang": "GREEK",
        "books": [str(b) for b in range(1, 18)],
        "book_label": "Books 1–17 (17 Books)",
        "repo": "PerseusDL/canonical-greekLit",
        "dir_path": "data/tlg0099/tlg001",
    },
    {
        "id": "pausanias",
        "genre": "2. Ancient Geography & Periploi",
        "title": "Pausanias, Description of Greece",
        "lang": "GREEK",
        "books": [str(b) for b in range(1, 11)],
        "book_label": "Books 1–10 (10 Books)",
        "repo": "PerseusDL/canonical-greekLit",
        "dir_path": "data/tlg0525/tlg001",
    },
    {
        "id": "apollodorus_lib",
        "genre": "3. Mythology & Heroic Compendia",
        "title": "Apollodorus, Library of Mythology",
        "lang": "GREEK",
        "books": ["1", "2", "3"],
        "book_label": "Books 1–3 (3 Books)",
        "repo": "PerseusDL/canonical-greekLit",
        "dir_path": "data/tlg0548/tlg001",
    },
    {
        "id": "apollodorus_epit",
        "genre": "3. Mythology & Heroic Compendia",
        "title": "Apollodorus, Epitome",
        "lang": "GREEK",
        "books": [str(b) for b in range(1, 8)],
        "book_label": "Sections 1–7 (7 Sections)",
        "repo": "PerseusDL/canonical-greekLit",
        "dir_path": "data/tlg0548/tlg002",
    },
    {
        "id": "josephus",
        "genre": "4. Biography & Literary Miscellany",
        "title": "Flavius Josephus, Antiquities",
        "lang": "GREEK",
        "books": [str(b) for b in range(1, 21)],
        "book_label": "Books 1–20 (20 Books)",
        "repo": "PerseusDL/canonical-greekLit",
        "dir_path": "data/tlg0526/tlg001",
    },
    {
        "id": "pliny",
        "genre": "5. Roman & Latin Encyclopedias",
        "title": "Pliny the Elder, Natural History",
        "lang": "LATIN",
        "books": [str(b) for b in range(1, 38)],
        "book_label": "Books 1–37 (37 Books)",
        "repo": "PerseusDL/canonical-latinLit",
        "dir_path": "data/phi0978/phi001",
    },
    {
        "id": "gellius",
        "genre": "5. Roman & Latin Encyclopedias",
        "title": "Aulus Gellius, Attic Nights",
        "lang": "LATIN",
        "books": [str(b) for b in range(1, 21)],
        "book_label": "Books 1–20 (20 Books)",
        "repo": "PerseusDL/canonical-latinLit",
        "dir_path": "data/phi1254/phi001",
    },
]

CUSTOM_WORKS_PATH = Path("data/custom_works.json")

GENRE_OPTIONS = [
    "1. Universal & Hellenistic History",
    "2. Ancient Geography & Periploi",
    "3. Mythology & Heroic Compendia",
    "4. Biography & Literary Miscellany",
    "5. Roman & Latin Encyclopedias",
]


def auto_classify_genre(title: str, lang: str) -> str:
    """Automatically assigns one of the 5 standard genres based on title/author keywords."""
    t_low = title.lower()
    if any(k in t_low for k in ["geograph", "peripl", "pausanias", "strabo", "tour", "coast", "island"]):
        return "2. Ancient Geography & Periploi"
    if any(k in t_low for k in ["myth", "fable", "hyginus", "apollodorus", "hero", "epitome", "ovid"]):
        return "3. Mythology & Heroic Compendia"
    if any(k in t_low for k in ["lives", "life", "plutarch", "biograph", "banquet", "moralia", "athenaeus", "philosoph"]):
        return "4. Biography & Literary Miscellany"
    if lang == "LATIN" and any(k in t_low for k in ["natural", "nights", "encyclop", "varro", "pliny", "solinus", "censorinus"]):
        return "5. Roman & Latin Encyclopedias"
    return "1. Universal & Hellenistic History"


def get_full_corpus_registry() -> list[dict]:
    """Returns built-in CORPUS_REGISTRY merged with any user-added works in data/custom_works.json."""
    registry = list(CORPUS_REGISTRY)
    if CUSTOM_WORKS_PATH.exists():
        try:
            custom_list = json.loads(CUSTOM_WORKS_PATH.read_text(encoding="utf-8"))
            existing_ids = {w["id"] for w in registry}
            for cw in custom_list:
                if cw["id"] not in existing_ids:
                    registry.append(cw)
        except Exception:
            pass
    return registry


def save_custom_work(new_work: dict):
    CUSTOM_WORKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    custom_list = []
    if CUSTOM_WORKS_PATH.exists():
        try:
            custom_list = json.loads(CUSTOM_WORKS_PATH.read_text(encoding="utf-8"))
        except Exception:
            custom_list = []
    custom_list = [w for w in custom_list if w["id"] != new_work["id"]]
    custom_list.append(new_work)
    CUSTOM_WORKS_PATH.write_text(json.dumps(custom_list, indent=2), encoding="utf-8")

def remove_custom_work(work_id: str):
    """
    Removes a custom work from data/custom_works.json and purges all of its
    cached XML, aligned CSVs, Codex HTML files, scan history, and Discovery Archive rows.
    """
    import glob
    import json
    import os
    import sqlite3
    from pathlib import Path
    import pandas as pd

    wid_clean = work_id.strip().lower()
    wid_upper = wid_clean.upper()

    # 1. Remove from custom_works.json
    if CUSTOM_WORKS_PATH.exists():
        custom_list = json.loads(CUSTOM_WORKS_PATH.read_text(encoding="utf-8"))
        before_cnt = len(custom_list)
        custom_list = [
            w for w in custom_list
            if str(w.get("id", "")).strip().lower() != wid_clean
        ]
        CUSTOM_WORKS_PATH.write_text(json.dumps(custom_list, indent=2), encoding="utf-8")
        print(f"[*] Removed '{wid_clean}' from custom_works.json ({before_cnt} -> {len(custom_list)} custom works)")

    # 2. Remove from scan_history.csv
    if os.path.exists(SCAN_LOG_PATH):
        df = pd.read_csv(SCAN_LOG_PATH)
        df = df[~df["sector_id"].astype(str).str.upper().str.startswith(wid_upper + "_")]
        df.to_csv(SCAN_LOG_PATH, index=False)

    # 3. Remove from Discovery Archive SQLite DB (data/public_candidates.db)
    db_path = Path("data/public_candidates.db")
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "DELETE FROM public_candidates WHERE UPPER(sector_id) LIKE ?",
                (f"{wid_upper}_%",),
            )
            conn.commit()

    # 4. Delete cached XML, aligned CSVs, plots, and Codex HTML files
    for pat in [
        f"data/{wid_clean}_*.xml",
        f"data/{wid_clean}_*_aligned.csv",
        f"candidates/{wid_clean}_*",
        f"candidates/*/{wid_clean}_*",
    ]:
        for filepath in glob.glob(pat):
            try:
                os.remove(filepath)
            except OSError:
                pass

def get_scan_history() -> dict:
    if not os.path.exists(SCAN_LOG_PATH):
        return {}
    df = pd.read_csv(SCAN_LOG_PATH)
    return {
        str(row["sector_id"]): f"{row['ghost_count']} Ghosts ({row['max_snr']}σ)"
        for _, row in df.iterrows()
    }

def log_completed_scan(sector_id: str, title: str, ghost_count: int, boundary_count: int, max_snr: float):
    os.makedirs("data", exist_ok=True)
    history_df = pd.read_csv(SCAN_LOG_PATH) if os.path.exists(SCAN_LOG_PATH) else pd.DataFrame(
        columns=["sector_id", "title", "ghost_count", "boundary_count", "max_snr"]
    )
    history_df = history_df[history_df["sector_id"] != sector_id]
    new_row = pd.DataFrame([{
        "sector_id": sector_id,
        "title": title,
        "ghost_count": ghost_count,
        "boundary_count": boundary_count,
        "max_snr": round(float(max_snr), 2)
    }])
    history_df = pd.concat([history_df, new_row], ignore_index=True)
    history_df.to_csv(SCAN_LOG_PATH, index=False)

def parse_book_selection(user_input: str, valid_books: list[str]) -> list[str]:
    raw = user_input.strip().upper()
    if raw == "ALL":
        return valid_books
    if "-" in raw:
        parts = raw.split("-", 1)
        try:
            start, end = int(parts[0]), int(parts[1])
            selected = [str(b) for b in range(start, end + 1) if str(b) in valid_books]
            if selected:
                return selected
        except ValueError:
            pass
    if raw in valid_books:
        return [raw]
    return [valid_books[0]]

def interactive_select_target() -> list[dict]:
    history = get_scan_history()

    print("\n" + "=" * 92)
    print(" LOST TEXT FINDER — GRECO-ROMAN COMPILATION ARCHIVE (Perseus Digital Library)")
    print(" Online Library Reference: https://scaife.perseus.org/")
    print("=" * 92)
    print(f" {'#':<4} {'Work Title':<44} {'Lang':<7} {'Available Books':<24} {'Progress'}")
    print("-" * 92)

    current_genre = ""
    for idx, work in enumerate(CORPUS_REGISTRY, start=1):
        if work["genre"] != current_genre:
            current_genre = work["genre"]
            print(f"\n [{current_genre}]")

        scanned_cnt = sum(
            1 for b in work["books"]
            if f"{work['id'].upper()}_{b.zfill(2)}" in history
        )
        total_cnt = len(work["books"])
        prog_str = f"{scanned_cnt}/{total_cnt} Scanned"
        print(f"  {idx:<3d} {work['title']:<44} {work['lang']:<7} {work['book_label']:<24} {prog_str}")

    print("\n [Survey Modes]")
    print("  R   Random Unscanned Book (Picks an unanalyzed book at random across the archive)")
    print("=" * 92)

    choice = input("\nSelect a Work [1-10] or [R]andom: ").strip().upper()

    if choice == "R":
        unscanned_pool = []
        for work in CORPUS_REGISTRY:
            for b in work["books"]:
                sec_id = f"{work['id'].upper()}_{b.zfill(2)}"
                if sec_id not in history:
                    unscanned_pool.append((work, b))
        if not unscanned_pool:
            work = random.choice(CORPUS_REGISTRY)
            b = random.choice(work["books"])
        else:
            work, b = random.choice(unscanned_pool)

        sec_id = f"{work['id'].upper()}_{b.zfill(2)}"
        print(f"\n[*] RANDOM SELECTION: {work['title']} — Book {b} ({sec_id})")
        return [{**work, "selected_book": b, "sector_id": sec_id}]

    try:
        w_idx = int(choice) - 1
        work = CORPUS_REGISTRY[w_idx] if 0 <= w_idx < len(CORPUS_REGISTRY) else CORPUS_REGISTRY[0]
    except ValueError:
        work = CORPUS_REGISTRY[0]

    print("\n" + "-" * 92)
    print(f" SELECTED WORK: {work['title']} ({work['lang']})")
    print("-" * 92)

    row_items = []
    for b in work["books"]:
        sec_id = f"{work['id'].upper()}_{b.zfill(2)}"
        status = history.get(sec_id, "Unscanned")
        row_items.append(f"Book {b:>2}: [{status:<18}]")
        if len(row_items) == 3:
            print("  " + "   ".join(row_items))
            row_items = []
    if row_items:
        print("  " + "   ".join(row_items))

    print("-" * 92)
    b_input = input(
        f"Enter Book # (e.g. '{work['books'][0]}'), a Range (e.g. '1-5'), or 'ALL': "
    ).strip()

    chosen_books = parse_book_selection(b_input, work["books"])
    targets = []
    for b in chosen_books:
        sec_id = f"{work['id'].upper()}_{b.zfill(2)}"
        targets.append({**work, "selected_book": b, "sector_id": sec_id})

    print(f"\n[*] Queued {len(targets)} book(s) from {work['title']}: {', '.join(chosen_books)}")
    return targets

if __name__ == "__main__":
    interactive_select_target()