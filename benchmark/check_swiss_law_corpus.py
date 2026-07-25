"""LAW-0 / F9 zero-token kill-or-resurrect gate (docs/capability-roadmap.md
section 4 FREE tier, item F9: "LAW-0: dump the 207 English rcds/swiss_legislation
titles, overlap against LEXam English items -- Kills or resurrects the corpus
arm for zero tokens"; pre-registered bar in section 3.7: "LAW-0 must show >=30%
topical overlap between the 207 English acts and LEXam English item subjects
before LAW-1 is funded").

Our LEXam law result was -14 and the diagnosed cause was corpus mismatch (the
project's STEM/US-law Wikipedia RAG index has no Swiss law; only 2/30
retrievals were on-topic in the logged rag_presolve run). This script checks,
with a LIVE probe (no paid LLM tokens -- this is a public-dataset lookup, the
same class of zero-token operation as `benchmark/load_lexam.py`'s own
datasets-server statistics check) whether a domain-correct Swiss-law corpus is
even obtainable:

  1. Probe the HuggingFace dataset `rcds/swiss_legislation` via the
     datasets-server `/info` and `/statistics` endpoints (cheap, no full
     download) for row count and language field distribution.
  2. Read ONLY the metadata columns (uuid/canton/language/title/short/
     abbreviation/sr_number -- never the multi-megabyte html_content/
     pdf_content columns) from all 5 parquet shards via column-projected
     HTTP range reads, to get the canton breakdown and to check whether the
     `title`/`short`/`abbreviation` fields are actually populated for the
     English subset (spoiler, verified below: they are NOT -- a real,
     load-bearing data-quality finding, not an assumption).
  3. Because `title` is blank for English rows, pull the REAL title from
     each English row's `html_content` (the official Fedlex HTML translation)
     via its `<h1 class="erlasstitel...">`/`<h2 class="erlasskurztitel...">`
     markup -- fetched only for the shard(s) that actually contain English
     rows (detected live, not hardcoded, so this stays correct if the
     dataset is reshuffled/resharded upstream).
  4. Load the LEXam ENGLISH items already logged in this repo (the four
     `*lexam*.jsonl` result files, deduped by question_id) and run a
     stopword-filtered keyword/title-overlap match against the 207 extracted
     English corpus titles, reporting how many LEXam items have a plausible
     serving act in the corpus at two thresholds (>=1 shared content word,
     >=2 shared content words).
  5. State the LAW-0 verdict against the pre-registered >=30% bar.

Usage:
    .venv/Scripts/python.exe benchmark/check_swiss_law_corpus.py

Requires network access to huggingface.co (a public dataset read, not a paid
LLM call -- zero tokens spent against the QuorumQA quota). No API keys, no
`quorumqa` client, no `qwen_client` import anywhere in this file.

Writes:
    benchmark/results/swiss_law_corpus_english_titles.csv  -- all 207 English
        rows: sr_number, title, short_title, uuid (the durable, offline-
        inspectable record of exactly what the corpus contains)
    benchmark/results/swiss_law_corpus_overlap.csv          -- per LEXam
        item: question_id, subject, n_shared_keywords, best matching corpus
        title(s)
    benchmark/results/swiss_law_corpus_check_data.json      -- everything
        above plus the raw dataset-level statistics, for re-checking any
        number quoted in the report
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import requests

RESULTS_DIR = Path(__file__).resolve().parent / "results"

DATASET_ID = "rcds/swiss_legislation"
DATASETS_SERVER = "https://datasets-server.huggingface.co"

LEXAM_RESULT_FILES = [
    "lexam_pilot_seed42.jsonl",
    "lever_control_lexam_seed42.jsonl",
    "lever_thinking_gate_lexam_seed42.jsonl",
    "lever_rag_recursive_lexam_seed42.jsonl",
]

TITLE_RE = re.compile(r'<h1[^>]*class="[^"]*erlasstitel[^"]*"[^>]*>(.*?)</h1>', re.S)
SHORT_TITLE_RE = re.compile(r'<h2[^>]*class="[^"]*erlasskurztitel[^"]*"[^>]*>(.*?)</h2>', re.S)
TAG_RE = re.compile(r"<[^>]+>")


def clean_html_fragment(s: str) -> str:
    s = TAG_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------------------
# Step 1-2: dataset-level stats + metadata-only column read (no content)
# ---------------------------------------------------------------------------


def fetch_dataset_stats() -> dict:
    info = requests.get(f"{DATASETS_SERVER}/info?dataset={DATASET_ID}", timeout=60).json()
    stats = requests.get(
        f"{DATASETS_SERVER}/statistics?dataset={DATASET_ID}&config=default&split=train", timeout=120
    ).json()
    by_col = {s["column_name"]: s["column_statistics"] for s in stats["statistics"]}
    return {
        "num_examples": info["dataset_info"]["default"]["splits"]["train"]["num_examples"],
        "download_size_bytes": info["dataset_info"]["default"]["download_size"],
        "dataset_size_bytes": info["dataset_info"]["default"]["dataset_size"],
        "language_frequencies": by_col.get("language", {}).get("frequencies", {}),
        "canton_frequencies": by_col.get("canton", {}).get("frequencies", {}),
        "is_active_frequencies": by_col.get("is_active", {}).get("frequencies", {}),
    }


def fetch_parquet_urls() -> list[str]:
    d = requests.get(f"{DATASETS_SERVER}/parquet?dataset={DATASET_ID}", timeout=60).json()
    return [f["url"] for f in d["parquet_files"] if f["split"] == "train"]


def fetch_metadata_only(parquet_urls: list[str]) -> pd.DataFrame:
    cols = ["uuid", "canton", "language", "title", "short", "abbreviation", "sr_number"]
    frames = [pd.read_parquet(u, columns=cols) for u in parquet_urls]
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Step 3: real titles from html_content, only for shards holding English rows
# ---------------------------------------------------------------------------


def fetch_english_titles(parquet_urls: list[str]) -> list[dict]:
    out = []
    for url in parquet_urls:
        lang_only = pd.read_parquet(url, columns=["language"])
        n_en = int((lang_only["language"] == "en").sum())
        if n_en == 0:
            continue
        df = pd.read_parquet(url, columns=["language", "sr_number", "uuid", "html_content"])
        en = df[df["language"] == "en"]
        for _, row in en.iterrows():
            html = row.get("html_content") or ""
            m = TITLE_RE.search(html)
            title = clean_html_fragment(m.group(1)) if m else ""
            m2 = SHORT_TITLE_RE.search(html)
            short_title = clean_html_fragment(m2.group(1)) if m2 else ""
            out.append({
                "uuid": row["uuid"],
                "sr_number": row["sr_number"],
                "title": title,
                "short_title": short_title,
                "combined_title": (title + " " + short_title).strip(),
            })
    return out


# ---------------------------------------------------------------------------
# Step 4: LEXam English items already logged + keyword overlap
# ---------------------------------------------------------------------------


def load_lexam_items() -> dict[str, dict]:
    items: dict[str, dict] = {}
    provenance: dict[str, set] = {}
    for fname in LEXAM_RESULT_FILES:
        path = RESULTS_DIR / fname
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                obj = row.get("engine") or row.get("baseline")
                if not obj or "item" not in obj:
                    continue
                item = obj["item"]
                qid = item["question_id"]
                items[qid] = {
                    "question_id": qid,
                    "subject": item.get("subject"),
                    "question": item["question"],
                }
                provenance.setdefault(qid, set()).add(fname)
    return items


# A naive stopword-filtered bag-of-words overlap (first attempt, kept for
# transparency) turns out to be dominated by generic connector words that
# happen to recur across many bureaucratic legal titles ("against", "human",
# "convention", "europe", "foreign", "major", "income", "taxes"...) -- e.g. 8
# of the 90 LEXam items matched SR 0.810.3 ("...Convention against
# Trafficking in Human Organs") purely on the words against/human/convention/
# europe, even though several of those LEXam items are legal-philosophy
# questions about human DIGNITY, not organ trafficking. That is coincidence,
# not topical relevance, and reporting it uncorrected would overstate the
# bar-clearing verdict. STOPWORDS below is the base filter (function words +
# generic legal boilerplate); MATCH_SCORE additionally applies inverse
# corpus-document-frequency weighting, computed live over the 207 extracted
# titles, so a word that recurs across dozens of unrelated titles ("foreign",
# "international", "against") contributes almost nothing to a match score,
# while a word distinctive to one or two titles ("obligations", "trafficking",
# "citizenship", "cartels") contributes close to its full weight. This is
# standard TF-IDF-style downweighting, applied here because a flat word-count
# threshold cannot distinguish a genuine subject match from a coincidental
# collision on common bureaucratic phrasing.

STOPWORDS = {
    "the", "of", "on", "and", "for", "in", "to", "a", "an", "is", "are", "or",
    "act", "federal", "ordinance", "swiss", "confederation", "law", "code",
    "concerning", "relating", "regarding", "with", "by", "at", "from", "into",
    "which", "that", "this", "these", "those", "as", "be", "it", "its",
    "certain", "other", "various", "general", "special", "amendment",
    "amending", "regulation", "regulations", "provisions", "provision",
    "national", "public", "private", "council", "assembly", "committee",
    "please", "indicate", "following", "statements", "correct", "incorrect",
    "based", "context", "select", "applicable", "true", "false", "statement",
    "case", "cases", "question", "questions", "answer", "answers", "part",
    "against", "between", "provided", "conditions", "understanding",
}

WORD_RE = re.compile(r"[a-zA-Z]{4,}")


def keywords(text: str) -> set[str]:
    return {w.lower() for w in WORD_RE.findall(text) if w.lower() not in STOPWORDS}


def build_idf(corpus_kw_sets: list[set[str]]) -> dict[str, float]:
    n_docs = len(corpus_kw_sets)
    df: Counter = Counter()
    for kw in corpus_kw_sets:
        for w in kw:
            df[w] += 1
    # +1 smoothing; a word in every title gets weight ~0, a word in exactly
    # one title gets weight ~log(n_docs).
    import math
    return {w: math.log(n_docs / c) for w, c in df.items()}


def overlap_match(lexam_items: dict[str, dict], corpus_titles: list[dict]) -> list[dict]:
    corpus_kw = [(c, keywords(c["combined_title"])) for c in corpus_titles]
    idf = build_idf([kw for _, kw in corpus_kw])

    out = []
    for qid, item in lexam_items.items():
        q_kw = keywords(item["question"])
        scored = []
        for corpus_entry, ckw in corpus_kw:
            shared = q_kw & ckw
            if shared:
                weighted = sum(idf.get(w, 0.0) for w in shared)
                scored.append((weighted, len(shared), corpus_entry["sr_number"], corpus_entry["combined_title"], sorted(shared, key=lambda w: -idf.get(w, 0.0))))
        scored.sort(key=lambda t: -t[0])
        best_score = scored[0][0] if scored else 0.0
        best_n = scored[0][1] if scored else 0
        out.append({
            "question_id": qid,
            "subject": item["subject"],
            "n_matches_ge1_raw": len(scored),
            "best_shared_keyword_count": best_n,
            "best_idf_weighted_score": best_score,
            "top_matches": [(s[1], s[2], s[3], s[4]) for s in scored[:3]],
        })
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    print("=" * 100)
    print(f"STEP 1: dataset-level stats for {DATASET_ID} (HF datasets-server, no download)")
    print("=" * 100)
    stats = fetch_dataset_stats()
    print(f"num_examples (verified live): {stats['num_examples']}")
    print(f"download_size: {stats['download_size_bytes'] / 1e6:.1f} MB compressed, "
          f"{stats['dataset_size_bytes'] / 1e9:.2f} GB decompressed")
    print(f"language distribution: {stats['language_frequencies']}")
    print(f"is_active distribution: {stats['is_active_frequencies']}")
    n_en_stats = stats["language_frequencies"].get("en", 0)

    print()
    print("=" * 100)
    print("STEP 2: metadata-only column read (uuid/canton/language/title/short/abbreviation/sr_number)")
    print("=" * 100)
    parquet_urls = fetch_parquet_urls()
    print(f"parquet shards: {len(parquet_urls)}")
    meta = fetch_metadata_only(parquet_urls)
    print(f"rows read: {len(meta)} (cross-check vs datasets-server num_examples: "
          f"{'MATCH' if len(meta) == stats['num_examples'] else 'MISMATCH'})")
    en_meta = meta[meta["language"] == "en"]
    print(f"English rows: {len(en_meta)} (cross-check vs statistics endpoint: "
          f"{'MATCH' if len(en_meta) == n_en_stats else 'MISMATCH'})")
    print(f"English rows' canton distribution: {dict(Counter(en_meta['canton']))}")
    n_title_blank = int((en_meta["title"] == "").sum())
    n_short_blank = int((en_meta["short"] == "").sum())
    n_abbr_blank = int((en_meta["abbreviation"] == "").sum())
    print(f"English rows with BLANK metadata `title` field: {n_title_blank}/{len(en_meta)} "
          f"({'ALL BLANK -- title column is unusable for English rows, must extract from html_content' if n_title_blank == len(en_meta) else 'partially populated'})")
    print(f"English rows with BLANK metadata `short` field: {n_short_blank}/{len(en_meta)}")
    print(f"English rows with BLANK metadata `abbreviation` field: {n_abbr_blank}/{len(en_meta)}")

    print()
    print("=" * 100)
    print("STEP 3: extracting REAL titles from html_content (Fedlex official English translations)")
    print("=" * 100)
    english_titles = fetch_english_titles(parquet_urls)
    print(f"English rows with content fetched: {len(english_titles)}")
    n_title_extracted = sum(1 for t in english_titles if t["title"])
    print(f"Titles successfully extracted via <h1 class=erlasstitel> regex: {n_title_extracted}/{len(english_titles)}")
    print()
    print("Sample (first 15, sorted by sr_number):")
    for t in sorted(english_titles, key=lambda x: x["sr_number"])[:15]:
        print(f"    SR {t['sr_number']:14s} {t['combined_title'][:90]}")

    print()
    print("=" * 100)
    print("STEP 4: LEXam English items already logged in this repo")
    print("=" * 100)
    lexam_items = load_lexam_items()
    print(f"Distinct LEXam question_ids across {LEXAM_RESULT_FILES}: {len(lexam_items)}")
    subj_dist = Counter(it["subject"] for it in lexam_items.values())
    print(f"Subject distribution: {dict(subj_dist)}")

    overlap = overlap_match(lexam_items, english_titles)
    n_total = len(overlap)

    # Naive raw counts (kept, but flagged): a pure stopword-filtered
    # word-count overlap is dominated by generic bureaucratic connector
    # words that recur across dozens of unrelated titles.
    n_raw_ge1 = sum(1 for o in overlap if o["best_shared_keyword_count"] >= 1)
    n_raw_ge2 = sum(1 for o in overlap if o["best_shared_keyword_count"] >= 2)
    pct_raw_ge1 = 100 * n_raw_ge1 / n_total if n_total else 0
    pct_raw_ge2 = 100 * n_raw_ge2 / n_total if n_total else 0

    # IDF-weighted score thresholds, calibrated against the score
    # distribution itself rather than picked blind. A word appearing in
    # exactly 1 of 207 titles scores ln(207/1)=5.33; in 2 titles, 4.64; in 5
    # titles, 3.71; in 10 titles, 3.03; in 20 titles, 2.34; in 50, 1.42. A
    # score >=4.0 therefore requires (roughly) one word private to <=3
    # corpus titles, or several moderately distinctive words together --
    # the level at which a match stops being explainable by generic legal
    # boilerplate. This is disclosed as a judgment call, not a discovered
    # constant.
    scores = sorted((o["best_idf_weighted_score"] for o in overlap), reverse=True)
    print()
    print(f"Best-match IDF-weighted score distribution across {n_total} LEXam items "
          f"(sorted desc, for threshold transparency):")
    print(f"    max={scores[0]:.2f}  p10={scores[int(0.1*n_total)]:.2f}  "
          f"p25={scores[int(0.25*n_total)]:.2f}  median={scores[n_total//2]:.2f}  "
          f"p75={scores[int(0.75*n_total)]:.2f}  min={scores[-1]:.2f}")

    IDF_THRESHOLD = 4.0
    n_idf = sum(1 for o in overlap if o["best_idf_weighted_score"] >= IDF_THRESHOLD)
    pct_idf = 100 * n_idf / n_total if n_total else 0

    print()
    print(f"NAIVE overlap (>=1 shared stopword-filtered keyword, UNWEIGHTED -- inflated by generic "
          f"connector-word collisions, see docstring): {n_raw_ge1}/{n_total} = {pct_raw_ge1:.1f}%")
    print(f"NAIVE overlap (>=2 shared keywords, UNWEIGHTED): {n_raw_ge2}/{n_total} = {pct_raw_ge2:.1f}%")
    print(f"IDF-WEIGHTED overlap (best-match score >= {IDF_THRESHOLD}, corrected for generic-word "
          f"collision -- the load-bearing number): {n_idf}/{n_total} = {pct_idf:.1f}%")
    print()
    print(f"Matched items at IDF-weighted score >= {IDF_THRESHOLD}, full list:")
    for o in overlap:
        if o["best_idf_weighted_score"] >= IDF_THRESHOLD:
            n_shared, sr, title, shared_words = o["top_matches"][0]
            print(f"    {o['question_id']}  subject={o['subject']!s:16s}  score={o['best_idf_weighted_score']:.2f}  "
                  f"shared={shared_words}")
            print(f"        <- SR {sr} {title[:90]}")

    print()
    print("=" * 100)
    print("LAW-0 VERDICT (pre-registered bar: >=30% topical overlap)")
    print("=" * 100)
    verdict_raw_ge1 = "CLEARS BAR" if pct_raw_ge1 >= 30 else "DOES NOT CLEAR BAR"
    verdict_idf = "CLEARS BAR" if pct_idf >= 30 else "DOES NOT CLEAR BAR"
    print(f"NAIVE >=1-keyword overlap rate {pct_raw_ge1:.1f}% vs 30% bar: {verdict_raw_ge1} "
          f"(reported for transparency, NOT the number to trust -- see caveat above)")
    print(f"IDF-WEIGHTED overlap rate {pct_idf:.1f}% vs 30% bar: {verdict_idf}  <-- LOAD-BEARING VERDICT")

    # --- write artifacts ---
    RESULTS_DIR.mkdir(exist_ok=True)

    with (RESULTS_DIR / "swiss_law_corpus_english_titles.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["sr_number", "title", "short_title", "uuid"])
        w.writeheader()
        for t in sorted(english_titles, key=lambda x: x["sr_number"]):
            w.writerow({"sr_number": t["sr_number"], "title": t["title"], "short_title": t["short_title"], "uuid": t["uuid"]})

    with (RESULTS_DIR / "swiss_law_corpus_overlap.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["question_id", "subject", "best_idf_weighted_score",
                                            "best_shared_keyword_count_raw", "n_matches_ge1_raw",
                                            "top_match_sr", "top_match_title", "top_match_shared_words"])
        w.writeheader()
        for o in overlap:
            top = o["top_matches"][0] if o["top_matches"] else (0, "", "", [])
            w.writerow({
                "question_id": o["question_id"], "subject": o["subject"],
                "best_idf_weighted_score": round(o["best_idf_weighted_score"], 3),
                "best_shared_keyword_count_raw": o["best_shared_keyword_count"],
                "n_matches_ge1_raw": o["n_matches_ge1_raw"],
                "top_match_sr": top[1], "top_match_title": top[2], "top_match_shared_words": ";".join(top[3]),
            })

    data = {
        "dataset_stats": stats,
        "metadata_cross_checks": {
            "n_rows_read": len(meta), "n_rows_datasets_server": stats["num_examples"],
            "n_english_rows_parquet": len(en_meta), "n_english_rows_datasets_server": n_en_stats,
            "n_title_blank": n_title_blank, "n_short_blank": n_short_blank, "n_abbr_blank": n_abbr_blank,
            "english_canton_distribution": dict(Counter(en_meta["canton"])),
        },
        "n_english_titles_extracted": len(english_titles),
        "n_titles_nonblank_after_extraction": n_title_extracted,
        "lexam_n_items": len(lexam_items),
        "lexam_subject_distribution": dict(subj_dist),
        "overlap_naive_ge1_count": n_raw_ge1, "overlap_naive_ge1_pct": pct_raw_ge1,
        "overlap_naive_ge2_count": n_raw_ge2, "overlap_naive_ge2_pct": pct_raw_ge2,
        "idf_threshold": IDF_THRESHOLD,
        "overlap_idf_weighted_count": n_idf, "overlap_idf_weighted_pct": pct_idf,
        "idf_score_distribution": {"max": scores[0], "p10": scores[int(0.1*n_total)], "p25": scores[int(0.25*n_total)],
                                    "median": scores[n_total//2], "p75": scores[int(0.75*n_total)], "min": scores[-1]},
        "law0_bar_pct": 30.0,
        "law0_verdict_naive_ge1": verdict_raw_ge1,
        "law0_verdict_idf_weighted": verdict_idf,
    }
    with (RESULTS_DIR / "swiss_law_corpus_check_data.json").open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)

    print()
    print("Wrote: benchmark/results/swiss_law_corpus_english_titles.csv, "
          "benchmark/results/swiss_law_corpus_overlap.csv, "
          "benchmark/results/swiss_law_corpus_check_data.json")
    print()
    print("Reproduce with: .venv/Scripts/python.exe benchmark/check_swiss_law_corpus.py")
    print("(requires network access to huggingface.co; zero paid LLM tokens spent)")


if __name__ == "__main__":
    main()
