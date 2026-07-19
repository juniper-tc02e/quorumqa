"""Loads the benchmark question set.

Primary source: GPQA-Diamond (idavidrein/gpqa on HuggingFace) -- public,
PhD-level, "Google-proof" science questions with a static answer key. This
dataset is gated on HuggingFace (accept the terms on the dataset page and
pass HF_TOKEN) to deter search-engine contamination.

Fallback 1: the same GPQA-Diamond data, HuggingFace-independent -- the
authors also publish it as a password-protected zip directly in their
GitHub repo (idavidrein/gpqa). Used whenever the HF path fails for ANY
reason (gating, auth, or huggingface.co itself being down), not just
gating -- this is the real dataset, not a substitute, so it's preferred
over the MMLU-Pro fallback below.

Fallback 2: TIGER-Lab/MMLU-Pro (ungated, also on HuggingFace), trimmed to 4
choices per question so it fits the same A-D schema. Only reached if BOTH
the HF path and the GitHub zip fail -- log a clear warning so nobody
mistakes it for the primary benchmark when reading results.
"""

import csv
import io
import logging
import os
import random
import string
import urllib.request
import zipfile
from pathlib import Path

from datasets import load_dataset

from quorumqa.config import HF_TOKEN
from quorumqa.schemas import GPQAItem

log = logging.getLogger(__name__)

_LETTERS = string.ascii_uppercase[:4]

_GITHUB_ZIP_URL = "https://raw.githubusercontent.com/idavidrein/gpqa/main/dataset.zip"
_GITHUB_ZIP_PASSWORD = b"deserted-untie-orchid"  # published in full in the repo's own README
_CACHE_DIR = Path(__file__).resolve().parent / "data" / "cache"


def _shuffle_choices(rng: random.Random, correct: str, incorrect: list[str]) -> tuple[list[str], str]:
    choices = [correct, *incorrect]
    order = list(range(len(choices)))
    rng.shuffle(order)
    shuffled = [choices[i] for i in order]
    correct_index = order.index(0)
    return shuffled, _LETTERS[correct_index]


def _load_gpqa_diamond(n: int, seed: int) -> list[GPQAItem]:
    ds = load_dataset("Idavidrein/gpqa", "gpqa_diamond", split="train", token=HF_TOKEN)
    rng = random.Random(seed)
    indices = list(range(len(ds)))
    rng.shuffle(indices)

    items: list[GPQAItem] = []
    for i in indices[:n]:
        row = ds[i]
        question = row.get("Question") or row["question"]
        correct = row.get("Correct Answer") or row["correct_answer"]
        incorrect = [
            row.get(f"Incorrect Answer {k}") or row.get(f"incorrect_answer_{k}")
            for k in (1, 2, 3)
        ]
        incorrect = [x for x in incorrect if x]
        if len(incorrect) != 3:
            continue
        choices, correct_letter = _shuffle_choices(rng, correct, incorrect)
        items.append(
            GPQAItem(
                question_id=str(row.get("Record ID", i)),
                question=question,
                choices=choices,
                correct_letter=correct_letter,
                subject=row.get("Subdomain") or row.get("High-level domain"),
            )
        )
    return items


def _load_gpqa_diamond_from_github_zip(n: int, seed: int) -> list[GPQAItem]:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = _CACHE_DIR / "gpqa_dataset.zip"
    if not zip_path.exists():
        log.info("Downloading GPQA dataset zip from GitHub (HuggingFace-independent fallback)...")
        urllib.request.urlretrieve(_GITHUB_ZIP_URL, zip_path)

    with zipfile.ZipFile(zip_path) as zf, zf.open("dataset/gpqa_diamond.csv", pwd=_GITHUB_ZIP_PASSWORD) as raw:
        rows = list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8")))

    rng = random.Random(seed)
    indices = list(range(len(rows)))
    rng.shuffle(indices)

    items: list[GPQAItem] = []
    for i in indices[:n]:
        row = rows[i]
        question = row["Question"].strip()
        correct = row["Correct Answer"].strip()
        incorrect = [row[f"Incorrect Answer {k}"].strip() for k in (1, 2, 3)]
        if not question or not correct or not all(incorrect):
            continue
        choices, correct_letter = _shuffle_choices(rng, correct, incorrect)
        items.append(
            GPQAItem(
                question_id=row.get("Record ID") or str(i),
                question=question,
                choices=choices,
                correct_letter=correct_letter,
                subject=row.get("Subdomain") or row.get("High-level domain"),
            )
        )
    return items


def _load_mmlu_pro_fallback(n: int, seed: int) -> list[GPQAItem]:
    log.warning("GPQA-Diamond unavailable -- falling back to MMLU-Pro subset. "
                "Results are NOT the primary benchmark; re-run on GPQA before publishing numbers.")
    ds = load_dataset("TIGER-Lab/MMLU-Pro", split="test")
    rng = random.Random(seed)
    indices = list(range(len(ds)))
    rng.shuffle(indices)

    items: list[GPQAItem] = []
    for i in indices:
        if len(items) >= n:
            break
        row = ds[i]
        options: list[str] = row["options"]
        answer_index: int = row["answer_index"]
        if len(options) < 4:
            continue
        correct = options[answer_index]
        incorrect_pool = [o for j, o in enumerate(options) if j != answer_index]
        incorrect = rng.sample(incorrect_pool, 3)
        choices, correct_letter = _shuffle_choices(rng, correct, incorrect)
        items.append(
            GPQAItem(
                question_id=str(row.get("question_id", i)),
                question=row["question"],
                choices=choices,
                correct_letter=correct_letter,
                subject=row.get("category"),
            )
        )
    return items


def load_benchmark_set(n: int = 90, seed: int = 42, skip_huggingface: bool = False) -> list[GPQAItem]:
    """Set skip_huggingface=True (or env var QUORUMQA_SKIP_HF=1) to go
    straight to the GitHub zip fallback -- saves ~20s of retry-and-fail per
    call while huggingface.co is down, once you already know it's down."""
    skip_huggingface = skip_huggingface or os.environ.get("QUORUMQA_SKIP_HF") == "1"
    if not skip_huggingface:
        try:
            items = _load_gpqa_diamond(n, seed)
            if items:
                return items
            log.warning("GPQA-Diamond (HuggingFace) returned zero usable rows -- trying the GitHub zip fallback.")
        except Exception as exc:  # dataset gating, auth, or huggingface.co being unreachable
            log.warning("Could not load GPQA-Diamond from HuggingFace (%s) -- trying the GitHub zip fallback.", exc)

    try:
        items = _load_gpqa_diamond_from_github_zip(n, seed)
        if items:
            log.info("Loaded GPQA-Diamond via the GitHub zip fallback (HuggingFace-independent).")
            return items
        log.warning("GitHub zip fallback returned zero usable rows -- falling back to MMLU-Pro.")
    except Exception as exc:
        log.warning("GitHub zip fallback also failed (%s) -- falling back to MMLU-Pro.", exc)

    return _load_mmlu_pro_fallback(n, seed)
