"""readout 계약 타입 라운드트립 — fixture가 정답지다.

`python -m unittest discover -s tests` 로 돈다. 외부 의존 없음.

라운드트립은 **바이트가 아니라 파싱 결과**를 비교한다. fixture 5개의 들여쓰기·배열 줄바꿈이
파일마다 달라서 텍스트 동일성은 계약 정합성과 무관한 것을 잡는다. 여기서 보는 것은
「파싱 → 객체 → 직렬화」가 원본과 같은 dict인가 — 필드 누락·추가·이름 변화가 전부 여기서 걸린다.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from daesingo.readout import contracts, registry  # noqa: E402
from daesingo.readout.fixtures import fixture_paths, load_all, load_raw  # noqa: E402


class RoundTripTest(unittest.TestCase):
    def test_every_fixture_round_trips(self):
        paths = fixture_paths()
        self.assertEqual(len(paths), 5, "readout fixture는 5개다")
        for path in paths:
            with self.subTest(fixture=path.name):
                raw = load_raw(path)
                parsed = contracts.ReadoutFixture.from_dict(raw)
                self.assertEqual(parsed.to_dict(), raw)

    def test_object_counts(self):
        """v5 기준 객체 규모. 숫자가 바뀌면 Mock Pack이 움직인 것이고, 확인하고 고칠 일이다."""
        fixtures = load_all()
        runs = sum(len(f.readout_runs) for f in fixtures.values())
        plates = sum(len(f.plate_readouts) for f in fixtures.values())
        overlays = sum(len(f.overlay_time_readouts) for f in fixtures.values())
        self.assertEqual((runs, plates, overlays), (12, 5, 6))

    def test_unknown_key_is_rejected(self):
        """모르는 키를 조용히 버리지 않는다 — 버리면 라운드트립이 통과해 버린다."""
        raw = load_raw(fixture_paths()[0])
        raw["readout_runs"][0]["unexpected_field"] = 1
        with self.assertRaises(contracts.UnknownFieldError):
            contracts.ReadoutFixture.from_dict(raw)


class RegisteredValueTest(unittest.TestCase):
    """fixture가 등재값만 쓰는지 본다. 파싱은 관대하고 검사는 여기서 한다."""

    @classmethod
    def setUpClass(cls):
        cls.fixtures = load_all()

    def test_run_values(self):
        for scenario, fixture in self.fixtures.items():
            for run in fixture.readout_runs:
                with self.subTest(scenario=scenario, run=run.run_id):
                    self.assertIn(run.operation, registry.OPERATIONS)
                    self.assertIn(run.outcome, registry.OUTCOMES)
                    if run.failure is not None:
                        self.assertIn(run.failure.kind, registry.FAILURE_KINDS)
                        self.assertIn(run.failure.code, registry.FAILURE_CODES)

    def test_plate_values(self):
        for scenario, fixture in self.fixtures.items():
            for plate in fixture.plate_readouts:
                with self.subTest(scenario=scenario, readout=plate.readout_id):
                    self.assertIn(plate.observation.status, registry.OBSERVATION_STATUSES)
                    self.assertIn(plate.input_ref.source_profile, registry.SOURCE_PROFILES)
                    self.assertIn(plate.target_association.status, registry.ASSOCIATION_STATUSES)
                    if plate.abstain_reason is not None:
                        self.assertIn(plate.abstain_reason, registry.ABSTAIN_REASONS)

    def test_overlay_values(self):
        for scenario, fixture in self.fixtures.items():
            for overlay in fixture.overlay_time_readouts:
                with self.subTest(scenario=scenario, readout=overlay.readout_id):
                    self.assertIn(overlay.observation.status, registry.OBSERVATION_STATUSES)
                    self.assertIn(overlay.input_ref.source_profile, registry.SOURCE_PROFILES)
                    reason = overlay.observation.reason
                    if reason is not None:
                        self.assertIn(reason.code, registry.OVERLAY_REASON_CODES)


if __name__ == "__main__":
    unittest.main()
