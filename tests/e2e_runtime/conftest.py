from io import StringIO
from types import MappingProxyType

import pytest

from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.db import create_api_engine
from daesingo.common.db.migrate import upgrade_all
from daesingo.common.logging import configure_logging


@pytest.fixture
def async_db(mysql_schema_url, tmp_path):
    upgrade_all(mysql_schema_url)
    config = RuntimeConfig.from_mapping("api", {
        "DAESINGO_RUNTIME_DB_URL": mysql_schema_url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(tmp_path),
        "DAESINGO_RUNTIME_API_TEMP_ROOT": str(tmp_path),
    })
    stream = StringIO()
    startup = Startup(config, MappingProxyType({}), configure_logging("api", stream=stream))
    engine = create_api_engine(config.db)
    try:
        yield startup, stream, engine
    finally:
        engine.dispose()
