import random
from random import SystemRandom
from typing import List

from PyWrappedGraph.Algorithms import yield_edges_from, chunks
from P0Config import P0Config


class P3TasksSampler(object):
    """
        Select this data beforehand to:
        - avoid affecting the runtime of benchmark.
        - perform same "random" operations on different DBs.
    """

    def __init__(self):
        self.conf = P0Config.shared()
        self.count_finds = self.conf.count_finds
        self.count_analytics = self.conf.count_analytics
        self.count_changes = self.conf.count_changes
        self.clear()

    def clear(self):
        self.edges_to_query = []
        self.nodes_to_query = []
        self.nodes_to_analyze = []
        self.edges_to_change_by_one = []
        self.edges_to_change_batched = [[]]
        self._buffer_edges = []

    def number_of_needed_samples(self) -> int:
        return max(self.count_finds,
                   self.count_analytics,
                   self.count_changes)

    def sample_reservoir(self, filename: str) -> int:
        self.clear()
        count_seen = 0
        count_needed = self.number_of_needed_samples()
        for e in yield_edges_from(filename):
            count_seen += 1
            if len(self._buffer_edges) < count_needed:
                self._buffer_edges.append(e)
            else:
                s = int(random.random() * count_seen)
                if s < count_needed:
                    self._buffer_edges[s] = e
        self._split_samples_into_tasks()

    def sample_from_distribution(self, count_nodes):
        count_needed = self.number_of_needed_samples()
        while len(self._buffer_edges) < count_needed:
            v1 = random.randrange(1, count_nodes)
            v2 = random.randrange(1, count_nodes)
            if v1 == v2:
                continue
            self._buffer_edges.append({
                'v1': v1,
                'v2': v2,
            })
        self._split_samples_into_tasks()

    def sample_nodes_from_edges(self, cnt) -> List[int]:
        cnt = min(len(self._buffer_edges), cnt)
        es = random.sample(self._buffer_edges, cnt)
        # Save only unique values, but don't forget to shuffle.
        vs = {(e['v1'] if bool(random.getrandbits(1)) else e['v2'])
              for e in es}
        vs = list(vs)
        random.shuffle(vs)
        return vs

    def _split_samples_into_tasks(self):
        self.count_finds = min(len(self._buffer_edges), self.count_finds)
        self.edges_to_query = random.sample(
            self._buffer_edges, self.count_finds)
        self.nodes_to_query = self.sample_nodes_from_edges(
            self.count_finds)
        self.nodes_to_analyze = self.sample_nodes_from_edges(
            self.count_analytics)
        self.edges_to_change_by_one = self._buffer_edges[:self.count_changes]
        self.edges_to_change_batched = list(chunks(
            self._buffer_edges[:self.count_changes],
            100,
        ))