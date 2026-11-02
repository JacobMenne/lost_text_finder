# Lost Text Finder

**A computational philology and signal-processing pipeline that scans surviving Greco-Roman prose compilations ("cover-texts") for uncredited fragments of lost ancient histories, sea-voyage manuals (*periploi*), and embedded verse—complete with a local HTML5 Parchment Codex web application.**

---

## Overview

Over 90% of classical Greek and Roman literature has been lost. However, surviving encyclopedic compilers—such as **Strabo**, **Diodorus Siculus**, **Pausanias**, **Apollodorus**, **Athenaeus**, **Diogenes Laertius**, **Pliny the Elder**, and **Aulus Gellius**—worked directly from now-vanished scrolls in ancient libraries, frequently copying or closely paraphrasing long passages without modern quotation marks or explicit citations.

**Lost Text Finder** applies sliding-window information theory and forensic stylometry directly to aligned **Perseus TEI-XML** Greek, Latin, and English editions to isolate the exact paragraphs where a foreign author's statistical signature takes over.

---

## Key Features

### 1. Stylized HTML5 Parchment Codex Application
* **Zero-Config Local Web Server (`http.server`):** Runs identically on Linux, Windows, and macOS in any modern browser (`http://127.0.0.1:8765/`) with a clean one-click shutdown handler.
* **Customizable Tome Aesthetics:** Bundled **Appearance Menu** with live switching between *Aged Parchment*, *Illuminated Vellum*, *Alexandria Night*, and *Modern Academic Press*, plus typeface, border rule, font size, and margin sliders persisted via `localStorage`.
* **Full Book Context Reader:** Every flagged anomaly links directly to its exact `Book.Chapter.Section` inside a complete bilingual (Greek/Latin + English) book reader with inline anomaly highlighting.

### 2. Three-Channel Stylometric Anomaly Scanner
Slides a configurable word window (default `180` words, auto-scaling down to `90` words for short texts and epitomes) across the original Greek or Latin text and computes robust Median Absolute Deviation ($\sigma$) Signal-to-Noise Ratios across three specialized channels:
1. **Lost Historian Channel (`LOST_HISTORIAN`):** Detects abrupt drops in **vowel-hiatus collision rates** (characteristic of Isocratean/Ephorean prose) paired with **Jensen-Shannon Divergence (JSD)** spikes in subconscious connective particle distributions ($\delta\varepsilon, \mu\varepsilon\nu, \gamma\alpha\rho, \circ\upsilon\nu$ / *autem, enim, igitur, atque*).
2. **Lost Periplus / Sea-Voyage Channel (`LOST_PERIPLUS`):** Measures dense clusters of ancient maritime logbook vocabulary—sailing distances in *stadia* or *milia passuum*, harbors (*limen/portus*), headlands, anchorages, and directional sequence markers.
3. **Embedded Verse & Mythic Channel (`LOST_VERSE_MYTH`):** Converts Greek and Latin words into binary Long/Short syllable waves (`1`/`0`) to detect embedded dactylic hexameter and tragic iambic cadences inside prose narrative.

### 3. Self-Calibrating Burrows' Delta Attribution
* Automatically harvests explicitly cited passages inside each book (*Ephorus*, *Artemidorus*, *Timaeus*, *Posidonius*, *Callisthenes*, *Archaic Epic / Nostoi*, *Attic Tragedy*, *Early Roman Annalists*) to build standardized Z-score reference profiles.
* Computes **Burrows' Delta** similarity percentages for every **Uncredited Passage** and **Extended Borrowing** (where copying continues past a closed citation).

### 4. Dual SQLite Architecture: Discovery Archive & Private Bookmarks
* **Discovery Archive (`data/public_candidates.db`):** Automatically indexes all discovered anomalies ($\ge 2.5\sigma$) across scanned books, featuring a two-tier toggle (**Tier 1: $3.0\sigma–8.0\sigma+$ Extreme Statistical Anomalies** vs. **Tier 2: $2.5\sigma–3.0\sigma$ Moderate Stylistic Shifts**) and instant keyword search with inline `<mark>` highlighting.
* **Personal Florilegium Bookmarks (`data/personal_bookmarks.db`):** Strictly local, git-ignored SQLite vault allowing users to bookmark passages, organize them into custom thematic folders, and attach private research notes.

### 5. Extensible Corpus Importer
* Ships with 10 complete Greek and Latin multi-volume compilations (140+ books in numerical order) across 5 classical genres.
* Includes a built-in **Add New Text to Archive** importer supporting any TEI-XML work from [Perseus Greek (`canonical-greekLit`)](https://github.com/PerseusDL/canonical-greekLit), [Perseus Latin (`canonical-latinLit`)](https://github.com/PerseusDL/canonical-latinLit), or [OpenGreekAndLatin (`First1KGreek`)](https://github.com/OpenGreekAndLatin/First1KGreek) with automatic XML book discovery and genre classification.

---

## Quickstart & Installation

### 1. Clone the Repository
```bash
git clone [https://github.com/JacobMenne/lost_text_finder.git](https://github.com/JacobMenne/lost_text_finder.git)
cd lost_text_finder