"""Test-only owned process checkpoints around the real upload publication/tx."""
import os
from pathlib import Path
import sys
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))

import daesingo.case as case_api
from daesingo.api import upload, composition
from daesingo.api.__main__ import main
from daesingo.api.composition import ApiComposition
from daesingo.recording import RecordingService
from test_sources_mysql import Probe


def checkpoint():
    Path(os.environ['UPLOAD_CHECKPOINT']).write_text('entered', encoding='ascii')
    Event().wait(60)
    raise RuntimeError('owned checkpoint not released')


if __name__ == '__main__':
    mode = os.environ['UPLOAD_KILL_MODE']
    composition.FfprobeMediaProbe = Probe
    original_publish = upload.publish
    def publish(*args):
        if mode == 'before_publish':
            checkpoint()
        result = original_publish(*args)
        if mode == 'after_publish':
            checkpoint()
        return result
    upload.publish = publish
    original_attach = case_api.record_source_registered
    def attach(*args, **kwargs):
        original_attach(*args, **kwargs)
        if mode == 'before_commit':
            checkpoint()
    case_api.record_source_registered = attach
    original_view = ApiComposition.get_view
    def view(*args):
        if mode == 'after_commit':
            checkpoint()
        return original_view(*args)
    ApiComposition.get_view = view
    raise SystemExit(main(sys.argv[1:]))
