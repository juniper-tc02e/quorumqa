"""STEM-subset selection rule for the G0 Wikipedia corpus.

Full English Wikipedia (HF `wikimedia/wikipedia`, config `20231101.en`,
the 2023-11-01 dump snapshot) is ~6.4M articles / ~20GB of text -- far more
than G0 needs or should index. This module implements the subset rule
used by benchmark/build_rag_index.py: keep an article iff its TITLE or
LEAD PARAGRAPH contains a term from a broad STEM keyword allowlist
(physics, chemistry, biology/medicine, engineering, mathematics). This is
a precision-lenient / recall-generous filter by design -- G0's retrieval
target is SuperGPQA-hard's unanimous-wrong gap (see
docs/recursive-rag-plan.md section 1), which spans many STEM subfields, so
false positives (a borderline-STEM article let through) cost only index
size, while false negatives (a genuinely relevant article dropped) cost
retrieval quality. Target subset size: ~200k-400k articles.

PROVENANCE (firewall section 4 -- every corpus snapshot documents its
source and selection rule): dataset = HF `wikimedia/wikipedia`, config
`20231101.en`, split=train, CC-BY-SA-4.0 / GFDL (per-article, standard
Wikipedia license). Nothing benchmark-derived is in this keyword list or
selection rule -- it is a topical filter over a general-purpose
encyclopedia dump, independent of any benchmark question set.
"""

from __future__ import annotations

import re

# Broad but not exhaustive -- deliberately biased toward recall. Grouped by
# field for readability; matching is case-insensitive whole-word/phrase.
_STEM_KEYWORDS: list[str] = [
    # Physics
    "physics", "quantum", "mechanics", "thermodynamic", "electromagnet",
    "relativity", "particle physics", "astrophysics", "nuclear physics",
    "optics", "photon", "electron", "proton", "neutron", "quark",
    "wave function", "field theory", "condensed matter", "plasma physics",
    "cosmology", "astronomy", "astronomical", "gravitational", "spectroscopy",
    "semiconductor", "superconduct", "magnetism", "kinetics", "dynamics",
    "energy", "entropy", "velocity", "acceleration", "momentum",
    # Chemistry
    "chemistry", "chemical", "molecule", "molecular", "compound",
    "organic chemistry", "inorganic chemistry", "biochemistry",
    "polymer", "catalyst", "reaction", "solvent", "acid", "base",
    "isotope", "periodic table", "element", "enzyme", "protein structure",
    "crystallography", "spectrometry", "titration", "electrochemistry",
    # Biology & medicine
    "biology", "biological", "organism", "cell biology", "genetics",
    "genome", "gene", "dna", "rna", "protein", "evolution", "species",
    "taxonomy", "ecology", "ecosystem", "microbiology", "virology",
    "bacteria", "virus", "pathogen", "anatomy", "physiology",
    "neuroscience", "neuron", "immunology", "immune system",
    "medicine", "medical", "disease", "syndrome", "diagnosis", "therapy",
    "treatment", "clinical", "pharmacology", "drug", "vaccine", "surgery",
    "cancer", "tumor", "infection", "epidemiology", "pathology",
    "endocrine", "cardiovascular", "respiratory system", "metabolism",
    "biotechnology", "molecular biology", "cell membrane", "chromosome",
    "mutation", "biodiversity", "botany", "zoology", "physiological",
    # Engineering
    "engineering", "engineer", "mechanical engineering",
    "electrical engineering", "civil engineering", "chemical engineering",
    "aerospace", "robotics", "control system", "circuit", "semiconductor device",
    "structural engineering", "materials science", "nanotechnology",
    "thermodynamics", "fluid dynamics", "signal processing", "algorithm",
    "computer science", "software engineering", "programming language",
    "artificial intelligence", "machine learning", "neural network",
    "database", "computer architecture", "operating system", "cryptography",
    "telecommunications", "power system", "manufacturing process",
    # Mathematics
    "mathematics", "mathematical", "theorem", "algebra", "calculus",
    "geometry", "topology", "combinatorics", "number theory",
    "probability", "statistics", "differential equation", "linear algebra",
    "graph theory", "set theory", "logic", "proof", "matrix",
    "vector space", "polynomial", "integral", "derivative", "function (mathematics)",
    "equation", "eigenvalue", "optimization problem",
    # Profession/role nouns -- catches biography-style leads ("... is a
    # theoretical physicist ...") that the noun-form keywords above miss
    # because e.g. "physicist" doesn't contain the substring "physics".
    "physicist", "chemist", "biologist", "ecologist", "zoologist",
    "botanist", "geologist", "geophysicist", "astronomer", "cosmologist",
    "mathematician", "statistician", "physician", "surgeon", "virologist",
    "immunologist", "epidemiologist", "microbiologist", "neuroscientist",
    "biochemist", "neurologist", "cardiologist", "oncologist",
    "radiologist", "geneticist", "pharmacologist", "toxicologist",
    "meteorologist", "paleontologist", "anatomist",
]

# Compile once: a single alternation regex with word-boundary anchoring on
# each term (works for multi-word phrases too since \b anchors the phrase
# ends, and internal spaces match literally).
_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in _STEM_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

LEAD_CHARS = 1000
"""How many characters of the article body count as the 'lead' for
matching, when the caller doesn't pre-extract a lead paragraph."""


def is_stem_article(title: str, lead_or_body: str) -> bool:
    """True if `title` or the leading `LEAD_CHARS` of `lead_or_body`
    contains a STEM keyword/phrase (case-insensitive, word/phrase-bounded).

    Callers should pass the article's lead paragraph if they have it
    separately extracted; passing the full body is fine too since only the
    first LEAD_CHARS characters are checked (title-match already covers
    most on-topic articles; the lead-text check catches ones with a
    generic title but an on-topic first paragraph, e.g. a person's
    biography that opens "... is a theoretical physicist known for...").
    """
    if title and _PATTERN.search(title):
        return True
    lead = lead_or_body[:LEAD_CHARS] if lead_or_body else ""
    return bool(_PATTERN.search(lead))


def stem_keywords() -> tuple[str, ...]:
    """Read-only view of the keyword list, e.g. for logging/reporting."""
    return tuple(_STEM_KEYWORDS)
