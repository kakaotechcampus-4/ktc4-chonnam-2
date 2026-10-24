"""Fresh process/download and kill-boundary consumer; never print diagnostics."""
from io import StringIO
import hashlib
import json
import os
from pathlib import Path
from threading import Event
from types import MappingProxyType
import warnings

warnings.filterwarnings('ignore', message='Using `httpx` with `starlette.testclient` is deprecated.*')
from fastapi.testclient import TestClient
from daesingo.api.app import create_app
from daesingo.api.composition import ApiComposition
from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.logging import configure_logging
from daesingo.recording import RecordingService


def main():
    config = RuntimeConfig.from_mapping('api', {
        'DAESINGO_RUNTIME_DB_URL': os.environ['ASSET_TEST_DB'],
        'DAESINGO_RUNTIME_MEDIA_ROOT': os.environ['ASSET_TEST_ROOT'],
        'DAESINGO_RUNTIME_API_TEMP_ROOT': os.environ['ASSET_TEST_ROOT']})
    startup = Startup(config, MappingProxyType({}), configure_logging('api', stream=StringIO()))
    phase = os.environ.get('ASSET_TEST_PHASE')
    app = create_app(startup=startup)
    composition = app.state.composition
    def pause(connection):
        marker = Path(os.environ['ASSET_TEST_MARKER'])
        temporary = marker.with_suffix('.tmp')
        temporary.write_text(json.dumps({'connection': connection, 'checkedout': composition.engine.pool.checkedout()}))
        temporary.replace(marker)
        Event().wait(30)
        raise RuntimeError('interruption boundary expired')
    if phase == 'read':
        original = RecordingService.open_derived_asset
        def open_asset(self, ref):
            opened = original(self, ref)
            try:
                pause(self._repository._connection.exec_driver_sql('SELECT CONNECTION_ID()').scalar_one())
            finally:
                opened.stream.close()
        RecordingService.open_derived_asset = open_asset
    if phase == 'detached':
        original = ApiComposition.load_asset
        def load(self, *args):
            result = original(self, *args)
            pause(None)
            return result
        ApiComposition.load_asset = load
    with TestClient(app) as client:
        response = client.get(os.environ['ASSET_TEST_PATH'])
    print(json.dumps({'status': response.status_code, 'sha256': hashlib.sha256(response.content).hexdigest(),
        'type': response.headers.get('content-type'), 'length': response.headers.get('content-length'),
        'disposition': response.headers.get('content-disposition'), 'cache': response.headers.get('cache-control')}))


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        raise SystemExit(1) from None
