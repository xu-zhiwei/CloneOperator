"""Finite, refreshed batches over a stage's safe candidate locations.

This adapter leaves the frozen operator repository and its k API unchanged.
It deliberately does not use apply(k=large): generated sites cannot extend
the same batch, and every selected location is reanalyzed before applying.
"""
import hashlib
import random
from collections import Counter


def key(edits):
    return tuple(sorted((e.start_byte, e.end_byte) for e in edits))


def intersects(a, b):
    if a[0] == a[1] or b[0] == b[1]:
        return max(a[0], b[0]) <= min(a[1], b[1])
    return max(a[0], b[0]) < min(a[1], b[1])


def move_span(span, edits, conservative=False):
    """Remap a pending location or a conservative conflict guard in bytes.

    A location partly overwritten by another edit is invalidated. A guard
    instead expands to the enclosing replacement; it must never disappear.
    Edits use coordinates before this application, including UTF-8 lengths.
    """
    start, end = span
    for e in sorted(edits, key=lambda x: x['start_byte']):
        a, b = e['start_byte'], e['end_byte']
        if start >= b:
            continue
        elif end <= a:
            break
        elif start <= a and end >= b:
            continue
        elif not conservative:
            return None
    # Mapping each boundary separately also handles several edits inside it.
    def boundary(p, right):
        delta = 0
        for e in sorted(edits, key=lambda x: x['start_byte']):
            a, b = e['start_byte'], e['end_byte']
            size = len(e['after'].encode('utf-8'))
            if a == b:
                if a < p or a == p and not right:
                    delta += size
            elif b <= p:
                delta += size - (b - a)
            elif a < p < b:
                return a + delta + (size if right else 0)
            elif p == a:
                return a + delta
        return p + delta
    if start == end:
        # Original insertion sites are after an existing statement or opening
        # brace. Keep that boundary before a new snippet, rather than after
        # its trailing whitespace (which is not an AST insertion boundary).
        point = boundary(start, True)
        return point, point
    return boundary(start, False), boundary(end, True)


def output_regions(edits):
    regions = []
    delta = 0
    for e in sorted(edits, key=lambda x: x['start_byte']):
        start = e['start_byte'] + delta
        size = len(e['after'].encode('utf-8'))
        regions.append((start, start + size))
        delta += size - (e['end_byte'] - e['start_byte'])
    return regions


class BatchComposer:
    """Batch each operator once, with conservative cross-stage conflicts.

    Conflict guards are remapped source regions, not a full AST provenance
    system. Nested conflicting regions can therefore be conservatively
    skipped. Counts expose these skips rather than claiming optimal coverage.
    """
    def __init__(self, inventory, strategies, config, pid):
        self.inventory = inventory
        self.strategies = strategies
        self.config = config
        self.pid = pid
        impl_to_paper = {v['implementation_id']: p for p, v in inventory.items()}
        self.inverses = {p: impl_to_paper[v['inverse_id']] for p, v in inventory.items()}
        self.guards = []
        self.reservations = {}
        self.frozen_sites = {}
        self.frozen_analysis = {}
        self.history = set()

    def seed(self, paper, extra=''):
        material = '%s|%s|%s|%s|%s' % (
            self.config['name'], self.config['seed'], self.pid, paper, extra)
        return int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], 'big')

    def snapshot(self, paper, code):
        strategy = self.strategies[paper]
        strategy.rng = random.Random(self.seed(paper, 'snapshot'))
        ctx = strategy.make_context(code)
        if ctx.tree.root_node.has_error:
            return [], Counter(input_parse_error=1)
        if strategy.language == 'java' and not ctx.translation_safe:
            return [], Counter(java_lexical_translation_not_supported=1)
        choices = list(strategy.candidates(ctx))
        return choices, Counter(r['reason'] for r in ctx.rejections)

    def reserve_group(self, group, code):
        by_site = {}
        for paper in group:
            choices, _ = self.snapshot(paper, code)
            for edits in choices:
                by_site.setdefault(key(edits), set()).add(paper)
        # Alternatives compete at the same loop/dispatch region. Assignment
        # depends only on source, configuration, and seed, never model scores.
        reservations = []
        for site, papers in sorted(by_site.items()):
            names = sorted(papers)
            n = self.seed('/'.join(group), str(site)) % len(names)
            reservations.append((site, names[n]))
        self.reservations[tuple(group)] = reservations

    def group_for(self, paper):
        return next((tuple(g) for g in self.config['exclusive_groups'] if paper in g), None)

    def blocked(self, paper, site):
        inverse = self.inverses[paper]
        group = self.group_for(paper)
        if group:
            owners = [owner for reserved, owner in self.reservations[group] if reserved == site]
            if not owners:
                return 'generated_or_invalidated_exclusive_site'
            if paper not in owners:
                return 'assigned_to_other_safe_construction'
        for old_paper, regions in self.guards:
            if old_paper == inverse or group and old_paper in group:
                if any(intersects(a, b) for a in site for b in regions):
                    return 'inverse_or_conversion_region_conflict'
        return None

    def remap_state(self, edits):
        self.guards = [(p, [move_span(s, edits, conservative=True) for s in spans])
                       for p, spans in self.guards]
        for group, rows in self.reservations.items():
            updated = []
            for site, owner in rows:
                spans = [move_span(s, edits) for s in site]
                if all(s is not None for s in spans):
                    updated.append((tuple(sorted(spans)), owner))
            self.reservations[group] = updated
        for paper, sites in self.frozen_sites.items():
            updated = []
            for location_id, site in sites:
                if site is None:
                    updated.append((location_id, None))
                    continue
                spans = [move_span(s, edits) for s in site]
                updated.append((location_id, tuple(sorted(spans)) if all(s is not None for s in spans) else None))
            self.frozen_sites[paper] = updated

    def freeze_insertion_phase(self, papers, code):
        # All insertion operators share the pre-insertion location snapshot.
        # Later operators must not proliferate sites inside earlier snippets.
        for paper in papers:
            choices, rejections = self.snapshot(paper, code)
            sites = sorted(set(key(c) for c in choices))
            self.frozen_sites[paper] = list(enumerate(sites))
            self.frozen_analysis[paper] = (len(choices), rejections)

    def apply_stage(self, paper, code):
        strategy = self.strategies[paper]
        if paper in self.frozen_sites:
            indexed_sites = list(self.frozen_sites[paper])
            alternative_count, initial_rejections = self.frozen_analysis[paper]
        else:
            candidates, initial_rejections = self.snapshot(paper, code)
            indexed_sites = list(enumerate(sorted(set(key(c) for c in candidates))))
            alternative_count = len(candidates)
        initial_count = len(indexed_sites)
        # Small locations first retain opportunities in nested expressions.
        # Fresh analysis below avoids stale bindings or colliding fresh names.
        rng = random.Random(self.seed(paper, 'order'))
        pending = [(n, site) for n, site in indexed_sites if site is not None]
        rng.shuffle(pending)
        pending.sort(key=lambda item: sum(b-a for a, b in item[1]))
        changes = []
        skipped = Counter()
        skipped['overwritten_before_insertion_stage'] += sum(site is None for n, site in indexed_sites)
        failed = Counter()
        reasons = Counter()
        original_candidates = strategy.candidates
        before_hash = hashlib.sha256(code.encode()).hexdigest()
        while pending:
            location_id, site = pending.pop(0)
            reason = self.blocked(paper, site)
            if reason:
                skipped[reason] += 1
                continue
            matched = []
            def only_location(ctx):
                # Recheck the target's AST sites rather than reconstructing
                # thousands of unrelated candidates on every local edit.
                # Multi-edit rules can anchor on any footprint. A full scan
                # fallback preserves unusual constructor opportunities.
                identify = strategy.identify_sites
                def nearby(current):
                    for node in identify(current):
                        if any(node.start_byte <= a and b <= node.end_byte for a, b in site):
                            yield node
                strategy.identify_sites = nearby
                try:
                    choices = list(original_candidates(ctx))
                finally:
                    strategy.identify_sites = identify
                selected = [edits for edits in choices if key(edits) == site]
                if not selected:
                    choices = list(original_candidates(ctx))
                    selected = [edits for edits in choices if key(edits) == site]
                matched[:] = selected
                return selected
            strategy.candidates = only_location
            strategy.seed = self.seed(paper, str(location_id))
            try:
                applied = strategy.apply(code, k=1)
            finally:
                strategy.candidates = original_candidates
            reasons.update(r['reason'] for r in applied.rejections)
            if not applied.successful or applied.code == code:
                failed['no_longer_safe_or_available' if not matched else 'candidate_validation_failed'] += 1
                continue
            fingerprint = hashlib.sha256(applied.code.encode()).hexdigest()
            if fingerprint in self.history:
                failed['previous_complete_source_state'] += 1
                continue
            assert applied.successful == 1 and len(applied.changes) == 1
            change = applied.changes[0]
            edits = change['edits']
            refreshed = []
            for n, remaining in pending:
                spans = [move_span(s, edits) for s in remaining]
                if any(s is None for s in spans):
                    skipped['overwritten_snapshot_location'] += 1
                else:
                    refreshed.append((n, tuple(sorted(spans))))
            pending = refreshed
            self.remap_state(edits)
            self.guards.append((paper, output_regions(edits)))
            self.history.add(fingerprint)
            changes.append(dict(change, snapshot_location_id=location_id,
                                before_sha256=hashlib.sha256(code.encode()).hexdigest(),
                                after_sha256=fingerprint))
            code = applied.code
        assert initial_count == len(changes) + sum(skipped.values()) + sum(failed.values())
        return code, dict(paper_id=paper, implementation_id=self.inventory[paper]['implementation_id'],
            requested=initial_count, snapshot_safe_locations=initial_count,
            snapshot_alternative_candidates=alternative_count, successful=len(changes),
            skipped=dict(skipped), failed=dict(failed), changes=changes,
            before_sha256=before_hash, after_sha256=hashlib.sha256(code.encode()).hexdigest(),
            initial_analysis_rejections=dict(initial_rejections), rejections=dict(reasons))

    def compose(self, code):
        original = code
        self.history.add(hashlib.sha256(code.encode()).hexdigest())
        trace = []
        frozen_insertion = False
        for stage in self.config['stages']:
            paper = stage['paper_id']
            if stage.get('phase') == 7 and not frozen_insertion:
                self.freeze_insertion_phase([s['paper_id'] for s in self.config['stages'] if s.get('phase') == 7], code)
                frozen_insertion = True
            group = self.group_for(paper)
            if group and group not in self.reservations:
                self.reserve_group(group, code)
            code, record = self.apply_stage(paper, code)
            trace.append(record)
        return dict(program_id=self.pid, code=code,
            original_sha256=hashlib.sha256(original.encode()).hexdigest(),
            effectively_changed=code != original,
            successful=sum(t['successful'] for t in trace), attempted_operators=len(trace), trace=trace,
            original_utf8_bytes=len(original.encode()), mutated_utf8_bytes=len(code.encode()),
            validation='candidate_checks_and_parse_only; conservative remapped-region conflicts; finite stage snapshots')
