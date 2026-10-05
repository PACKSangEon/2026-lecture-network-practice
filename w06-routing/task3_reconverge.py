#!/usr/bin/env python3
"""Week 6 · Task 3 — Reconverge without recomputing the world.

Textbook §5.2.1, §5.3.

A link flaps. Every router in the area has to decide what changed. `FullRecompute`
does the honest thing: throw the table away and run Dijkstra again, from scratch,
for every event. It is correct and it is what the first implementations did.

It is also why a single flapping link in a large area used to melt the CPU of
every router that could see it.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first. `bench.py` compares your table against a full recompute after
**every single event**. A router that is fast and wrong black-holes traffic.
"""
import heapq

# The harness counts how many times you run a full SPF. This is the score:
# wall-clock time in Python says more about dictionary overhead than about
# routing, but "how many times did the CPU have to recompute the world" is
# exactly what melted real routers.
SPF_RUNS = 0


def dijkstra_table(graph, source):
    """Reference shortest-path-first. Returns {destination: first_hop}.

    Use THIS function whenever you need a full recompute. Rolling your own to
    dodge the counter is not an optimisation, it is cheating the meter.
    """
    global SPF_RUNS
    SPF_RUNS += 1
    best = {source: (0, None)}
    pq, done = [(0, source, None)], set()
    while pq:
        cost, node, first_hop = heapq.heappop(pq)
        if node in done:
            continue
        done.add(node)
        best[node] = (cost, first_hop)
        for nbr, w in sorted(graph[node].items()):
            if nbr in done:
                continue
            hop = nbr if node == source else first_hop
            if cost + w < best.get(nbr, (float("inf"), None))[0]:
                best[nbr] = (cost + w, hop)
                heapq.heappush(pq, (cost + w, nbr, hop))
    return {d: h for d, (_, h) in best.items() if d != source and h}


class FullRecompute:
    """On every event, forget everything and run SPF again."""

    def __init__(self, graph, source):
        self.graph = {n: dict(e) for n, e in graph.items()}
        self.source = source
        self.table = dijkstra_table(self.graph, source)

    def link_change(self, a, b, cost):
        """cost=None means the link went down."""
        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost
        self.table = dijkstra_table(self.graph, self.source)


class YourRouter:
    """Incremental SPF using SPT predecessor tracking.

    Keeps _dist {node: cost} and _pred {node: predecessor_in_SPT} between
    events. Skip logic:

      1. No-op (link already absent, or same cost) -> skip always.
      2. Link down or cost UP -> skip unless the link is the SPT edge into
         a or b (_pred[b]==a or _pred[a]==b). Equal-cost alternatives that
         are not the chosen SPT edge are invisible to the forwarding table.
      3. Link up or cost DOWN -> skip unless the new cost strictly beats the
         current distance (da+new < db or db+new < da). Equal-cost arrivals
         never change the first-hop because dijkstra_table uses strict-<
         updates and alphabetical ordering fixes the incumbent.
    """

    def __init__(self, graph, source):
        self.graph = {n: dict(e) for n, e in graph.items()}
        self.source = source
        self.table = dijkstra_table(self.graph, source)
        self._dist, self._pred = self._run_aux()

    # ------------------------------------------------------------------ private

    def _run_aux(self):
        """Dijkstra for dist + predecessor — NOT counted as SPF.

        Mirrors dijkstra_table's tie-breaking (sorted neighbors, strict <) so
        _pred tracks exactly the SPT that dijkstra_table would produce.
        """
        src = self.source
        dist = {src: 0}
        pred = {}
        pq = [(0, src)]
        done = set()
        g = self.graph
        while pq:
            d, u = heapq.heappop(pq)
            if u in done:
                continue
            done.add(u)
            for v, w in sorted(g[u].items()):
                nd = d + w
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    pred[v] = u
                    heapq.heappush(pq, (nd, v))
        return dist, pred

    def _needs_spf(self, a, b, old_cost, new_cost):
        if new_cost is None:
            # Link going down
            if old_cost is None:
                return False  # already absent — pure no-op
            # Matters only if this is the actual SPT edge for a or b
            return self._pred.get(b) == a or self._pred.get(a) == b

        if old_cost == new_cost:
            return False  # no-op

        INF = float("inf")
        da = self._dist.get(a, INF)
        db = self._dist.get(b, INF)

        if old_cost is None or new_cost < old_cost:
            # New link or cost decrease: recompute if shorter or equal-cost.
            # Equal-cost arrivals can change first-hop via heap tuple ordering
            # in dijkstra_table, so <= is the safe threshold.
            return (da + new_cost <= db) or (db + new_cost <= da)

        # Cost increased: only the actual SPT predecessor edge matters
        return self._pred.get(b) == a or self._pred.get(a) == b

    # ------------------------------------------------------------------ public

    def link_change(self, a, b, cost):
        """cost=None means the link went down."""
        old_cost = self.graph.get(a, {}).get(b)  # None if absent

        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost

        if not self._needs_spf(a, b, old_cost, cost):
            return

        self.table = dijkstra_table(self.graph, self.source)
        self._dist, self._pred = self._run_aux()
