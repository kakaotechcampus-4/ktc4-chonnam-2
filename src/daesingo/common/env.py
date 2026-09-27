"""`.env` 파일 로더. 설정의 유일한 출처는 이 파일이며 shell 환경변수는 쓰지 않는다."""

import os


def load_env_file(path: str | None = None) -> dict[str, str]:
    """`.env` 의 ``KEY=VALUE`` 를 dict 로 읽는다. 파일이 없으면 빈 dict.

    os.environ 을 건드리지 않는다 — 값은 이 파일에서만 온다. 주석(``#``)과 빈 줄,
    ``=`` 가 없는 줄은 건너뛰고, 값 양끝의 따옴표는 제거한다.
    """
    if path is None:
        path = os.path.join(os.getcwd(), ".env")
    values: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as stream:
            for raw in stream:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip().strip('"').strip("'")
    except FileNotFoundError:
        return {}
    return values
