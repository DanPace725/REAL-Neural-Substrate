"""Trace-organizer environment: wraps the trace collection as a REAL-legible world.

The environment loads the trace index, tracks organizational state (groups,
assignments, links), and exposes observation/action surfaces that the adapters
bind to the RealCoreEngine.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from .lexicon import Lexicon

if TYPE_CHECKING:
    from .surveyor import SurveyResults, ClusterSuggestion


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TraceEntry:
    """Loaded metadata for a single trace file."""

    trace_id: int
    path: str
    filename: str
    title: str
    timestamp: str
    date: str
    keywords: List[str]
    referenced_files: List[str]
    content_keywords: List[str] = field(default_factory=list)
    has_been_read: bool = False


@dataclass
class TraceGroup:
    """An organizational category created by the system."""

    name: str
    seed_keywords: List[str] = field(default_factory=list)
    member_ids: List[int] = field(default_factory=list)
    created_at_cycle: int = 0


@dataclass
class TraceLink:
    """A declared relationship between two traces."""

    id_a: int
    id_b: int
    reason: str = ""
    similarity: float = 0.0


@dataclass
class OrganizationalState:
    """Complete organizational state — what the system has built so far."""

    groups: Dict[str, TraceGroup] = field(default_factory=dict)
    assignments: Dict[int, str] = field(default_factory=dict)  # trace_id → group_name
    links: List[TraceLink] = field(default_factory=list)
    assignment_reasons: Dict[int, str] = field(default_factory=dict)
    revision_count: int = 0
    # Filesystem organization: which traces have been physically copied
    organized_traces: Set[int] = field(default_factory=set)  # trace_ids with files in folders
    organized_folders: Set[str] = field(default_factory=set)  # group names with folders created


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

class TraceEnvironment:
    """Manages the trace collection and organizational state.

    This is the 'world' the REAL agent inhabits.  It provides:
      - observation snapshots (numeric features about the current state)
      - action execution (read, tag, group, link, etc.)
      - similarity computations (Jaccard on keyword sets)
    """

    def __init__(
        self,
        repo_root: str | Path,
        index_path: str | Path | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.index_path = Path(index_path) if index_path else self.repo_root / "docs" / "traces" / "index.json"
        self.traces: Dict[int, TraceEntry] = {}
        self.org = OrganizationalState()
        self._focus_id: Optional[int] = None
        self._unread_queue: List[int] = []
        self._all_keywords: Set[str] = set()
        self._keyword_to_ids: Dict[str, Set[int]] = {}
        # Survey results channel — populated by surveyor sub-agent
        self._survey_results: Optional[Any] = None  # SurveyResults when available
        self._survey_clusters_absorbed: int = 0
        self._survey_similarity_boost: Dict[Tuple[int, int], float] = {}
        # Refiner results channel — populated by refiner sub-agent
        self._refiner_results: Optional[Any] = None  # RefinerResults when available
        # Lexicon: REAL-native language understanding, grows as agent reads
        self.lexicon = Lexicon()
        self._load_index()

    # ------------------------------------------------------------------
    # Index loading
    # ------------------------------------------------------------------

    def _load_index(self) -> None:
        with open(self.index_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        for idx, entry in enumerate(data.get("entries", [])):
            keywords = [kw.lower().strip() for kw in entry.get("keywords", [])]
            te = TraceEntry(
                trace_id=idx,
                path=entry.get("path", ""),
                filename=entry.get("filename", ""),
                title=entry.get("title", ""),
                timestamp=entry.get("timestamp", ""),
                date=entry.get("date", ""),
                keywords=keywords,
                referenced_files=entry.get("referenced_files", []),
            )
            self.traces[idx] = te
            self._all_keywords.update(keywords)
            for kw in keywords:
                self._keyword_to_ids.setdefault(kw, set()).add(idx)

        self._unread_queue = list(range(len(self.traces)))

    @property
    def trace_count(self) -> int:
        return len(self.traces)

    # ------------------------------------------------------------------
    # Deep read — extract richer features from actual file content
    # ------------------------------------------------------------------

    def read_trace_content(self, trace_id: int) -> Dict[str, Any]:
        """Read a trace file and extract content-level features.

        Returns timing information so the engine can measure metabolic cost.
        """
        te = self.traces[trace_id]
        t0 = time.perf_counter()

        full_path = self.repo_root / te.path
        text = ""
        if full_path.exists():
            text = full_path.read_text(encoding="utf-8", errors="replace")

        # Simple content keyword extraction: split on non-alpha, lower, filter short
        words = re.findall(r"[a-z_][a-z0-9_]{2,}", text.lower())
        # Frequency-weighted: keep words that appear 2+ times
        freq: Dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        content_keywords = [w for w, c in freq.items() if c >= 2 and w not in _STOP_WORDS]
        te.content_keywords = content_keywords[:50]  # cap at 50 most relevant
        te.has_been_read = True

        # Feed the lexicon — this is the agent engaging with language
        self.lexicon.ingest(trace_id, text)

        # Update keyword index with content keywords
        for kw in te.content_keywords:
            self._all_keywords.add(kw)
            self._keyword_to_ids.setdefault(kw, set()).add(trace_id)

        elapsed = time.perf_counter() - t0
        return {
            "trace_id": trace_id,
            "content_keyword_count": len(te.content_keywords),
            "text_length": len(text),
            "elapsed_secs": elapsed,
        }

    # ------------------------------------------------------------------
    # Similarity
    # ------------------------------------------------------------------

    def keyword_set(self, trace_id: int) -> Set[str]:
        """Combined keyword set (index keywords + content keywords if read)."""
        te = self.traces[trace_id]
        return set(te.keywords) | set(te.content_keywords)

    def file_ref_set(self, trace_id: int) -> Set[str]:
        return set(self.traces[trace_id].referenced_files)

    def jaccard(self, set_a: Set[str], set_b: Set[str]) -> float:
        if not set_a and not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def trace_similarity(self, id_a: int, id_b: int) -> float:
        """Combined similarity: surface features + relational understanding.

        The blend shifts as the lexicon develops:
          - Early (few traces ingested): mostly keyword + file-ref Jaccard
          - Later (rich lexicon): relational similarity dominates

        This means the agent's ability to discriminate improves as it
        reads more — understanding develops through engagement.
        """
        kw_sim = self.jaccard(self.keyword_set(id_a), self.keyword_set(id_b))
        file_sim = self.jaccard(self.file_ref_set(id_a), self.file_ref_set(id_b))
        surface = 0.65 * kw_sim + 0.35 * file_sim

        # Relational similarity from lexicon (only if both traces ingested)
        lex = self.lexicon
        if lex.has_trace(id_a) and lex.has_trace(id_b):
            relational = lex.trace_similarity(id_a, id_b)
            # Blend weight: lexicon influence grows with development
            # At 5 traces: ~25% relational. At 30+: ~70% relational.
            maturity = min(1.0, lex.traces_ingested / 40.0)
            lex_weight = 0.15 + 0.55 * maturity  # 0.15 → 0.70
            return (1.0 - lex_weight) * surface + lex_weight * relational

        return surface

    def temporal_proximity(self, id_a: int, id_b: int) -> float:
        """Normalized temporal closeness (same day = 1.0, 14+ days apart = 0.0)."""
        ta = self.traces[id_a].date
        tb = self.traces[id_b].date
        if not ta or not tb:
            return 0.0
        try:
            from datetime import datetime
            da = datetime.strptime(ta, "%Y-%m-%d")
            db = datetime.strptime(tb, "%Y-%m-%d")
            days_apart = abs((da - db).days)
            return max(0.0, 1.0 - days_apart / 14.0)
        except (ValueError, TypeError):
            return 0.0

    # ------------------------------------------------------------------
    # Group-level metrics
    # ------------------------------------------------------------------

    def intra_group_similarity(self, group_name: str) -> float:
        """Mean pairwise keyword similarity within a group."""
        group = self.org.groups.get(group_name)
        if not group or len(group.member_ids) < 2:
            return 0.0
        members = group.member_ids
        total = 0.0
        count = 0
        for i, id_a in enumerate(members):
            for id_b in members[i + 1:]:
                total += self.trace_similarity(id_a, id_b)
                count += 1
        return total / count if count > 0 else 0.0

    def mean_intra_group_similarity(self) -> float:
        """Mean of all groups' internal similarities."""
        if not self.org.groups:
            return 0.0
        sims = [self.intra_group_similarity(name) for name in self.org.groups]
        return sum(sims) / len(sims)

    def inter_group_distinction(self) -> float:
        """1 - mean pairwise centroid similarity between groups. Higher = more distinct."""
        groups = list(self.org.groups.values())
        if len(groups) < 2:
            return 0.5  # neutral when only one group
        # Compute group keyword centroids (union of member keywords)
        centroids: Dict[str, Set[str]] = {}
        for g in groups:
            kw_union: Set[str] = set()
            for tid in g.member_ids:
                kw_union |= self.keyword_set(tid)
            centroids[g.name] = kw_union

        total = 0.0
        count = 0
        names = list(centroids.keys())
        for i, na in enumerate(names):
            for nb in names[i + 1:]:
                total += self.jaccard(centroids[na], centroids[nb])
                count += 1
        mean_overlap = total / count if count > 0 else 0.0
        return max(0.0, min(1.0, 1.0 - mean_overlap))

    # ------------------------------------------------------------------
    # Organizational actions
    # ------------------------------------------------------------------

    def next_unread(self) -> Optional[int]:
        """Return next trace id that hasn't been deeply read, or None."""
        while self._unread_queue:
            tid = self._unread_queue[0]
            if not self.traces[tid].has_been_read:
                return tid
            self._unread_queue.pop(0)
        return None

    def pop_unread(self) -> Optional[int]:
        """Pop and return next unread trace, setting it as focus."""
        while self._unread_queue:
            tid = self._unread_queue.pop(0)
            if not self.traces[tid].has_been_read:
                self._focus_id = tid
                return tid
        return None

    # ------------------------------------------------------------------
    # Foraging: exploratory reading driven by relational curiosity
    # ------------------------------------------------------------------

    def forage_neighbor(self) -> Optional[int]:
        """Read something similar to the current focus — follow a thread.

        Like noticing a related document on the shelf while reading one.
        Picks the unread trace most similar (by surface keywords) to the
        current focus. This deepens understanding of the current topic.
        """
        if self._focus_id is None:
            return self.pop_unread()

        focus_kw = self.keyword_set(self._focus_id)
        if not focus_kw:
            return self.pop_unread()

        best_id = None
        best_sim = -1.0
        for tid, te in self.traces.items():
            if te.has_been_read:
                continue
            # Use keyword overlap (surface) since we haven't read it yet
            sim = self.jaccard(focus_kw, set(te.keywords))
            if sim > best_sim:
                best_sim = sim
                best_id = tid

        if best_id is not None:
            self._focus_id = best_id
            # Remove from unread queue if present
            if best_id in self._unread_queue:
                self._unread_queue.remove(best_id)
            return best_id
        return None

    def forage_gap(self) -> Optional[int]:
        """Read something from an under-understood group — fill knowledge gaps.

        The system has assigned traces to groups but might not have actually
        read them. This is the difference between 'filed' and 'understood.'
        Picks a trace that's assigned to a group but hasn't been ingested
        by the lexicon, prioritizing larger groups (bigger payoff).
        """
        # Find assigned-but-unread traces, prefer traces in larger groups
        candidates = []
        for gname, group in self.org.groups.items():
            for tid in group.member_ids:
                if not self.traces[tid].has_been_read:
                    candidates.append((tid, len(group.member_ids), gname))

        if not candidates:
            return self.pop_unread()  # fallback

        # Sort by group size (descending) — bigger groups benefit more
        candidates.sort(key=lambda x: -x[1])
        tid = candidates[0][0]
        self._focus_id = tid
        if tid in self._unread_queue:
            self._unread_queue.remove(tid)
        return tid

    def forage_surprise(self) -> Optional[int]:
        """Read something maximally different from what we've seen — seek novelty.

        Like deliberately picking up a book from an unfamiliar section.
        Picks the unread trace with the LEAST keyword overlap with all
        previously read traces. This broadens the lexicon's vocabulary.
        """
        read_kw_union: Set[str] = set()
        for tid, te in self.traces.items():
            if te.has_been_read:
                read_kw_union.update(te.keywords)
                read_kw_union.update(te.content_keywords)

        if not read_kw_union:
            return self.pop_unread()

        best_id = None
        best_novelty = -1.0
        for tid, te in self.traces.items():
            if te.has_been_read:
                continue
            # Novelty = fraction of this trace's keywords we haven't seen
            te_kw = set(te.keywords)
            if not te_kw:
                continue
            novel_frac = 1.0 - len(te_kw & read_kw_union) / len(te_kw)
            if novel_frac > best_novelty:
                best_novelty = novel_frac
                best_id = tid

        if best_id is not None:
            self._focus_id = best_id
            if best_id in self._unread_queue:
                self._unread_queue.remove(best_id)
            return best_id
        return None

    @property
    def focus_trace(self) -> Optional[TraceEntry]:
        if self._focus_id is not None and self._focus_id in self.traces:
            return self.traces[self._focus_id]
        return None

    def create_group(self, name: str, seed_keywords: List[str] | None = None, cycle: int = 0) -> TraceGroup:
        if name in self.org.groups:
            return self.org.groups[name]
        group = TraceGroup(name=name, seed_keywords=seed_keywords or [], created_at_cycle=cycle)
        self.org.groups[name] = group
        return group

    def assign_to_group(self, trace_id: int, group_name: str, reason: str = "") -> bool:
        if group_name not in self.org.groups:
            return False
        old_group = self.org.assignments.get(trace_id)
        if old_group and old_group != group_name:
            # Revision — remove from old group
            old = self.org.groups[old_group]
            if trace_id in old.member_ids:
                old.member_ids.remove(trace_id)
            self.org.revision_count += 1

        self.org.assignments[trace_id] = group_name
        self.org.assignment_reasons[trace_id] = reason
        group = self.org.groups[group_name]
        if trace_id not in group.member_ids:
            group.member_ids.append(trace_id)
        return True

    def link_traces(self, id_a: int, id_b: int, reason: str = "") -> TraceLink:
        sim = self.trace_similarity(id_a, id_b)
        link = TraceLink(id_a=id_a, id_b=id_b, reason=reason, similarity=sim)
        self.org.links.append(link)
        return link

    def find_most_similar(self, trace_id: int, exclude: Set[int] | None = None) -> Tuple[int, float]:
        """Find the most similar trace to the given one (among read traces)."""
        exclude = exclude or set()
        best_id = -1
        best_sim = -1.0
        for tid, te in self.traces.items():
            if tid == trace_id or tid in exclude or not te.has_been_read:
                continue
            sim = self.trace_similarity(trace_id, tid)
            if sim > best_sim:
                best_sim = sim
                best_id = tid
        return best_id, best_sim

    def suggest_group_name(self, trace_id: int) -> str:
        """Generate a group name from a trace's most discriminating keywords.

        Prefers keywords that appear in 3-15 traces (common enough to be meaningful,
        rare enough to be discriminating). Filters out very long or code-like tokens.
        """
        te = self.traces[trace_id]
        all_kw = list(set(te.keywords + te.content_keywords))

        # Filter: readable, not too long, not code-like
        candidates = [
            kw for kw in all_kw
            if kw not in _STOP_WORDS
            and 3 <= len(kw) <= 25
            and "_" not in kw or kw.count("_") <= 1  # allow one underscore
        ]

        # Score: prefer keywords in 3-15 traces (sweet spot for group names)
        def name_score(kw: str) -> float:
            count = len(self._keyword_to_ids.get(kw, set()))
            if count < 2:
                return 0.1  # too rare, might be noise
            if count > 20:
                return 0.2  # too common, not discriminating
            return 1.0 - abs(count - 8) / 20.0  # peak around 8 occurrences

        scored = sorted(candidates, key=name_score, reverse=True)
        top = scored[:2]
        return "-".join(top) if top else f"group-{len(self.org.groups)}"

    def best_matching_group(self, trace_id: int) -> Tuple[str, float]:
        """Find the existing group with highest mean similarity to this trace."""
        best_name = ""
        best_sim = -1.0
        for name, group in self.org.groups.items():
            if not group.member_ids:
                continue
            sims = [self.trace_similarity(trace_id, mid) for mid in group.member_ids]
            mean_sim = sum(sims) / len(sims)
            if mean_sim > best_sim:
                best_sim = mean_sim
                best_name = name
        return best_name, best_sim

    def split_group(self, group_name: str) -> Tuple[str, str] | None:
        """Split a group into two based on internal similarity structure.

        Returns names of the two resulting groups, or None if can't split.
        """
        group = self.org.groups.get(group_name)
        if not group or len(group.member_ids) < 4:
            return None

        # Simple split: find the member most dissimilar to the rest, seed a new group
        members = list(group.member_ids)
        mean_sims = {}
        for tid in members:
            sims = [self.trace_similarity(tid, other) for other in members if other != tid]
            mean_sims[tid] = sum(sims) / len(sims) if sims else 0.0

        # The most dissimilar member seeds the new group
        outlier = min(mean_sims, key=mean_sims.get)
        new_name = self.suggest_group_name(outlier)
        if new_name == group_name:
            new_name = f"{new_name}-split"

        # Reassign: traces more similar to outlier than to remaining centroid go to new group
        self.create_group(new_name)
        remaining = [tid for tid in members if tid != outlier]
        for tid in remaining:
            sim_to_outlier = self.trace_similarity(tid, outlier)
            sim_to_rest = sum(self.trace_similarity(tid, r) for r in remaining if r != tid)
            sim_to_rest = sim_to_rest / max(1, len(remaining) - 1)
            if sim_to_outlier > sim_to_rest:
                self.assign_to_group(tid, new_name, reason=f"split from {group_name}")

        self.assign_to_group(outlier, new_name, reason=f"seed of split from {group_name}")
        return group_name, new_name

    def merge_groups(self) -> Tuple[str, str] | None:
        """Merge the two most similar groups. Returns merged names or None."""
        groups = list(self.org.groups.values())
        if len(groups) < 2:
            return None

        best_pair = None
        best_sim = -1.0
        for i, ga in enumerate(groups):
            for gb in groups[i + 1:]:
                if not ga.member_ids or not gb.member_ids:
                    continue
                # Cross-group mean similarity
                total = 0.0
                count = 0
                for ida in ga.member_ids:
                    for idb in gb.member_ids:
                        total += self.trace_similarity(ida, idb)
                        count += 1
                sim = total / count if count > 0 else 0.0
                if sim > best_sim:
                    best_sim = sim
                    best_pair = (ga.name, gb.name)

        if best_pair is None or best_sim < 0.15:
            return None

        keep, absorb = best_pair
        absorbed_group = self.org.groups[absorb]
        for tid in list(absorbed_group.member_ids):
            self.assign_to_group(tid, keep, reason=f"merged from {absorb}")
        del self.org.groups[absorb]
        return keep, absorb

    # ------------------------------------------------------------------
    # Filesystem organization (sandboxed to docs/traces/organized/)
    # ------------------------------------------------------------------

    @property
    def _organized_root(self) -> Path:
        """The sandbox directory where organized copies go."""
        return self.repo_root / "docs" / "traces" / "organized"

    def _safe_folder_name(self, group_name: str) -> str:
        """Sanitize a group name into a safe directory name.

        The system can't spell, so folder names come from keywords it
        already extracted — but we still sanitize for filesystem safety.
        """
        # Replace anything that's not alphanumeric, hyphen, or underscore
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", group_name)
        # Collapse multiple underscores/hyphens
        safe = re.sub(r"[_-]{2,}", "-", safe)
        # Trim and lowercase
        safe = safe.strip("-_").lower()
        # Fallback if empty
        return safe or "unnamed-group"

    def create_group_folder(self, group_name: str) -> Dict[str, Any]:
        """Create a filesystem folder for a group.

        Sandboxed: only creates directories under docs/traces/organized/.
        Returns status info.
        """
        if group_name not in self.org.groups:
            return {"success": False, "reason": "group does not exist"}

        folder_name = self._safe_folder_name(group_name)
        folder_path = self._organized_root / folder_name

        # Safety: verify we're inside the sandbox
        try:
            folder_path.resolve().relative_to(self._organized_root.resolve())
        except ValueError:
            return {"success": False, "reason": "path escapes sandbox"}

        folder_path.mkdir(parents=True, exist_ok=True)
        self.org.organized_folders.add(group_name)

        return {
            "success": True,
            "folder": str(folder_path),
            "folder_name": folder_name,
            "group": group_name,
        }

    def organize_trace_to_folder(self, trace_id: int) -> Dict[str, Any]:
        """Copy a trace file into its group's organized folder.

        Copies (not moves) the original trace into docs/traces/organized/<group>/.
        Only works if:
          - The trace is assigned to a group
          - The group has a folder (or creates it automatically)
          - The trace hasn't already been organized to this group

        Returns status info including the destination path.
        """
        if trace_id not in self.org.assignments:
            return {"success": False, "reason": "trace not assigned to any group"}

        group_name = self.org.assignments[trace_id]
        te = self.traces[trace_id]

        # Source file
        source_path = self.repo_root / te.path
        if not source_path.exists():
            return {"success": False, "reason": f"source file not found: {te.path}"}

        # Ensure group folder exists
        folder_name = self._safe_folder_name(group_name)
        folder_path = self._organized_root / folder_name

        # Safety: verify we're inside the sandbox
        try:
            folder_path.resolve().relative_to(self._organized_root.resolve())
        except ValueError:
            return {"success": False, "reason": "path escapes sandbox"}

        folder_path.mkdir(parents=True, exist_ok=True)
        self.org.organized_folders.add(group_name)

        # Destination
        dest_path = folder_path / te.filename

        # Copy (not move) — originals stay untouched
        try:
            shutil.copy2(str(source_path), str(dest_path))
        except OSError as e:
            return {"success": False, "reason": f"copy failed: {e}"}

        self.org.organized_traces.add(trace_id)

        return {
            "success": True,
            "trace_id": trace_id,
            "source": str(source_path),
            "dest": str(dest_path),
            "group": group_name,
            "folder": folder_name,
        }

    def organize_group_batch(self, group_name: str) -> Dict[str, Any]:
        """Organize all assigned traces in a group to its folder.

        Creates the folder if needed, then copies all unorganized members.
        Returns a summary.
        """
        group = self.org.groups.get(group_name)
        if not group:
            return {"success": False, "reason": "group does not exist"}
        if not group.member_ids:
            return {"success": False, "reason": "group has no members"}

        # Create folder
        folder_result = self.create_group_folder(group_name)
        if not folder_result.get("success"):
            return folder_result

        copied = 0
        skipped = 0
        errors = 0
        for tid in group.member_ids:
            if tid in self.org.organized_traces:
                # Check if it's already in the RIGHT folder (might have been reassigned)
                current_group = self.org.assignments.get(tid)
                if current_group == group_name:
                    skipped += 1
                    continue

            result = self.organize_trace_to_folder(tid)
            if result.get("success"):
                copied += 1
            else:
                errors += 1

        return {
            "success": True,
            "group": group_name,
            "folder": folder_result["folder_name"],
            "copied": copied,
            "skipped": skipped,
            "errors": errors,
            "total_members": len(group.member_ids),
        }

    @property
    def organization_ratio(self) -> float:
        """Fraction of assigned traces that have been physically organized."""
        assigned = len(self.org.assignments)
        if assigned == 0:
            return 0.0
        return len(self.org.organized_traces) / assigned

    # ------------------------------------------------------------------
    # Survey results channel
    # ------------------------------------------------------------------

    def absorb_survey(self, results: Any) -> Dict[str, Any]:
        """Absorb results from a surveyor sub-agent.

        Stores the survey results, enriches the similarity cache with
        survey-computed similarities, and optionally creates groups from
        high-quality clusters that don't overlap with existing groups.

        Returns a summary of what was absorbed.
        """
        self._survey_results = results
        absorbed_sims = 0
        groups_created = 0
        traces_assigned = 0

        # 1. Absorb enriched similarity data into the environment
        for (id_a, id_b), sim in results.similarity_matrix.items():
            key = (min(id_a, id_b), max(id_a, id_b))
            self._survey_similarity_boost[key] = sim
            absorbed_sims += 1

        # 2. Convert high-quality cluster suggestions into groups
        for cluster in results.clusters:
            if cluster.mean_similarity < 0.05:
                continue  # too weak

            # Check if this cluster overlaps significantly with an existing group
            member_set = set(cluster.member_ids)
            best_overlap = 0.0
            for group in self.org.groups.values():
                existing_set = set(group.member_ids)
                if existing_set:
                    overlap = len(member_set & existing_set) / len(member_set | existing_set)
                    best_overlap = max(best_overlap, overlap)

            if best_overlap > 0.5:
                continue  # already covered by an existing group

            # Create group from survey cluster
            name = cluster.name
            if name in self.org.groups:
                name = f"{name}-survey"
            if name in self.org.groups:
                name = f"survey-{self._survey_clusters_absorbed}"

            group = self.create_group(
                name,
                seed_keywords=cluster.seed_keywords,
            )
            for tid in cluster.member_ids:
                if tid not in self.org.assignments:
                    self.assign_to_group(
                        tid, name,
                        reason=f"survey cluster (sim={cluster.mean_similarity:.3f})",
                    )
                    traces_assigned += 1
            groups_created += 1
            self._survey_clusters_absorbed += 1

        return {
            "similarities_absorbed": absorbed_sims,
            "groups_created": groups_created,
            "traces_assigned": traces_assigned,
            "survey_clusters": len(results.clusters),
            "survey_cycles_used": results.cycles_used,
            "survey_coherence": results.final_coherence,
        }

    @property
    def has_survey_results(self) -> bool:
        return self._survey_results is not None

    @property
    def survey_cluster_quality(self) -> float:
        """Mean similarity of survey clusters. 0.0 if no survey."""
        if self._survey_results is None or not self._survey_results.clusters:
            return 0.0
        sims = [c.mean_similarity for c in self._survey_results.clusters]
        return sum(sims) / len(sims)

    def survey_enhanced_similarity(self, id_a: int, id_b: int) -> float:
        """Trace similarity enriched with survey data when available.

        If the surveyor computed a similarity for this pair, blend it
        with the standard similarity (survey data is richer because it
        uses combined keyword + temporal proximity).
        """
        base_sim = self.trace_similarity(id_a, id_b)
        key = (min(id_a, id_b), max(id_a, id_b))
        survey_sim = self._survey_similarity_boost.get(key)
        if survey_sim is not None:
            # Blend: 40% base (keyword+file), 60% survey (keyword+temporal, computed on deep-read)
            return 0.4 * base_sim + 0.6 * survey_sim
        return base_sim

    # ------------------------------------------------------------------
    # Frontier sense: endogenous awareness of unexplored territory
    # ------------------------------------------------------------------

    def frontier_pressure(self) -> float:
        """How much unexplored territory weighs on the system.

        Like a slime mold sensing nutrients beyond its current reach —
        not a goal to "process all files", but a felt incompleteness
        that creates persistent pull toward the unknown.

        Uses a sublinear curve so that 70% coverage still feels 45%
        incomplete.  The pressure only truly fades at very high coverage.

            70% read → 0.455 pressure
            90% read → 0.251 pressure
            95% read → 0.139 pressure
        """
        total = self.trace_count
        if total == 0:
            return 0.0
        read = sum(1 for t in self.traces.values() if t.has_been_read)
        ratio = read / total
        return (1.0 - ratio) ** 0.6

    def frontier_novelty(self) -> float:
        """How much of the unknown is genuinely new vs. more-of-the-same.

        Measures the fraction of the total keyword vocabulary that exists
        ONLY in unread traces.  When the frontier is full of familiar
        topics, novelty is low (near frontier).  When there are entire
        unexplored topic clusters, novelty is high (far frontier).

        This naturally captures the near/far frontier gradient without
        needing two separate signals.
        """
        read_kw: set = set()
        unread_kw: set = set()
        for te in self.traces.values():
            if te.has_been_read:
                read_kw.update(te.keywords)
                read_kw.update(te.content_keywords)
            else:
                # Only index-level keywords for unread traces (haven't read content)
                unread_kw.update(te.keywords)
        all_kw = read_kw | unread_kw
        if not all_kw:
            return 0.0
        frontier_only = unread_kw - read_kw
        return len(frontier_only) / len(all_kw)

    # ------------------------------------------------------------------
    # Observation snapshot
    # ------------------------------------------------------------------

    def observe(self) -> Dict[str, float]:
        """Return a numeric observation of the current organizational state."""
        total = self.trace_count
        if total == 0:
            return {k: 0.0 for k in _OBS_KEYS}

        assigned_count = len(self.org.assignments)
        read_count = sum(1 for t in self.traces.values() if t.has_been_read)
        group_count = len(self.org.groups)
        link_count = len(self.org.links)

        # Focus trace features
        focus_sim_to_group = 0.0
        focus_novelty = 1.0
        if self._focus_id is not None and self._focus_id in self.org.assignments:
            gname = self.org.assignments[self._focus_id]
            group = self.org.groups.get(gname)
            if group and len(group.member_ids) > 1:
                sims = [
                    self.trace_similarity(self._focus_id, mid)
                    for mid in group.member_ids
                    if mid != self._focus_id
                ]
                focus_sim_to_group = sum(sims) / len(sims) if sims else 0.0
        if self._focus_id is not None:
            _, best_sim = self.find_most_similar(self._focus_id)
            focus_novelty = max(0.0, 1.0 - best_sim)

        obs = {
            "orphan_ratio": max(0.0, 1.0 - assigned_count / total),
            "read_ratio": read_count / total,
            "group_count": min(1.0, group_count / 20.0),
            "link_density": min(1.0, link_count / max(1, total)),
            "mean_group_size": (assigned_count / max(1, group_count)) / total if group_count > 0 else 0.0,
            "intra_group_similarity": self.mean_intra_group_similarity(),
            "inter_group_distinction": self.inter_group_distinction(),
            "focus_sim_to_group": focus_sim_to_group,
            "focus_novelty": focus_novelty,
            "revision_ratio": min(1.0, self.org.revision_count / max(1, assigned_count)),
            "has_focus": 1.0 if self._focus_id is not None else 0.0,
            # Survey-derived signals
            "has_survey": 1.0 if self._survey_results is not None else 0.0,
            "survey_cluster_quality": self.survey_cluster_quality,
            # Refiner-derived signals
            "has_refiner": 1.0 if self._refiner_results is not None else 0.0,
            "refiner_coverage": self._refiner_coverage(),
            "refiner_mean_quality": self._refiner_mean_quality(),
            # Filesystem organization
            "organization_ratio": self.organization_ratio,
            # Lexicon development — the agent's linguistic maturity
            "lexicon_maturity": min(1.0, self.lexicon.traces_ingested / max(1, total)),
            "lexicon_vocab": min(1.0, self.lexicon.vocabulary_size / 500.0),
            # Frontier sense — felt awareness of unexplored territory
            "frontier_pressure": self.frontier_pressure(),
            "frontier_novelty": self.frontier_novelty(),
        }
        return obs

    def _refiner_coverage(self) -> float:
        """Fraction of groups+orphans the refiner has examined."""
        if self._refiner_results is None:
            return 0.0
        total = len(self.org.groups) + (self.trace_count - len(self.org.assignments))
        examined = self._refiner_results.groups_examined + self._refiner_results.orphans_examined
        return examined / max(1, total)

    def _refiner_mean_quality(self) -> float:
        """Mean group quality from the refiner's analysis."""
        if self._refiner_results is None or not self._refiner_results.group_quality:
            return 0.0
        vals = list(self._refiner_results.group_quality.values())
        return sum(vals) / len(vals)

    # ------------------------------------------------------------------
    # Export results
    # ------------------------------------------------------------------

    def export_organization(self, path: str | Path) -> None:
        """Write the organizational state as a JSON file."""
        result = {
            "groups": {},
            "unassigned": [],
            "links": [],
            "stats": {
                "total_traces": self.trace_count,
                "assigned": len(self.org.assignments),
                "groups": len(self.org.groups),
                "links": len(self.org.links),
                "revisions": self.org.revision_count,
            },
        }
        for name, group in self.org.groups.items():
            result["groups"][name] = {
                "seed_keywords": group.seed_keywords,
                "members": [
                    {
                        "trace_id": tid,
                        "filename": self.traces[tid].filename,
                        "title": self.traces[tid].title,
                        "reason": self.org.assignment_reasons.get(tid, ""),
                    }
                    for tid in group.member_ids
                ],
            }
        result["unassigned"] = [
            {"trace_id": tid, "filename": self.traces[tid].filename}
            for tid in range(self.trace_count)
            if tid not in self.org.assignments
        ]
        for link in self.org.links:
            result["links"].append({
                "trace_a": self.traces[link.id_a].filename,
                "trace_b": self.traces[link.id_b].filename,
                "similarity": round(link.similarity, 3),
                "reason": link.reason,
            })

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "the", "and", "for", "that", "this", "with", "from", "are", "was",
    "but", "not", "have", "had", "has", "been", "were", "will", "would",
    "could", "should", "can", "may", "also", "into", "than", "then",
    "when", "where", "which", "what", "more", "some", "other", "each",
    "even", "instead", "added", "used", "using", "now", "new", "set",
    "get", "one", "two", "all", "any", "only", "very", "just", "how",
    "its", "our", "their", "there", "here", "those", "these", "such",
    "well", "too", "yet", "still", "much", "many", "few", "own",
    "does", "did", "done", "make", "made", "way", "use", "let",
    "need", "see", "try", "run", "per", "via", "def", "self", "none",
    "true", "false", "return", "import", "class", "pass", "elif",
})

_OBS_KEYS = [
    "orphan_ratio", "read_ratio", "group_count", "link_density",
    "mean_group_size", "intra_group_similarity", "inter_group_distinction",
    "focus_sim_to_group", "focus_novelty", "revision_ratio", "has_focus",
    "has_survey", "survey_cluster_quality",
    "has_refiner", "refiner_coverage", "refiner_mean_quality",
    "organization_ratio",
    "lexicon_maturity", "lexicon_vocab",
    "frontier_pressure", "frontier_novelty",
]
