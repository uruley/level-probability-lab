import importlib.util
import json
from pathlib import Path


def worker():
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'webull_stream_worker.py'
    spec = importlib.util.spec_from_file_location('webull_stream_worker', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Level:
    def __init__(self, price, size):
        self.price = price
        self.size = size


class Quote:
    def __init__(self, bids, asks):
        self.bids = bids
        self.asks = asks


def test_quote_ladder_writes_every_received_level(tmp_path):
    module = worker()
    quote = Quote(
        [Level(100, 10), Level(99.5, 20)],
        [Level(100.1, 5), Level(None, 9), Level(100.3, 8)],
    )
    record = module.quote_record(quote, 1000.0)
    assert record['bid'] == 100 and record['ask'] == 100.1
    assert record['bids'] == [
        {'level': 0, 'price': 100.0, 'size': 10},
        {'level': 1, 'price': 99.5, 'size': 20},
    ]
    assert record['asks'] == [
        {'level': 0, 'price': 100.1, 'size': 5},
        {'level': 2, 'price': 100.3, 'size': 8},
    ]
    assert record['asks'][1]['price'] != record['asks'][0]['price']
    path = tmp_path / 'stream.jsonl'
    module.append_jsonl(path, record)
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['bids'] == record['bids'] and saved['asks'] == record['asks']


def test_non_200_depth_is_rejected():
    module = worker()
    assert module.depth_status(200) == 'requested'
    assert module.depth_status(417) == 'rejected'
    assert module.depth_status(None) == 'rejected'


def test_one_level_quote_is_not_padded_and_not_called_level2():
    module = worker()
    state = {'level2': 'requested'}
    record = module.apply_quote(state, Quote([Level(100, 4)], [Level(100.2, 3)]), 1000.0)
    assert record['bids'] == [{'level': 0, 'price': 100.0, 'size': 4}]
    assert record['asks'] == [{'level': 0, 'price': 100.2, 'size': 3}]
    assert state['level2'] == 'top_of_book_only'
    assert state['level2_bids'] == 1 and state['level2_asks'] == 1
    module.apply_quote(state, Quote([Level(100, 4), Level(99, 6)], [Level(100.2, 3)]), 1001.0)
    assert state['level2'] == 'received'
    rejected = {'level2': 'rejected'}
    module.apply_quote(rejected, Quote([Level(100, 4), Level(99, 6)], []), 1002.0)
    assert rejected['level2'] == 'rejected'
    assert rejected['level2_bids'] == 2
