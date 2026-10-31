from archive_db import record_public_candidates
from pathlib import Path
from codex_reader import generate_codex_html, open_file_cross_platform
import os
import textwrap
import unicodedata
import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
import matplotlib.pyplot as plt

from catalog import log_completed_scan


def strip_accents(word: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", word)
        if unicodedata.category(c) != "Mn"
    )


def format_block(text: str, width: int = 74, indent: str = "  │ ") -> str:
    """Wraps long text into a clean, readable column block for the terminal."""
    cleaned = " ".join(str(text).split())
    return textwrap.fill(
        cleaned,
        width=width,
        initial_indent=indent,
        subsequent_indent=indent,
    )


# --- GREEK & LATIN FORENSIC DICTIONARIES ---
LANG_CONFIG = {
    "GREEK": {
        "particles": [
            "δε", "και", "μεν", "γαρ", "τε", "ουν", "αλλα", "αλλ",
            "δη", "γε", "ουδε", "μηδε", "ωστε", "επει", "ωσπερ", "διοπερ"
        ],
        "periplus_stems": (
            "σταδι", "λιμην", "λιμεν", "υφορμ", "ακρωτηρ", "ακρα",
            "νησο", "νησι", "πλου", "παραπλ", "ειτα", "εφεξη", "μεταξυ", "απο", "μεχρι"
        ),
        "vowels": set("αεηιουω"),
        "long_vowels": set("ηω"),
        "short_vowels": set("εο"),
        "diphthongs": ("αι", "ει", "οι", "υι", "αυ", "ευ", "ου", "ηυ"),
        "poetic_glue": "τε",
    },
    "LATIN": {
        "particles": [
            "et", "in", "ad", "autem", "enim", "igitur", "vero", "atque",
            "ac", "sed", "nam", "itaque", "quoque", "quidem", "tamen", "aut"
        ],
        "periplus_stems": (
            "portu", "promunturi", "insul", "stadi", "passu", "mili",
            "inde", "deinde", "sinu", "oppid", "flum", "amne", "litor", "navig"
        ),
        "vowels": set("aeiouy"),
        "long_vowels": set("aeou"),
        "short_vowels": set("i"),
        "diphthongs": ("ae", "oe", "au", "eu"),
        "poetic_glue": "que",
    }
}

SUSPECT_AUTHORS = {
    "Ephorus (Lost Universal History)": ["ephorus"],
    "Artemidorus (Lost Periplus)": ["artemidorus"],
    "Timaeus (Lost Western/Island History)": ["timaeus"],
    "Posidonius (Hellenistic History/Geography)": ["posidonius"],
    "Eratosthenes (Ancient Geographer)": ["eratosthenes"],
    "Theopompus / Callisthenes (Hellenistic History)": ["theopompus", "callisthenes", "hieronymus"],
    "Archaic Epic / Nostoi / Mythic Cycle": ["homer", "hesiod", "poet", "epic", "nostoi", "cypria"],
    "Attic Tragedy (Sophocles / Euripides / Aeschylus)": ["sophocles", "euripides", "aeschylus", "tragic"],
    "Lost Periploi / Naval Logs (Scylax / Pytheas / Nearchus)": ["scylax", "pytheas", "nearchus", "agatharchides", "onesicritus"],
    "Early Roman Annalists (Varro / Cato / Cornelius Nepos)": ["varro", "cato", "nepos", "juba", "agrippa"],
}

CITATION_VERBS = [
    "says", "according to", "writes", "records", "states",
    "mentions", "quotes", "relates", "tells us", "asserts"
]


def get_particle_distribution(base_words: list[str], lang: str) -> np.ndarray:
    plist = LANG_CONFIG[lang]["particles"]
    counts = np.array([base_words.count(p) for p in plist], dtype=float) + 0.5
    return counts / counts.sum()


def get_hiatus_rate(base_words: list[str], lang: str) -> float:
    if len(base_words) < 2:
        return 0.0
    vowels = LANG_CONFIG[lang]["vowels"]
    collisions = sum(
        1 for i in range(len(base_words) - 1)
        if base_words[i][-1] in vowels and base_words[i + 1][0] in vowels
    )
    return collisions / (len(base_words) - 1)


def get_periplus_density(base_words: list[str], lang: str) -> float:
    stems = LANG_CONFIG[lang]["periplus_stems"]
    hits = sum(1 for w in base_words if w.startswith(stems))
    return (hits / max(1, len(base_words))) * 100.0


def get_verse_metrical_score(base_words: list[str], lang: str) -> float:
    cfg = LANG_CONFIG[lang]
    vowels = cfg["vowels"]
    long_v = cfg["long_vowels"]
    short_v = cfg["short_vowels"]
    diph = cfg["diphthongs"]

    wave = []
    for w in base_words:
        i = 0
        while i < len(w):
            if w[i:i+2] in diph:
                wave.append("1")
                i += 2
            elif w[i] in long_v:
                wave.append("1")
                i += 1
            elif w[i] in short_v:
                rest = w[i+1:i+3]
                if len(rest) == 2 and all(c not in vowels for c in rest):
                    wave.append("1")
                else:
                    wave.append("0")
                i += 1
            elif w[i] in vowels:
                wave.append("0")
                i += 1
            else:
                i += 1

    wave_str = "".join(wave)
    if len(wave_str) < 12:
        return 0.0

    dactyls = wave_str.count("100100") + wave_str.count("10011")
    iambs = wave_str.count("010101")
    glue_bonus = sum(1 for w in base_words if w == cfg["poetic_glue"] or w.endswith(cfg["poetic_glue"])) * 0.4
    return (dactyls * 2.0 + iambs * 1.5 + glue_bonus) / (len(wave_str) / 10.0)


def extract_vector(base_words: list[str], lang: str) -> np.ndarray:
    if len(base_words) < 15:
        return np.zeros(19)
    p_dist = get_particle_distribution(base_words, lang)
    hiatus = get_hiatus_rate(base_words, lang)
    periplus = get_periplus_density(base_words, lang)
    meter = get_verse_metrical_score(base_words, lang)
    return np.concatenate([p_dist, [hiatus, periplus, meter]])


def robust_snr(series: np.ndarray, invert: bool = False) -> np.ndarray:
    med = np.median(series)
    mad = np.median(np.abs(series - med))
    sigma = max(1e-6, 1.4826 * mad)
    z = (med - series) / sigma if invert else (series - med) / sigma
    return np.clip(z, -2.5, 12.0)


def deduplicate_peaks(sub_df: pd.DataFrame, min_window_gap: int = 3) -> pd.DataFrame:
    """
    Keeps the highest-SNR window for each distinct passage anomaly while preventing
    adjacent overlapping sliding windows (within ±2 steps) from duplicating the same hit.
    """
    if sub_df.empty:
        return sub_df
    sorted_df = sub_df.sort_values("peak_snr", ascending=False)
    kept_rows = []
    kept_win_ids = []
    for _, row in sorted_df.iterrows():
        wid = int(row["window_id"])
        if all(abs(wid - kw) >= min_window_gap for kw in kept_win_ids):
            kept_rows.append(row)
            kept_win_ids.append(wid)
    return pd.DataFrame(kept_rows)


def print_candidate_card(hit: pd.Series, full_text: bool = False):
    """Prints a cleanly spaced, 74-column wrapped diagnostic card for a single anomaly."""
    print("\n  ┌" + "─" * 78 + "┐")
    print(f"  │ BOOK.CHAP.SEC: {hit['cts_span']:<18} Peak SNR: {hit['peak_snr']:.2f}σ ({hit['dominant_channel']})")
    print(f"  │ FINDING TYPE:  {hit['novelty_status']}")
    print(f"  │ 1st Suspect Match: {hit['primary_attribution']}")
    print(f"  │ 2nd Suspect Match: {hit['secondary_attribution']}")
    print(f"  │ Forensic Metrics:  Hiatus={hit['hiatus_rate']*100:.1f}% | JSD={hit['jsd']:.3f} | Periplus={hit['periplus_density']:.1f}")
    print("  ├" + "─" * 78 + "┤")

    raw_eng = " ".join(str(hit["english_text"]).split())
    if not full_text and len(raw_eng) > 550:
        # Cut cleanly on a space boundary so words are never sliced in half
        cut_eng = raw_eng[:550].rsplit(" ", 1)[0]
        display_eng = cut_eng + " ... [Use Explorer Menu below to read full uncut passage]"
    else:
        display_eng = raw_eng

    print(format_block(display_eng, width=74, indent="  │ "))
    print("  └" + "─" * 78 + "┘")


def interactive_post_scan_explorer(
    df_sec: pd.DataFrame,
    wdf: pd.DataFrame,
    ghost_df: pd.DataFrame,
    bound_df: pd.DataFrame,
    known_df: pd.DataFrame,
    suspect_sections: dict,
    codex_path: Path,
):
    """Interactive post-scan inspection console with Parchment Codex launcher."""
    while True:
        print("\n" + "═" * 82)
        print(" INTERACTIVE DISCOVERY EXPLORER")
        print("═" * 82)
        print(f"  [O] Open Stylized Parchment Codex Reader ({codex_path.name} — Browser GUI)")
        print(f"  [U] Uncredited Passages ({len(ghost_df)} found — Foreign style with NO source named nearby)")
        print(f"  [E] Extended Borrowings ({len(bound_df)} found — Source named earlier, copying continues here)")
        print(f"  [K] Explicit Citations  ({len(known_df)} found — Lost author explicitly named in this section)")
        print(f"  [S] Suspect Lineup Evidence ({len(suspect_sections)} named author profiles in this book)")
        print("  [C] Read Surrounding Book Context (Enter any Book.Chap.Sec, e.g. '14.3.8' or '14.6.3')")
        print("  [Q] Finish & Return")
        print("─" * 82)

        cmd = input("Choose an explorer option [O / U / E / K / S / C / Q]: ").strip().upper()

        if cmd in ("Q", ""):
            break

        elif cmd == "O":
            print(f"\n  [*] Launching Stylized Parchment Codex Reader -> {codex_path}")
            open_file_cross_platform(codex_path)

        elif cmd in ("U", "G"):
            if ghost_df.empty:
                print("\n  [!] No Uncredited Passages above threshold in this book.")
            else:
                print(f"\n  === ALL {len(ghost_df)} UNCREDITED PASSAGES (FULL UNCUT TEXT) ===")
                for _, hit in ghost_df.iterrows():
                    print_candidate_card(hit, full_text=True)

        elif cmd in ("E", "B"):
            if bound_df.empty:
                print("\n  [!] No Extended Borrowings above threshold in this book.")
            else:
                print(f"\n  === ALL {len(bound_df)} EXTENDED BORROWINGS (FULL UNCUT TEXT) ===")
                for _, hit in bound_df.iterrows():
                    print_candidate_card(hit, full_text=True)

        elif cmd == "K":
            if known_df.empty:
                print("\n  [!] No Explicit Citations above threshold in this book.")
            else:
                print(f"\n  === ALL {len(known_df)} EXPLICIT CITATIONS (FULL UNCUT TEXT) ===")
                for _, hit in known_df.iterrows():
                    print_candidate_card(hit, full_text=True)

        elif cmd == "S":
            print("\n  === SUSPECT LINEUP HARVESTED FROM EXPLICIT CITATIONS IN THIS BOOK ===")
            for idx, (s_label, sec_indices) in enumerate(suspect_sections.items(), start=1):
                refs = [str(df_sec.loc[i, "cts_ref"]) for i in sec_indices]
                print(f"   [{idx}] {s_label:<52} ({len(refs)} sections: {', '.join(refs[:6])})")

            sub = input("\n  Enter Suspect # to read their named training passages (or Enter to cancel): ").strip()
            try:
                s_idx = int(sub) - 1
                s_label = list(suspect_sections.keys())[s_idx]
                sec_indices = suspect_sections[s_label]
                print(f"\n  --- NAMED REFERENCE PASSAGES FOR: {s_label} ---")
                for i in sec_indices[:5]:
                    ref = df_sec.loc[i, "cts_ref"]
                    print(f"\n  [BOOK.CHAP.SEC: {ref}]")
                    print(format_block(df_sec.loc[i, "english_text"], width=74, indent="    │ "))
            except (ValueError, IndexError):
                pass

        elif cmd == "C":
            target_ref = input("  Enter Book.Chap.Sec to inspect surrounding context (e.g. '14.3.7'): ").strip()
            matches = df_sec.index[df_sec["cts_ref"] == target_ref].tolist()
            if not matches:
                matches = df_sec.index[df_sec["cts_ref"].str.startswith(target_ref)].tolist()

            if not matches:
                print(f"  [!] Section '{target_ref}' not found. Available range: {df_sec['cts_ref'].iloc[0]} to {df_sec['cts_ref'].iloc[-1]}")
            else:
                center_idx = matches[0]
                start_i = max(0, center_idx - 2)
                end_i = min(len(df_sec) - 1, center_idx + 2)
                print(f"\n  === SURROUNDING CONTEXT: {df_sec.loc[start_i, 'cts_ref']} to {df_sec.loc[end_i, 'cts_ref']} ===")
                for i in range(start_i, end_i + 1):
                    row = df_sec.loc[i]
                    marker = ">>> TARGET SECTION <<<" if i == center_idx else ""
                    print(f"\n  [BOOK.CHAP.SEC: {row['cts_ref']}] {marker}")
                    print("  ┌" + "─" * 76 + "┐")
                    print(format_block(row["english_text"], width=72, indent="  │ "))
                    print("  └" + "─" * 76 + "┘")


def scan_and_attribute(
    aligned_csv: str,
    window_size: int = 180,
    stride: int = 45,
    snr_threshold: float = 2.8,
    headless: bool = False,
) -> Path | None:
    df = pd.read_csv(aligned_csv)
    if df.empty:
        print("[!] Aligned CSV is empty — skipping scan.")
        return None

    sector_id = str(df.loc[0, "sector_id"])
    work_title = str(df.loc[0, "work_title"])
    lang = str(df.loc[0, "language"])

    tokens_base = []
    # Auto-scale window resolution for short texts / epitomes (< 4,500 words)
    if len(tokens_base) < 4500 and window_size > 100:
        window_size = 90
        stride = 22
    token_sec_idx = []
    for idx, row in df.iterrows():
        for w in str(row["source_text"]).split():
            bw = strip_accents(w)
            if bw:
                tokens_base.append(bw)
                token_sec_idx.append(idx)

    if len(tokens_base) < window_size:
        print(f"[!] Text too short ({len(tokens_base)} words) for {window_size}-word window.")
        return None

    host_p_dist = get_particle_distribution(tokens_base, lang)

    windows = []
    window_vectors = []
    for start in range(0, len(tokens_base) - window_size, stride):
        end = start + window_size
        w_tokens = tokens_base[start:end]

        s_idx = token_sec_idx[start]
        c_idx = token_sec_idx[start + window_size // 2]
        e_idx = token_sec_idx[end - 1]
        cts_span = (
            str(df.loc[s_idx, "cts_ref"])
            if s_idx == e_idx
            else f"{df.loc[s_idx, 'cts_ref']}–{df.loc[e_idx, 'cts_ref']}"
        )
        eng_span = " ".join(df.loc[s_idx:e_idx, "english_text"].dropna().unique())
        center_eng = str(df.loc[c_idx, "english_text"])

        vec = extract_vector(w_tokens, lang)
        window_vectors.append(vec)

        p_dist = vec[:16]
        hiatus, periplus, meter = vec[16], vec[17], vec[18]
        jsd = jensenshannon(p_dist, host_p_dist)

        windows.append({
            "sector_id": sector_id,
            "window_id": len(windows),
            "token_start": start,
            "sec_start_idx": s_idx,
            "sec_center_idx": c_idx,
            "sec_end_idx": e_idx,
            "cts_span": cts_span,
            "jsd": round(float(jsd), 4),
            "hiatus_rate": round(float(hiatus), 4),
            "periplus_density": round(float(periplus), 2),
            "verse_meter": round(float(meter), 3),
            "center_english": center_eng,
            "english_text": eng_span,
        })

    wdf = pd.DataFrame(windows)
    win_mat = np.array(window_vectors)

    jsd_snr = robust_snr(wdf["jsd"].values, invert=False)
    hiatus_drop_snr = robust_snr(wdf["hiatus_rate"].values, invert=True)

    wdf["historian_snr"] = np.round(0.55 * hiatus_drop_snr + 0.45 * jsd_snr, 2)
    wdf["periplus_snr"] = np.round(robust_snr(wdf["periplus_density"].values, invert=False), 2)
    wdf["verse_snr"] = np.round(0.65 * robust_snr(wdf["verse_meter"].values, invert=False) + 0.35 * jsd_snr, 2)

    snr_cols = ["historian_snr", "periplus_snr", "verse_snr"]
    ch_names = ["LOST_HISTORIAN", "LOST_PERIPLUS", "LOST_VERSE_MYTH"]
    snr_vals = wdf[snr_cols].values
    wdf["peak_snr"] = np.max(snr_vals, axis=1)
    wdf["dominant_channel"] = [ch_names[i] for i in np.argmax(snr_vals, axis=1)]

    feat_mean = np.mean(win_mat, axis=0)
    feat_std = np.where(np.std(win_mat, axis=0) < 1e-6, 1.0, np.std(win_mat, axis=0))
    win_z = (win_mat - feat_mean) / feat_std

    suspect_profiles = {}
    suspect_sections = {}
    for s_label, kw_list in SUSPECT_AUTHORS.items():
        matched_win = [
            i for i, eng in enumerate(wdf["center_english"])
            if any(k in eng.lower() for k in kw_list)
        ]
        matched_sec = [
            i for i, eng in enumerate(df["english_text"].fillna(""))
            if any(k in eng.lower() for k in kw_list)
        ]
        if matched_win:
            suspect_profiles[s_label] = np.mean(win_z[matched_win], axis=0)
            suspect_sections[s_label] = matched_sec

    all_author_keywords = [k for kw in SUSPECT_AUTHORS.values() for k in kw]

    statuses = []
    first_match = []
    second_match = []

    for i, row in wdf.iterrows():
        center_low = str(row["center_english"]).lower()
        span_low = str(row["english_text"]).lower()

        center_named = any(k in center_low for k in all_author_keywords) or any(v in center_low for v in CITATION_VERBS)
        span_named = any(k in span_low for k in all_author_keywords) or any(v in span_low for v in CITATION_VERBS)

        prev_eng = " ".join(wdf.loc[max(0, i - 3):max(0, i - 1), "center_english"]).lower() if i > 0 else ""
        prev_named = any(k in prev_eng for k in all_author_keywords)

        if center_named:
            statuses.append("EXPLICIT_CITATION (Named Source)")
        elif span_named or prev_named:
            statuses.append("EXTENDED_BORROWING (Continues Past Citation)")
        else:
            statuses.append("UNCREDITED_PASSAGE (No Source Named)")

        if suspect_profiles:
            deltas = {}
            for s_label, s_vec in suspect_profiles.items():
                dist = np.mean(np.abs(win_z[i] - s_vec))
                sim_pct = round(max(0.0, 100.0 * np.exp(-0.55 * dist)), 1)
                deltas[s_label] = sim_pct
            ranked = sorted(deltas.items(), key=lambda x: x[1], reverse=True)
            first_match.append(f"{ranked[0][0]} ({ranked[0][1]}%)")
            second_match.append(f"{ranked[1][0]} ({ranked[1][1]}%)" if len(ranked) > 1 else "N/A")
        else:
            first_match.append(f"Unattributed {row['dominant_channel']}")
            second_match.append("N/A")

    wdf["novelty_status"] = statuses
    wdf["primary_attribution"] = first_match
    wdf["secondary_attribution"] = second_match

    cand_dir = Path("candidates")
    (cand_dir / "tentative_ghosts").mkdir(parents=True, exist_ok=True)
    (cand_dir / "boundary_extensions").mkdir(parents=True, exist_ok=True)
    (cand_dir / "verified_known").mkdir(parents=True, exist_ok=True)

    sec_low = sector_id.lower()
    high_snr = wdf[wdf["peak_snr"] >= snr_threshold]

    ghost_df = deduplicate_peaks(high_snr[high_snr["novelty_status"].str.startswith("UNCREDITED")])
    bound_df = deduplicate_peaks(high_snr[high_snr["novelty_status"].str.startswith("EXTENDED")])
    known_df = deduplicate_peaks(high_snr[high_snr["novelty_status"].str.startswith("EXPLICIT")])

    ghost_df.to_csv(cand_dir / "tentative_ghosts" / f"{sec_low}_ghosts.csv", index=False)
    bound_df.to_csv(cand_dir / "boundary_extensions" / f"{sec_low}_boundaries.csv", index=False)
    known_df.to_csv(cand_dir / "verified_known" / f"{sec_low}_known.csv", index=False)

    # Save 3-Panel Diagnostic Plot
    fig, axes = plt.subplots(3, 1, figsize=(13, 8.5), sharex=True)
    plot_cfg = [
        ("historian_snr", "Channel 1: Lost Historian SNR (Hiatus Drop + Particle JSD)", "#d95f02"),
        ("periplus_snr", "Channel 2: Lost Periplus / Geographical Log SNR", "#1b9e77"),
        ("verse_snr", "Channel 3: Embedded Verse / Mythic Cadence SNR", "#7570b3"),
    ]
    for ax, (col, title, color) in zip(axes, plot_cfg):
        ax.plot(wdf["window_id"], wdf[col], color=color, lw=1.7)
        ax.axhline(snr_threshold, color="crimson", linestyle="--", alpha=0.75, label=f"{snr_threshold:.1f}σ Threshold")
        ax.set_ylabel("SNR (σ)")
        ax.set_title(f"{sector_id} — {title}", fontweight="bold")
        ax.grid(alpha=0.25)
        ax.legend(loc="upper right")

    axes[-1].set_xlabel(f"Sliding Window Index ({window_size}-Word Windows across {work_title})")
    plt.tight_layout()
    plot_path = cand_dir / f"{sec_low}_diagnostic_scan.png"
    plt.savefig(plot_path, dpi=180)
    plt.close(fig)

    codex_path = cand_dir / f"{sec_low}_codex.html"
    generate_codex_html(
        df_sec=df,
        wdf=wdf,
        ghost_df=ghost_df,
        bound_df=bound_df,
        known_df=known_df,
        suspect_sections=suspect_sections,
        plot_path=plot_path,
        output_html_path=codex_path,
        snr_threshold=snr_threshold,
        window_size=window_size,
    )

    # Automatically record Uncredited Passages & Extended Borrowings into the Public Candidates DB
    record_public_candidates(
        work_title=work_title,
        lang=lang,
        ghost_df=ghost_df,
        bound_df=bound_df,
    )

    max_snr = float(wdf["peak_snr"].max()) if not wdf.empty else 0.0
    log_completed_scan(
        sector_id=sector_id,
        title=work_title,
        ghost_count=len(ghost_df),
        boundary_count=len(bound_df),
        max_snr=max_snr,
    )

    print(f"[+] Scan complete: {work_title} ({sector_id}) | Peak {max_snr:.2f}σ -> {codex_path}")

    if headless:
        return codex_path

    open_file_cross_platform(codex_path)

    top_discoveries = pd.concat([ghost_df, bound_df]).sort_values("peak_snr", ascending=False).head(4)
    for _, hit in top_discoveries.iterrows():
        print_candidate_card(hit, full_text=False)

    interactive_post_scan_explorer(df, wdf, ghost_df, bound_df, known_df, suspect_sections, codex_path)
    return codex_path