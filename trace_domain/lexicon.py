"""REAL-native language understanding through relational engagement.

The Lexicon is the trace organizer's developing vocabulary — it builds
a co-occurrence graph as the agent reads traces, deriving word meaning
from relational context rather than imported embeddings.

Key ideas:
  - Tokenization is the "body plan" — word boundaries are given
  - Meaning is relational profile — a word IS its co-occurrence pattern
  - Salience is emergent — words that help discriminate get amplified
  - Trace similarity comes from relational neighborhood overlap

This is deliberately NOT a neural embedding. It's a REAL-native approach
to linguistic understanding: meaning through relation, not representation.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ── Tokenization: the body plan ──────────────────────────────────────

# Words that carry no discriminative signal — the "connective tissue"
# of language. Like metabolic housekeeping: necessary but not informative.
_STOP_WORDS = frozenset({
    # Determiners / pronouns
    "the", "this", "that", "these", "those", "its",
    # Conjunctions / prepositions
    "and", "but", "for", "nor", "yet", "with", "from", "into", "than",
    "then", "when", "where", "which", "who", "how", "what", "about",
    "after", "before", "between", "through", "during", "above", "below",
    "because", "since", "while", "although", "though", "until", "unless",
    # Auxiliary / modal
    "are", "was", "were", "been", "being", "have", "has", "had", "having",
    "will", "would", "could", "should", "may", "might", "can", "shall",
    "does", "did", "doing",
    # Common verbs (too generic)
    "not", "also", "just", "very", "much", "many", "more", "most",
    "some", "such", "only", "own", "same", "now", "here", "there",
    "all", "each", "every", "both", "few", "other", "any", "our", "out",
    # Markdown / technical noise
    "http", "https", "www", "com", "org", "true", "false", "none",
    "def", "self", "return", "import", "class", "elif", "else",
    "try", "except", "finally", "raise", "pass", "yield", "lambda",
    "assert", "print", "len", "str", "int", "float", "list", "dict",
    "set", "tuple", "type", "range", "enumerate", "zip", "map", "filter",
})

# Pattern: lowercase words 3+ chars, allowing underscores (Python identifiers)
_TOKEN_RE = re.compile(r"[a-z][a-z0-9_]{2,}")


def tokenize(text: str) -> List[str]:
    """Extract meaningful tokens from text.

    This is the 'body plan' — word boundaries are given, like prosodic
    cues for a developing language learner. We don't ask the agent to
    discover word boundaries; we give it that structure.
    """
    raw = _TOKEN_RE.findall(text.lower())
    return [t for t in raw if t not in _STOP_WORDS and len(t) < 40]


# ── The Lexicon ──────────────────────────────────────────────────────

@dataclass
class LexiconStats:
    """Snapshot of lexicon development state."""
    vocabulary_size: int
    traces_ingested: int
    total_tokens: int
    mean_salience: float
    top_salient: List[Tuple[str, float]]  # (word, salience) pairs


class Lexicon:
    """REAL-native word understanding through relational engagement.

    The lexicon grows as the agent reads traces. Each ingested text
    updates a co-occurrence graph from which word meaning (relational
    profiles) and trace similarity emerge.

    This is developmental: early on, the lexicon is sparse and similarity
    scores are low. As the agent reads more, relational structure builds
    and discrimination improves. The agent literally understands its
    corpus better the more it engages with it.
    """

    # Co-occurrence window: words within this distance are "related"
    WINDOW: int = 6

    # Minimum document frequency for a word to have a profile
    MIN_DOC_FREQ: int = 1

    # Cache size limit to prevent memory bloat
    MAX_PROFILE_CACHE: int = 2000

    def __init__(self) -> None:
        # Core graph: word → {neighbor: co-occurrence count}
        self._cooccur: Dict[str, Counter] = {}

        # Document frequency: how many traces contain each word
        self._doc_freq: Counter = Counter()

        # Per-trace token storage (for trace profiles)
        self._trace_tokens: Dict[int, List[str]] = {}
        # Per-trace term frequency: how central each word is to each trace
        self._trace_tf: Dict[int, Dict[str, float]] = {}

        # Tracking
        self._total_ingested: int = 0
        self._total_tokens: int = 0

        # Caches — invalidated on each ingest
        self._salience_cache: Dict[str, float] = {}
        self._profile_cache: Dict[str, Dict[str, float]] = {}
        self._trace_profile_cache: Dict[int, Dict[str, float]] = {}
        self._similarity_cache: Dict[Tuple[int, int], float] = {}

    # ── Ingestion ────────────────────────────────────────────────────

    def ingest(self, trace_id: int, text: str) -> int:
        """Process a trace's text, updating the relational graph.

        Called when the agent reads a trace. This is the act of
        *engaging with* language — not passive storage but active
        relational construction.

        Returns number of tokens processed.
        """
        tokens = tokenize(text)
        if not tokens:
            return 0

        # Don't re-ingest (but allow update if we want to later)
        if trace_id in self._trace_tokens:
            return len(self._trace_tokens[trace_id])

        self._trace_tokens[trace_id] = tokens
        self._total_ingested += 1
        self._total_tokens += len(tokens)

        # Compute term frequency for this trace
        # TF = count / total_tokens — how central is each word to THIS trace
        raw_counts: Counter = Counter(tokens)
        total_t = len(tokens)
        self._trace_tf[trace_id] = {
            w: c / total_t for w, c in raw_counts.items()
        }

        # Update document frequency
        unique = set(tokens)
        for word in unique:
            self._doc_freq[word] += 1

        # Update co-occurrence within sliding window
        for i, word in enumerate(tokens):
            if word not in self._cooccur:
                self._cooccur[word] = Counter()
            neighbors = self._cooccur[word]

            lo = max(0, i - self.WINDOW)
            hi = min(len(tokens), i + self.WINDOW + 1)
            for j in range(lo, hi):
                if i != j:
                    neighbors[tokens[j]] += 1

        # Invalidate all caches — the relational landscape has changed
        self._salience_cache.clear()
        self._profile_cache.clear()
        self._trace_profile_cache.clear()
        self._similarity_cache.clear()

        return len(tokens)

    # ── Salience: emergent informativeness ───────────────────────────

    def salience(self, word: str) -> float:
        """How diagnostically useful is this word?

        Words appearing in every trace have zero discriminative power.
        Words appearing in a few traces carry high signal. This is
        essentially IDF, but framed as the agent discovering which
        words are informative through exposure, not through a formula
        applied from outside.

        Returns 0.0–1.0.
        """
        if word in self._salience_cache:
            return self._salience_cache[word]

        if self._total_ingested == 0 or word not in self._doc_freq:
            return 0.0

        df = self._doc_freq[word]
        n = self._total_ingested

        # Log-scaled inverse document frequency, normalized to [0, 1]
        # Words in 1 trace: salience ≈ 1.0
        # Words in all traces: salience = 0.0
        raw = math.log(n / df) / math.log(max(n, 2))

        # Sharper discrimination: aggressively suppress project-wide vocabulary.
        # Words appearing in >40% of traces are "project jargon" — they tell you
        # this is a REAL trace, not WHICH kind of REAL trace.
        frac = df / n
        if frac > 0.40:
            raw *= 0.1   # near-zero — these words are noise for discrimination
        elif frac > 0.25:
            raw *= 0.4   # heavily suppressed
        elif 0.05 < frac < 0.25:
            # Sweet spot: common enough to be meaningful, rare enough to discriminate
            raw = min(1.0, raw * 1.2)

        val = max(0.0, min(1.0, raw))
        self._salience_cache[word] = val
        return val

    # ── Relational profiles: meaning as relation ─────────────────────

    def relational_profile(self, word: str) -> Dict[str, float]:
        """A word's meaning IS its relational signature.

        Returns a normalized vector over the vocabulary, where each
        entry represents how strongly this word co-occurs with that
        neighbor, weighted by the neighbor's salience.

        Two words with similar profiles are semantically related —
        not because someone labeled them so, but because they
        participate in similar relational contexts.
        """
        if word in self._profile_cache:
            return self._profile_cache[word]

        cooccur = self._cooccur.get(word)
        if not cooccur:
            return {}

        total = sum(cooccur.values())
        if total == 0:
            return {}

        # Weight each neighbor by co-occurrence frequency × neighbor salience
        profile: Dict[str, float] = {}
        for neighbor, count in cooccur.items():
            s = self.salience(neighbor)
            if s < 0.01:
                continue  # skip zero-salience words
            weight = (count / total) * s
            if weight > 0.0005:  # prune negligible
                profile[neighbor] = weight

        # L2-normalize to unit length (so cosine similarity = dot product)
        magnitude = math.sqrt(sum(v * v for v in profile.values()))
        if magnitude > 0:
            profile = {k: v / magnitude for k, v in profile.items()}

        # Cache management
        if len(self._profile_cache) < self.MAX_PROFILE_CACHE:
            self._profile_cache[word] = profile
        return profile

    # ── Trace profiles: aggregate relational signature ───────────────

    def trace_profile(self, trace_id: int) -> Dict[str, float]:
        """The relational signature of a trace.

        Aggregates the relational profiles of all salient words in the
        trace, weighted by their salience. The result is a single vector
        that represents what this trace is "about" in relational space.

        This is NOT a bag-of-words. Two traces might not share any words
        but if they use words from the same relational neighborhood,
        they'll have similar profiles.
        """
        if trace_id in self._trace_profile_cache:
            return self._trace_profile_cache[trace_id]

        tokens = self._trace_tokens.get(trace_id)
        if not tokens:
            return {}

        tf = self._trace_tf.get(trace_id, {})

        # Weighted sum of word profiles, weighted by TF × salience.
        # TF captures how central a word is to THIS trace.
        # Salience captures how diagnostic a word is across the corpus.
        # Together: words that are both locally important and globally
        # discriminating dominate the profile.
        aggregate: Counter = Counter()
        unique = set(tokens)

        for word in unique:
            s = self.salience(word)
            if s < 0.05:
                continue  # skip near-zero salience words

            # TF weighting: words mentioned 5x in this trace matter more
            # than words mentioned once in passing
            word_tf = tf.get(word, 0.0)
            weight = s * (1.0 + 10.0 * word_tf)  # TF amplification

            wp = self.relational_profile(word)
            for k, v in wp.items():
                aggregate[k] += v * weight

        # L2-normalize
        magnitude = math.sqrt(sum(v * v for v in aggregate.values()))
        if magnitude > 0:
            result = {k: v / magnitude for k, v in aggregate.items()}
        else:
            result = {}

        self._trace_profile_cache[trace_id] = result
        return result

    # ── Trace similarity: relational overlap ─────────────────────────

    def trace_similarity(self, id_a: int, id_b: int) -> float:
        """Relational similarity between two traces.

        Computed as cosine similarity of their trace profiles — which
        means it captures shared relational structure, not just
        shared keywords.

        Returns 0.0–1.0 (clamped non-negative).
        """
        key = (min(id_a, id_b), max(id_a, id_b))
        if key in self._similarity_cache:
            return self._similarity_cache[key]

        pa = self.trace_profile(id_a)
        pb = self.trace_profile(id_b)

        if not pa or not pb:
            return 0.0

        # Cosine similarity (profiles are already L2-normalized)
        shared = set(pa.keys()) & set(pb.keys())
        if not shared:
            val = 0.0
        else:
            val = max(0.0, sum(pa[k] * pb[k] for k in shared))

        self._similarity_cache[key] = val
        return val

    # ── Diagnostics ──────────────────────────────────────────────────

    def stats(self) -> LexiconStats:
        """Current development state of the lexicon."""
        if not self._doc_freq:
            return LexiconStats(
                vocabulary_size=0,
                traces_ingested=0,
                total_tokens=0,
                mean_salience=0.0,
                top_salient=[],
            )

        all_salience = [(w, self.salience(w)) for w in self._doc_freq]
        all_salience.sort(key=lambda x: -x[1])
        mean_s = sum(s for _, s in all_salience) / len(all_salience)

        return LexiconStats(
            vocabulary_size=len(self._cooccur),
            traces_ingested=self._total_ingested,
            total_tokens=self._total_tokens,
            mean_salience=round(mean_s, 4),
            top_salient=[(w, round(s, 3)) for w, s in all_salience[:20]],
        )

    def word_neighbors(self, word: str, top_n: int = 10) -> List[Tuple[str, float]]:
        """Most strongly related words (by relational profile weight).

        Useful for debugging: "what does the lexicon think 'benchmark' means?"
        """
        profile = self.relational_profile(word)
        if not profile:
            return []
        ranked = sorted(profile.items(), key=lambda x: -x[1])
        return [(w, round(v, 4)) for w, v in ranked[:top_n]]

    @property
    def vocabulary_size(self) -> int:
        return len(self._cooccur)

    @property
    def traces_ingested(self) -> int:
        return self._total_ingested

    def has_trace(self, trace_id: int) -> bool:
        return trace_id in self._trace_tokens

    # ── Persistence: vocabulary that accumulates across sessions ──────

    def save_state(self, path: str | Path) -> None:
        """Save the lexicon's learned state to disk.

        This is the agent's accumulated linguistic understanding —
        it should grow across sessions, not reset. Every run adds
        more words, richer co-occurrence patterns, and better
        discrimination ability.
        """
        state = {
            "version": 1,
            "total_ingested": self._total_ingested,
            "total_tokens": self._total_tokens,
            # Co-occurrence graph: the core relational structure
            "cooccur": {
                word: dict(neighbors)
                for word, neighbors in self._cooccur.items()
            },
            # Document frequencies
            "doc_freq": dict(self._doc_freq),
            # Per-trace data: which traces have been ingested and their tokens
            "trace_tokens": {
                str(tid): tokens
                for tid, tokens in self._trace_tokens.items()
            },
            "trace_tf": {
                str(tid): tf_dict
                for tid, tf_dict in self._trace_tf.items()
            },
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1)

    def load_state(self, path: str | Path) -> bool:
        """Restore a previously saved lexicon.

        Returns True if state was loaded, False if no saved state exists.
        After loading, caches are cleared so profiles are recomputed
        fresh from the (now richer) co-occurrence graph.
        """
        path = Path(path)
        if not path.exists():
            return False

        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)

        version = state.get("version", 0)
        if version < 1:
            return False  # incompatible format

        self._total_ingested = state.get("total_ingested", 0)
        self._total_tokens = state.get("total_tokens", 0)

        # Restore co-occurrence graph
        self._cooccur = {
            word: Counter(neighbors)
            for word, neighbors in state.get("cooccur", {}).items()
        }

        # Restore document frequencies
        self._doc_freq = Counter(state.get("doc_freq", {}))

        # Restore per-trace data (JSON keys are strings, convert back to int)
        self._trace_tokens = {
            int(tid): tokens
            for tid, tokens in state.get("trace_tokens", {}).items()
        }
        self._trace_tf = {
            int(tid): tf_dict
            for tid, tf_dict in state.get("trace_tf", {}).items()
        }

        # Clear all caches — they'll be rebuilt on demand from the
        # now-restored graph
        self._salience_cache.clear()
        self._profile_cache.clear()
        self._trace_profile_cache.clear()
        self._similarity_cache.clear()

        return True

    @property
    def state_path(self) -> str:
        """Default save path (for convenience)."""
        return "trace_domain/lexicon_state.json"
