# Swiss law corpus check (LAW-0 / F9) — zero-token kill-or-resurrect gate

Implements `docs/capability-roadmap.md` section 4 FREE-tier item **F9** ("LAW-0:
dump the 207 English `rcds/swiss_legislation` titles, overlap against LEXam English
items — Kills or resurrects the corpus arm for zero tokens") and the pre-registered
bar in section 3.7 ("LAW-0 must show ≥30% topical overlap between the 207 English
acts and LEXam English item subjects before LAW-1 is funded"). Script:
`benchmark/check_swiss_law_corpus.py`. Reproduce:

```
.venv/Scripts/python.exe benchmark/check_swiss_law_corpus.py
```

Requires live network access to `huggingface.co` (a public-dataset read via the HF
datasets-server API and column-projected parquet reads — **not** a paid LLM call;
zero tokens spent against the QuorumQA quota, the same class of operation
`benchmark/load_lexam.py` already performs against the same datasets-server). Writes
`benchmark/results/swiss_law_corpus_english_titles.csv` (all 207 English rows: SR
number, real title, real short-title, uuid), `benchmark/results/swiss_law_corpus_overlap.csv`
(per-LEXam-item match scores), and `benchmark/results/swiss_law_corpus_check_data.json`
(everything, unrounded).

## 0. Background: why this check exists

The project's LEXam law result was **−14** and the diagnosed cause was corpus
mismatch: the STEM/US-law Wikipedia RAG index this project already has has no Swiss
law content, and the logged `rag_presolve` run on LEXam showed only 2/30 retrievals
on-topic. `docs/capability-roadmap.md` §3.7 explicitly flags the earlier assumption
that `rcds/swiss_legislation`'s 207 English rows are "the Fedlex translations of the
Constitution/Civil Code/Code of Obligations/Criminal Code" as **"an unverified
inference, not a measurement."** This script turns that inference into a
measurement.

## 1. Does the corpus exist, and what does it actually contain?

**Yes — verified live against the HF datasets-server, two independent endpoints
cross-checked against each other:**

| Metric | Value |
|---|---|
| Total rows | **35,698** (verified via both `/info` and `/statistics`, and by summing all 5 parquet shards — all three numbers agree exactly) |
| Compressed / decompressed size | 191.5 MB / 2.05 GB |
| Language distribution | de 17,559 · fr 11,197 · it 6,201 · **en 207** · rm 534 |
| `is_active` | **True for all 35,698 rows** (no filtering needed on this axis) |
| English rows' canton | **100% `ch`** (federal legislation only — no cantonal English translations exist in this dataset) |

**English row count is exactly 207**, matching the roadmap's cited figure — now
independently re-derived from a live probe rather than carried forward from an
earlier, undated claim.

**A real, load-bearing data-quality finding the roadmap's inference didn't catch:**
the dataset's own `title`/`short`/`abbreviation` metadata columns are **100% blank
for all 207 English rows** (verified: `n_title_blank = 207/207`). Anyone reading only
the metadata columns — the cheap, obvious way to "dump the 207 titles" — would see
207 empty strings and could wrongly conclude the corpus is unusable or the row set is
metadata-only stubs. The real titles exist, but only inside each row's
`html_content` field (the full official Fedlex English HTML translation, e.g. SR 210
alone is 2.17 MB of HTML) — extracted here via the standard Fedlex `<h1
class="erlasstitel">`/`<h2 class="erlasskurztitel">` markup. **206/207 titles
extracted successfully** (1 row's HTML did not match the expected markup pattern —
logged, not silently dropped; see the CSV for which one).

**Sample of what the 207 English acts actually are** (full list in
`swiss_law_corpus_english_titles.csv`, sorted by SR number):

| SR | Title |
|---|---|
| 101 | Federal Constitution of the Swiss Confederation |
| 210 | Swiss Civil Code |
| 220 | Federal Act on the Amendment of the Swiss Civil Code (Part Five: The Code of Obligations) |
| 272 | Swiss Civil Procedure Code (Civil Procedure Code, CPC) |
| 311.0 | Swiss Criminal Code |
| 312.0 | Swiss Criminal Procedure Code (Criminal Procedure Code, CrimPC) |
| 0.810.3 | Council of Europe Convention against Trafficking in Human Organs |
| 141.0 | Federal Act on Swiss Citizenship (Swiss Citizenship Act, SCA) |
| 151.1 | Federal Act on Gender Equality (Gender Equality Act, GEA) |
| 672.3 | Federal Act on the Recognition of Private Agreements for the Avoidance of Double Taxation |
| 784.40 | Federal Act on Radio and Television (RTVA) |
| 958.2 | Ordinance on the Recognition of Foreign Trading Venues for the Trading of Equity Securities of Companies |

The roadmap's inference is **half right**: the "big four" codes (Constitution, Civil
Code, Code of Obligations, Criminal Code) genuinely are present. But they are 4 of
207, not the corpus's center of gravity — the other 203 are a long, diverse tail of
niche federal statutes and ordinances (citizenship, archiving, cyber-risk
administration, national parks, patent courts, radio/TV, health/therapeutics,
banking, hospitality licensing, and more) that happen to have official English
Fedlex translations, almost certainly because they are business/international-facing
rather than because they were selected for any legal-education relevance.

## 2. Overlap against LEXam English items

**The LEXam pool:** 90 distinct English `question_id`s, pooled and deduped across
the four LEXam result files logged in this repo (`lexam_pilot_seed42.jsonl`,
`lever_control_lexam_seed42.jsonl`, `lever_thinking_gate_lexam_seed42.jsonl`,
`lever_rag_recursive_lexam_seed42.jsonl`). **Subject distribution: Interdisciplinary
79, Private 9, Public 2.** This alone is a warning sign for a legislative-text
corpus: "Interdisciplinary" dominates 88% of the pool, and reading the actual
question text (below) shows this bucket is legal history, legal theory/sociology,
and comparative (US/Roman/international) law — content a statute-text corpus
structurally cannot serve, however good the retrieval.

### 2a. Automated keyword/title overlap (first pass, reported for transparency — see caveat)

A stopword-filtered bag-of-words match (LEXam question text vs the 207 extracted
titles) gives:

- ≥1 shared keyword: **89/90 = 98.9%**
- ≥2 shared keywords: **35/90 = 38.9%**

Both numbers nominally clear the 30% bar. **They should not be trusted as-is.** With
207 candidate titles spanning almost every domain of federal regulation, a bag of
common-ish English nouns produces heavy coincidental collision: e.g. 8 of the 90
items matched SR 0.810.3 ("Council of Europe Convention against Trafficking in Human
Organs") purely via the words *against/human/convention/europe* — several of those
items are legal-philosophy questions about human **dignity**, unrelated to organ
trafficking. Re-weighting by inverse corpus-document-frequency (a word private to 1
of 207 titles scores far higher than one shared by 50) did not fix this on its own —
at 207 candidates, even a single moderately uncommon English word (e.g. "canton",
"regime", "capital", "their") coincidentally matches *some* title, so an
IDF-weighted single-word threshold still returns 98.9%. **A purely automated metric
cannot be trusted to answer this question at this corpus size** — it was not treated
as the load-bearing number.

### 2b. Manual audit of the strongest automated matches (the load-bearing analysis)

Every one of the 35 items that scored ≥2 shared keywords was hand-read against its
matched corpus title and classified:

- **GENUINE** (the matched act's actual subject plausibly serves the actual
  question): the cross-border/double-taxation scenario cluster (Eric/Anne
  hypotheticals — 6 distinct question_ids, all correctly pointing at SR 672.3
  "Avoidance of Double Taxation"), the Swiss radio/television constitutional
  question (→ SR 784.40), the Swiss criminal-procedure question (→ SR 312.0), the
  Swiss/US civil-procedure comparison question (→ SR 272), and one mandate/agency
  contract-law scenario (→ the Code of Obligations family). **10/90 items (11.1%).**
- **BORDERLINE** (right general legal domain, but the *specific* matched act is
  clearly the wrong instrument — e.g. a "recognition of foreign judgments" question
  matched to an ordinance about recognizing *foreign trading venues*, not
  judgments; a Civil-Code property-law question matched to the *Cultural* Property
  Transfer Act instead of the Code's own property provisions; a Lugano-Convention
  civil-procedure question matched to the unrelated Rotterdam Convention on
  chemicals). Counting these generously as "could plausibly be served by *something*
  in the corpus, even if not the exact matched act": **+9 more items, 19/90 (21.1%)
  cumulative.**
- **COINCIDENTAL** (generic connector-word collision or genuinely unrelated
  domain — legal history, Roman law, comparative Chinese business law, legal
  sociology/Luhmann theory, etc. matched via words like "against", "under",
  "their", "regime", "canton", "capital", "domain", "time"): **the remaining
  71/90 (78.9%), including every single-keyword-only match.**

**Corrected overlap estimate: 11–21% of the 90 LEXam English items, depending on how
generously "plausible" is read — in every reading, below the pre-registered 30%
bar.** The gap between this and the naive automated 98.9%/38.9% figures is itself
the finding: this is precisely the kind of "unverified inference" the roadmap
flagged, now replaced with an audited measurement, not a bigger unverified number.

## 3. Verdict

**LAW-0 DOES NOT CLEAR THE ≥30% BAR.** Under manual audit of every candidate match,
genuine or plausible topical overlap between the 90 logged LEXam English items and
the 207-act English Swiss-legislation corpus sits at roughly 11–21%, well short of
the 30% threshold `docs/capability-roadmap.md` §3.7 requires before LAW-1 (the
flagship-tier gap probe) is funded.

This is **not** because the corpus is fake, badly labeled, or unobtainable — it
demonstrably exists, is free, loads cleanly, and its English subset does contain the
Constitution/Civil Code/Code of Obligations/Criminal Code exactly as inferred. It is
because **LEXam's actually-logged English item pool is not the kind of content a
statute-text corpus can serve**: 88% of it is "Interdisciplinary" (legal
history/theory/comparative law — coniuratio, Roman law, Luhmann's systems theory,
US antitrust doctrine, the founding of the Institute of International Law), which no
amount of correctly-retrieved Swiss federal statute text answers, because the
answers to those questions are not *in* any statute. The minority of items that
genuinely are doctrinal (tax, procedure, media law, contract/agency) do have a
plausible serving act in the corpus — but that minority is roughly 1-in-5 to
1-in-9 items, not 3-in-10.

## 4. Decision consequences

- **Per `docs/capability-roadmap.md` §3.7's own pre-registered rule ("LAW-0 overlap
  thin → the English arm is dead before the index exists"): the axis is closed.**
  `swiss_law_corpus` remains **UNFUNDED**, LAW-1's flagship-tier gap probe should
  **not** be funded on this evidence, and no further engineering time should go
  into building a Swiss-law RAG index for the currently-logged LEXam item pool.
  This corroborates, from a different angle (corpus-content vs question-content
  mismatch, not corpus-existence), the roadmap's independent decision to drop
  `lexam_flagship_panel` and the `swiss_law_corpus` paid run.
- **This is a genuinely different failure mode than the original −14 diagnosis
  assumed**, and worth stating precisely for anyone revisiting this axis later: the
  earlier finding ("our STEM/US-law Wikipedia index has no Swiss law") is true but
  incomplete. Even a domain-correct, freely-obtainable, real Swiss-law corpus
  (which this script confirms exists) would not close most of the gap, because the
  gap is dominated by question *type* (history/theory/comparative), not just
  jurisdiction mismatch. A future attempt at this axis would need either (a) a
  fundamentally different LEXam item mix skewed toward the doctrinal `mcq_4`
  subject areas (`Private`/`Public`, currently only 11/90 = 12% of the logged
  pool) rather than `Interdisciplinary`, or (b) a corpus of legal
  history/theory/comparative-law reference material, which `rcds/swiss_legislation`
  structurally cannot be (it is enacted statute text only).
- **The German-language axis remains separately, and more severely, closed** — the
  roadmap's own §3.7 already notes LEXam's largest headroom is German-language
  items (1,036 de vs 619 en in `mcq_4`), which 207 English documents cannot reach
  regardless of this check's outcome; that conclusion is unchanged and not
  re-litigated here.
- **Process note for future zero-token gates in this family:** an automated
  keyword/title-overlap metric alone is not reliable at this corpus size (207
  candidates against ordinary English vocabulary) — any future LAW-0-style check
  should budget for a manual read-through of the top automated matches before
  reporting a verdict, exactly as done here. Reporting the naive 98.9%/38.9%
  numbers uncorrected would have wrongly resurrected a dead axis.
