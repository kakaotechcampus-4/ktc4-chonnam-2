"""Python 패키지 실행 기반에 대한 최소 smoke test."""

import unittest

from daesingo import __version__
from daesingo import common, recording


class PackageSmokeTest(unittest.TestCase):
    def test_package_imports(self) -> None:
        self.assertEqual(__version__, "0.1.0")
        self.assertEqual(common.__name__, "daesingo.common")
        self.assertEqual(recording.__name__, "daesingo.recording")


if __name__ == "__main__":
    unittest.main()
