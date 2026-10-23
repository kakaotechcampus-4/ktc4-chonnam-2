"""Fresh interpreter consumer for persisted FrameRef acceptance, no raw logs."""
from io import StringIO
import hashlib
import json
import os
from types import MappingProxyType
import warnings

warnings.filterwarnings('ignore', message='Using `httpx` with `starlette.testclient` is deprecated.*')
from fastapi.testclient import TestClient
from daesingo.api.app import create_app
from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.logging import configure_logging


def main():
    config = RuntimeConfig.from_mapping('api', {
        'DAESINGO_RUNTIME_DB_URL': os.environ['FRAME_TEST_DB'],
        'DAESINGO_RUNTIME_MEDIA_ROOT': os.environ['FRAME_TEST_ROOT'],
        'DAESINGO_RUNTIME_API_TEMP_ROOT': os.environ['FRAME_TEST_ROOT']})
    startup = Startup(config, MappingProxyType({}), configure_logging('api', stream=StringIO()))
    with TestClient(create_app(startup=startup)) as client:
        response = client.get(os.environ['FRAME_TEST_PATH'])
    print(json.dumps({'status': response.status_code, 'sha256': hashlib.sha256(response.content).hexdigest(),
                      'content_type': response.headers.get('content-type'), 'length': response.headers.get('content-length')}))


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        raise SystemExit(1) from None
