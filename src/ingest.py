import os
import re
import unicodedata
import requests
import pandas as pd
from lxml import etree


def resolve_perseus_urls(repo: str, dir_path: str, lang: str) -> tuple[str, str | None]:
    """
    Queries the GitHub contents API for the author's folder (with a direct HEAD fallback)
    to dynamically find the exact .perseus-grc/lat*.xml and .perseus-eng*.xml URLs.
    Never breaks when Perseus bumps edition numbers (e.g. eng2 -> eng3 or grc2 -> grc4).
    """
    src_tag = "grc" if lang == "GREEK" else "lat"
    api_url = f"https://api.github.com/repos/{repo}/contents/{dir_path}"

    orig_url = None
    eng_url = None

    try:
        resp = requests.get(api_url, timeout=20)
        if resp.status_code == 200:
            files = [item["name"] for item in resp.json() if item["name"].endswith(".xml")]
            src_matches = sorted([f for f in files if f"perseus-{src_tag}" in f])
            eng_matches = sorted([f for f in files if "perseus-eng" in f])
            if src_matches:
                orig_url = f"https://raw.githubusercontent.com/{repo}/master/{dir_path}/{src_matches[-1]}"
            if eng_matches:
                eng_url = f"https://raw.githubusercontent.com/{repo}/master/{dir_path}/{eng_matches[-1]}"
    except Exception:
        pass

    # Fallback probe if unauthenticated GitHub API is rate-limited
    parts = dir_path.split("/")
    prefix = f"{parts[-2]}.{parts[-1]}"
    base_raw = f"https://raw.githubusercontent.com/{repo}/master/{dir_path}/{prefix}"

    if not orig_url:
        for ver in ["2", "4", "1", "3", "5", "6"]:
            candidate = f"{base_raw}.perseus-{src_tag}{ver}.xml"
            if requests.head(candidate, timeout=10).status_code == 200:
                orig_url = candidate
                break

    if not eng_url:
        for ver in ["2", "3", "1", "4", "5"]:
            candidate = f"{base_raw}.perseus-eng{ver}.xml"
            if requests.head(candidate, timeout=10).status_code == 200:
                eng_url = candidate
                break

    if not orig_url:
        raise FileNotFoundError(f"Could not locate source XML in {repo}/{dir_path}")

    return orig_url, eng_url


def download_xml(url: str, local_path: str) -> str:
    """Downloads a Perseus TEI-XML file once and caches it locally in data/."""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    if not os.path.exists(local_path):
        print(f"[*] Downloading {os.path.basename(url)} -> {local_path}...")
        resp = requests.get(url, timeout=90)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(resp.content)
    return local_path


def clean_source_text(text: str, lang: str) -> str:
    norm = unicodedata.normalize("NFC", text).lower()
    if lang == "GREEK":
        cleaned = re.sub(r"[^\u0370-\u03ff\u1f00-\u1fff\s]", " ", norm)
    else:
        cleaned = re.sub(r"[^a-z\s]", " ", norm)
    return re.sub(r"\s+", " ", cleaned).strip()


def clean_english_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_notes(elem) -> str:
    """
    Removes translator <note> footnotes while preserving any sentence text
    stored in note.tail (which lxml otherwise deletes with parent.remove).
    """
    clone = etree.fromstring(etree.tostring(elem))
    for note in clone.xpath(".//*[local-name()='note']"):
        tail_text = note.tail or ""
        prev = note.getprevious()
        parent = note.getparent()
        if parent is None:
            continue
        if prev is not None:
            prev.tail = (prev.tail or "") + " " + tail_text
        else:
            parent.text = (parent.text or "") + " " + tail_text
        parent.remove(note)
    return " ".join(clone.itertext())


def extract_book_sections(xml_path: str, target_book: str, lang: str, is_source: bool = True) -> dict:
    """
    Universal Perseus TEI-XML extractor.
    Handles both 3-tier (book -> chapter -> section) and 2-tier (book -> chapter/section) trees,
    as well as single-book works where chapters are the top-level divs.
    """
    parser = etree.XMLParser(recover=True, resolve_entities=False, huge_tree=True)
    tree = etree.parse(xml_path, parser)
    root = tree.getroot()

    sections = {}

    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        tag = etree.QName(el).localname
        if not tag.startswith("div"):
            continue

        div_type = (el.get("subtype") or el.get("type") or "").lower()
        div_n = str(el.get("n") or "").strip()

        if div_type in ("book", "textpart", "epitome") and div_n == str(target_book):
            child_divs = [
                c for c in el
                if isinstance(c.tag, str) and etree.QName(c).localname.startswith("div")
            ]

            if not child_divs:
                raw = _strip_notes(el)
                sections[f"{target_book}.1"] = (
                    clean_source_text(raw, lang) if is_source else clean_english_text(raw)
                )
                break

            for c_el in child_divs:
                c_n = str(c_el.get("n") or "1").strip()
                grand_divs = [
                    g for g in c_el
                    if isinstance(g.tag, str) and etree.QName(g).localname.startswith("div")
                ]

                if grand_divs:
                    for g_el in grand_divs:
                        g_n = str(g_el.get("n") or "1").strip()
                        ref_id = f"{target_book}.{c_n}.{g_n}"
                        raw = _strip_notes(g_el)
                        sections[ref_id] = (
                            clean_source_text(raw, lang) if is_source else clean_english_text(raw)
                        )
                else:
                    ref_id = f"{target_book}.{c_n}"
                    raw = _strip_notes(c_el)
                    sections[ref_id] = (
                        clean_source_text(raw, lang) if is_source else clean_english_text(raw)
                    )

            if sections:
                break

    return sections


def ingest_target_book(target: dict) -> str:
    work_id = target["id"]
    book_num = str(target["selected_book"])
    sector_id = target["sector_id"].lower()
    lang = target["lang"]

    orig_cache = f"data/{work_id}_orig.xml"
    eng_cache = f"data/{work_id}_eng.xml"

    # Only query GitHub if the XML files aren't already cached locally
    if not os.path.exists(orig_cache) or not os.path.exists(eng_cache):
        orig_url, eng_url = resolve_perseus_urls(target["repo"], target["dir_path"], lang)
        download_xml(orig_url, orig_cache)
        if eng_url:
            download_xml(eng_url, eng_cache)
    else:
        print(f"[*] Using cached XML files for {target['title']}")

    print(f"[*] Aligning {target['title']} — Book {book_num} ({lang} + English)...")
    orig_secs = extract_book_sections(orig_cache, book_num, lang=lang, is_source=True)
    eng_secs = (
        extract_book_sections(eng_cache, book_num, lang=lang, is_source=False)
        if os.path.exists(eng_cache)
        else {}
    )

    eng_chapter_fallback = {}
    for ref, txt in eng_secs.items():
        chap_prefix = ".".join(ref.split(".")[:2])
        eng_chapter_fallback.setdefault(chap_prefix, []).append(txt)

    rows = []
    for ref_id, src_text in orig_secs.items():
        words = src_text.split()
        if len(words) < 5:
            continue

        eng_text = eng_secs.get(ref_id)
        if not eng_text:
            chap_prefix = ".".join(ref_id.split(".")[:2])
            fallback_list = eng_chapter_fallback.get(chap_prefix, [])
            eng_text = (
                " ".join(fallback_list)[:1200]
                if fallback_list
                else "[Untranslated in Perseus XML — Greek/Latin text analyzed directly]"
            )

        rows.append({
            "sector_id": target["sector_id"],
            "work_title": target["title"],
            "language": lang,
            "cts_ref": ref_id,
            "source_text": src_text,
            "english_text": eng_text,
            "word_count": len(words),
        })

    df = pd.DataFrame(rows)
    out_csv = f"data/{sector_id}_aligned.csv"
    df.to_csv(out_csv, index=False)
    print(f"[+] Aligned {len(df)} sections ({df['word_count'].sum():,} {lang.title()} words) -> {out_csv}")
    return out_csv