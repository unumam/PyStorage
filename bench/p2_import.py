from datetime import datetime
import os
import importlib

from pygraphdb.helpers import StatsCounter
from pygraphdb.helpers import export_edges_into_graph

import config


class BulkImporter(object):
    """
    Performs multithreaded bulk import into DB.
    Saves stats.
    """

    def printable_bytes(self, size, decimal_places=3):
        for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
            if size < 1024.0:
                break
            size /= 1024.0
        return f"{size:.{decimal_places}f}{unit}"

    def printable_count(self, size, decimal_places=3):
        for unit in ['', 'K', 'M', 'G', 'T']:
            if size < 1000.0:
                break
            size /= 1000.0
        return f"{size:.{decimal_places}f}{unit}"

    def parse_without_importing_if_unknown(self, dataset_path):
        # Avoid repeating ourselves.
        dataset_name = config.dataset_name(dataset_path)
        if config.stats.find_index(
            wrapper_class='Parsing in Python',
            operation_name='Insert Dump',
            dataset=dataset_name,
        ) != None:
            return

        class PseudoGraph(object):
            __edge_type__ = dict
            __max_batch_size__ = 1000000

            def __init__(self):
                self.count = 0

            def biggest_edge_id(self) -> int:
                return self.count

            def upsert_edges(self, es) -> int:
                self.count += len(es)
                return len(es)

        g = PseudoGraph()
        counter = StatsCounter()
        counter.handle(lambda: export_edges_into_graph(dataset_path, g))
        config.stats.upsert(
            wrapper_class='Parsing in Python',
            operation_name='Insert Dump',
            dataset=dataset_name,
            stats=counter,
        )

    def run(self):
        for dataset_path in config.datasets:
            # Define a baseline, so we know how much time it took
            # to read the data vs actually importing it into DB
            # and building indexes.
            self.parse_without_importing_if_unknown(dataset_path)

            for graph_type in config.wrapper_types:
                url = config.database_url(graph_type, dataset_path)
                if url is None:
                    continue

                g = graph_type(url)
                dataset_name = config.dataset_name(dataset_path)
                wrapper_name = config.wrapper_name(g)

                if (g.count_edges() != 0):
                    print(f'-- Skipping: {dataset_name} -> {wrapper_name}')
                    continue
                file_size = os.path.getsize(dataset_path)
                expected_edges = config.dataset_number_of_edges(dataset_path)
                print(f'-- Bulk importing: {dataset_name} -> {wrapper_name}')
                print(f'--- started at:', datetime.now().strftime('%H:%M:%S'))
                print(f'--- file size:', self.printable_bytes(file_size))

                def import_one() -> int:
                    g.insert_adjacency_list(dataset_path)
                    return g.count_edges()

                counter = StatsCounter()
                counter.handle(import_one)
                config.stats.upsert(
                    wrapper_class=wrapper_name,
                    operation_name='Insert Dump',
                    dataset=dataset_name,
                    stats=counter,
                )
                print(f'--- edges:', self.printable_count(counter.count_operations))
                print(f'--- edges/second:',
                      self.printable_count(counter.ops_per_sec()))
                print(f'--- bytes/second:',
                      self.printable_bytes(file_size / counter.time_elapsed))
                print(f'--- finished at:', datetime.now().strftime('%H:%M:%S'))
                config.stats.dump_to_file()


if __name__ == "__main__":
    try:
        BulkImporter().run()
    finally:
        config.stats.dump_to_file()
