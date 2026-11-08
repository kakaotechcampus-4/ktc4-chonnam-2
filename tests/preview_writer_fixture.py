"""Synthetic final-writer mode for existing C feature/reader regressions.

Bridge production defaults are tested separately, including pinned C source.
This fixture is imported only by tests which must seed final preview jobs.
"""
import pytest


@pytest.fixture(autouse=True)
def final_preview_writer(monkeypatch):
    from daesingo.case import candidate_video
    monkeypatch.setattr(candidate_video, "PREVIEW_REQUESTS_ENABLED", True)
