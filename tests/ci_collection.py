"""Record pytest's actual final selection, including legacy harness markers."""

import json
from pathlib import Path


def pytest_addoption(parser):
    parser.addoption('--ci-collection', help='Write final collected node identities')


def pytest_collection_finish(session):
    path = session.config.getoption('--ci-collection')
    if path:
        Path(path).write_text(json.dumps([item.nodeid for item in session.items], indent=2),
                              encoding='utf-8')
