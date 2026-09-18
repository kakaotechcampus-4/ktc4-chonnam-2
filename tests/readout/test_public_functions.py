"""공개 함수 2개 — 실제로 호출되고, 계약 형식으로 반환하고, 네 상태를 구분하는가.

라운드트립 테스트가 「fixture가 계약과 맞는가」였다면 여기는 **내 코드가 만든 출력이 계약과
맞는가**다. 그래서 모든 산출물을 `to_dict() → from_dict()`로 한 번 되돌려 보고, 같은
`invariants.check_all`을 생성된 출력에도 건다 — fixture에만 걸고 구현에는 안 걸면 검사한 것이
아니다.

`python -m pytest tests/readout` 로 돈다. 외부 의존 없음.
"""
import unittest

from daesingo.readout import api, invariants, providers, registry
from daesingo.readout.contracts import (
    InputRef,
    OverlayTimeReadout,
    PlateReadout,
    ReadoutFixture,
    ReadoutRun,
)

HINT = api.TargetHint(track_ref="track_test")


def request_for(clip, profile="readout-native", case="case_test", candidate="candidate_test"):
    return api.ReadRequest(
        case_id=case,
        candidate_id=candidate,
        input_ref=InputRef(
            incident_clip_ref=clip,
            source_profile=profile,
            provenance="SOURCE_DERIVED_INCIDENT_CLIP",
        ),
    )


def fresh_provider():
    """대본 진행이 처음인 Stub. `default_provider()`는 한 인스턴스를 돌려쓰므로
    테스트가 그것을 쓰면 실행 순서에 따라 서로 다른 대본을 보게 된다."""
    return providers.FixtureOcrProvider()


def round_trip(obj):
    """계약 타입으로 한 바퀴 돌려 온 것. 필드 이름·구조가 어긋나면 여기서 죽는다."""
    return type(obj).from_dict(obj.to_dict())


class PublicFunctionsExistTest(unittest.TestCase):
    """체크리스트 Core Flow — 「공개 함수 2개가 존재하고 호출 가능하다」."""

    def test_both_functions_are_callable_from_the_package(self):
        from daesingo import readout
        self.assertTrue(callable(readout.read_plate))
        self.assertTrue(callable(readout.read_overlay_time))

    def test_one_call_makes_exactly_one_run(self):
        """1 호출 = `ReadoutRun` 1건. `case`의 「1 execution : 1 run」이 여기에 기댄다."""
        provider = fresh_provider()
        run_ids = set()
        for _ in range(3):
            run, _ = api.read_plate(request_for("clip_h001"), HINT, provider=provider)
            run_ids.add(run.run_id)
        for _ in range(3):
            run, _ = api.read_overlay_time(request_for("clip_h001"), provider=provider)
            run_ids.add(run.run_id)
        self.assertEqual(len(run_ids), 6, "run_id는 1회성 식별자이며 재사용하지 않는다")


class HappyPathTest(unittest.TestCase):
    """`scenario_happy_001` 입력으로 두 함수가 실제로 돌고 계약 형식을 반환한다."""

    @classmethod
    def setUpClass(cls):
        provider = fresh_provider()
        cls.plate_run, cls.plate = api.read_plate(
            request_for("clip_h001"), HINT, provider=provider)
        cls.overlay_run, cls.overlay = api.read_overlay_time(
            request_for("clip_h001"), provider=provider)

    def test_returns_run_and_result(self):
        self.assertIsInstance(self.plate_run, ReadoutRun)
        self.assertIsInstance(self.plate, PlateReadout)
        self.assertIsInstance(self.overlay_run, ReadoutRun)
        self.assertIsInstance(self.overlay, OverlayTimeReadout)
        self.assertEqual(self.plate_run.operation, "PLATE_READ")
        self.assertEqual(self.overlay_run.operation, "OVERLAY_TIME_READ")
        self.assertEqual(self.plate_run.outcome, "SUCCEEDED")
        self.assertEqual(self.overlay_run.outcome, "SUCCEEDED")

    def test_output_is_contract_shaped(self):
        for obj in (self.plate_run, self.plate, self.overlay_run, self.overlay):
            with self.subTest(obj=type(obj).__name__):
                self.assertEqual(round_trip(obj).to_dict(), obj.to_dict())

    def test_plate_observation(self):
        obs = self.plate.observation
        self.assertEqual(obs.value, "12가3456")
        self.assertEqual(obs.status, "OK")
        self.assertEqual(obs.source, {"kind": "readout.plate_ocr"})
        self.assertEqual(obs.support_refs, [], "근거 ref는 best_frame·frame_results가 갖는다")
        self.assertFalse(self.plate.abstained)
        self.assertIsNone(self.plate.abstain_reason)

    def test_overlay_observation(self):
        obs = self.overlay.observation
        self.assertEqual(obs.value, "2026-08-24T18:05:12+09:00")
        self.assertEqual(obs.status, "OK")
        self.assertIsNone(obs.reason, "OK 갈래는 reason 키 자체가 없다")
        self.assertEqual(
            self.overlay.validation.to_dict(),
            {"format_ok": True, "monotonic_ok": True,
             "duration_match_ok": True, "sample_count": 3},
        )

    def test_run_ref_is_the_run_that_made_it(self):
        for result, run in ((self.plate, self.plate_run), (self.overlay, self.overlay_run)):
            with self.subTest(result=type(result).__name__):
                self.assertEqual(result.run_ref.ref, run.run_id)
                self.assertEqual(result.run_ref.kind, "readout_run")
                self.assertEqual(result.observation.produced_by.run_ref.ref, run.run_id)
                self.assertEqual(result.observation.produced_by.module, "readout")

    def test_frame_refs_are_preserved_unparsed(self):
        """§3 — readout은 `frame_ref`를 파싱하지 않고 받은 그대로 보존한다."""
        given = {"fr_h001_plate1", "fr_h001_plate2"}
        self.assertEqual({f.frame_ref for f in self.plate.frame_results}, given)
        self.assertIn(self.plate.best_frame.frame_ref, given)

    def test_registered_values_only(self):
        self.assertIn(self.plate_run.operation, registry.OPERATIONS)
        self.assertIn(self.plate.observation.status, registry.OBSERVATION_STATUSES)
        self.assertIn(self.plate.target_association.status, registry.ASSOCIATION_STATUSES)
        self.assertIn(self.plate.input_ref.source_profile, registry.SOURCE_PROFILES)


class AbstainTest(unittest.TestCase):
    """`scenario_plate_reread_001` — 보류가 확정값을 만들지 않고, 재판독이 앞 판독을 건드리지 않는다."""

    @classmethod
    def setUpClass(cls):
        provider = fresh_provider()
        cls.first_run, cls.first = api.read_plate(
            request_for("clip_p001"), HINT, provider=provider)
        cls.before = cls.first.to_dict()
        cls.second_run, cls.second = api.read_plate(
            request_for("clip_p001", "readout-native-hires"), HINT, provider=provider)

    def test_abstain_makes_no_confirmed_value(self):
        """Merge 중단 기준 — abstained=true인데 확정 번호판 값이 함께 나옴."""
        self.assertTrue(self.first.abstained)
        self.assertEqual(self.first.observation.status, "NEEDS_REVIEW")
        self.assertIn("?", self.first.observation.value)
        self.assertEqual(self.first.observation.value, "17나28??")

    def test_abstain_reason_is_single_and_registered(self):
        self.assertEqual(self.first.abstain_reason, "FRAME_DISAGREEMENT")
        self.assertIn(self.first.abstain_reason, registry.ABSTAIN_REASONS)
        self.assertIsNone(
            self.first.observation.reason,
            "abstain_reason이 authoritative다 — observation.reason을 중복 채우지 않는다",
        )

    def test_disagree_positions_match_the_question_marks(self):
        self.assertEqual(self.first.consensus.disagree_positions, [5, 6])
        self.assertEqual(self.first.consensus.text, self.first.observation.value)

    def test_association_wins_over_frame_consensus(self):
        """우선순위 `association > frame consensus` — 같은 프레임 불일치라도 사유가 달라진다."""
        class AmbiguousProvider(providers.OcrProvider):
            def read_plate(self, input_ref, target_hint):
                reading = providers.FixtureOcrProvider().read_plate(input_ref, target_hint)
                reading.association.status = "AMBIGUOUS"
                return reading

        _, plate = api.read_plate(request_for("clip_p001"), HINT, provider=AmbiguousProvider())
        self.assertEqual(plate.abstain_reason, "TARGET_AMBIGUOUS")

    def test_length_mismatch_still_abstains(self):
        """자리를 맞출 수 없는 불일치도 보류다 — 「모름」으로 접지 않는다.

        접으면 `abstained=false`가 되어 `eval`의 Wrong Accept 분모(「abstained=false인 전체」)에
        들어가고, `evidence`는 「프레임이 어긋나 보류」 대신 「값을 알 수 없음」을 보게 된다.
        """
        class RaggedProvider(providers.OcrProvider):
            def read_plate(self, input_ref, target_hint):
                return providers.PlateReading(
                    association=providers.AssociationReading(
                        "ASSOCIATED", False, None, "FALLBACK_ONLY", []),
                    frames=[
                        providers.PlateFrameReading("fr_a", [0, 0, 1, 1], "17나2804", 0.9,
                                                    {"plate_px_height": 40}),
                        providers.PlateFrameReading("fr_b", [0, 0, 1, 1], "7나2804", 0.85, {}),
                    ],
                )

        _, plate = api.read_plate(request_for("clip_h001"), provider=RaggedProvider())
        self.assertTrue(plate.abstained)
        self.assertEqual(plate.abstain_reason, "FRAME_DISAGREEMENT")
        self.assertEqual(plate.observation.status, "NEEDS_REVIEW")
        self.assertIsNone(plate.observation.value, "합의 문자열을 지어내지 않는다")
        self.assertEqual(plate.consensus.disagree_positions, [])

    def test_nothing_readable_is_unknown_not_abstain(self):
        """읽어낸 글자가 아예 없으면 보류할 관찰값 자체가 없다."""
        class BlankProvider(providers.OcrProvider):
            def read_plate(self, input_ref, target_hint):
                return providers.PlateReading(
                    association=providers.AssociationReading(
                        "ASSOCIATED", False, None, "FALLBACK_ONLY", []),
                    frames=[providers.PlateFrameReading("fr_a", [0, 0, 1, 1], None, None, {})],
                )

        _, plate = api.read_plate(request_for("clip_h001"), provider=BlankProvider())
        self.assertFalse(plate.abstained)
        self.assertIsNone(plate.abstain_reason)
        self.assertEqual(plate.observation.status, "UNKNOWN")
        self.assertIsNone(plate.observation.value)

    def test_reread_is_a_new_run_and_a_new_result(self):
        """재판독은 기존 판독을 mutate하지 않는다 — 새 run + 새 결과 객체다."""
        self.assertEqual(self.first.to_dict(), self.before, "앞 판독이 그대로 남아 있다")
        self.assertNotEqual(self.first_run.run_id, self.second_run.run_id)
        self.assertNotEqual(self.first.readout_id, self.second.readout_id)
        self.assertFalse(self.second.abstained)
        self.assertEqual(self.second.observation.value, "17나2867")
        self.assertEqual(self.second.observation.status, "OK")

    def test_reread_issues_new_crop_refs(self):
        """crop identity는 재사용하지 않는다 — 같은 프레임을 다시 떠도 새 crop이다."""
        first_crops = {f.crop_ref for f in self.first.frame_results}
        second_crops = {f.crop_ref for f in self.second.frame_results}
        shared_frames = ({f.frame_ref for f in self.first.frame_results}
                         & {f.frame_ref for f in self.second.frame_results})
        self.assertTrue(shared_frames, "같은 프레임을 다시 읽은 재판독이어야 의미가 있는 검사다")
        self.assertEqual(first_crops & second_crops, set())

    def test_best_frame_and_frame_results_share_one_crop(self):
        best = self.first.best_frame
        matching = [f for f in self.first.frame_results if f.frame_ref == best.frame_ref]
        self.assertEqual([f.crop_ref for f in matching], [best.crop_ref])


class TotalFailureTest(unittest.TestCase):
    """`scenario_infra_failure_001` — 완전 실패는 결과 객체를 만들지 않는다."""

    def test_failed_run_has_no_result_object(self):
        """Merge 중단 기준 — 완전 실패인데 결과 객체가 생성됨."""
        run, plate = api.read_plate(request_for("clip_x001"), HINT,
                                    provider=fresh_provider())
        self.assertIsNone(plate, "실패 사실·원인은 ReadoutRun만 갖는다")
        self.assertEqual(run.outcome, "FAILED")
        self.assertEqual(run.failure.kind, "INFRA")
        self.assertEqual(run.failure.code, "READOUT_PROVIDER_TIMEOUT")
        self.assertIn(run.failure.kind, registry.FAILURE_KINDS)
        self.assertIn(run.failure.code, registry.FAILURE_CODES)
        self.assertIsNotNone(run.ended_at, "실행이 끝난 시각은 남는다")

    def test_run_is_still_produced(self):
        """결과가 없어도 run은 남는다 — 1 호출 = 1 run이 실패에서도 성립한다."""
        run, _ = api.read_plate(request_for("clip_x001"), HINT,
                                provider=fresh_provider())
        self.assertEqual(round_trip(run).to_dict(), run.to_dict())


class OverlayBranchTest(unittest.TestCase):
    """네 갈래가 서로 다른 값으로 나온다 — 합치면 Merge 중단 기준 위반이다."""

    @classmethod
    def setUpClass(cls):
        provider = fresh_provider()
        cls.ok = api.read_overlay_time(request_for("clip_h001"), provider=provider).overlay
        cls.absent = api.read_overlay_time(request_for("clip_u001"), provider=provider).overlay
        # clip_x001의 overlay 대본은 2회분이다 — 첫 호출이 「있는지 못 봄」, 다음이 「못 알아봄」.
        cls.undetermined = api.read_overlay_time(
            request_for("clip_x001"), provider=provider).overlay
        cls.ocr_failed = api.read_overlay_time(
            request_for("clip_x001"), provider=provider).overlay

    def _branch(self, overlay):
        reason = overlay.observation.reason
        return overlay.observation.status, reason.code if reason else None

    def test_four_branches_are_four_distinct_values(self):
        branches = [self._branch(o) for o in
                    (self.ok, self.absent, self.undetermined, self.ocr_failed)]
        self.assertEqual(len(set(branches)), 4)
        self.assertEqual(branches, [
            ("OK", None),
            ("NOT_APPLICABLE", "readout.overlay.not_present"),
            ("UNKNOWN", "readout.overlay.presence_undetermined"),
            ("UNKNOWN", "readout.overlay.ocr_failed"),
        ])

    def test_absent_is_not_a_failure(self):
        """「화면에 시각이 안 찍힌 영상」은 정상 관찰 결과다."""
        run, overlay = api.read_overlay_time(request_for("clip_u001"),
                                             provider=fresh_provider())
        self.assertEqual(run.outcome, "SUCCEEDED")
        self.assertIsNone(run.failure)
        self.assertIsNotNone(overlay)

    def test_null_value_statuses_carry_no_value(self):
        for overlay in (self.absent, self.undetermined, self.ocr_failed):
            with self.subTest(status=self._branch(overlay)):
                self.assertIsNone(overlay.observation.value)

    def test_not_checked_is_null_not_false(self):
        """「검증 안 함」은 `false`가 아니라 `null`이다."""
        for overlay in (self.absent, self.undetermined):
            with self.subTest(readout=overlay.readout_id):
                self.assertIsNone(overlay.validation.format_ok)
                self.assertIsNone(overlay.validation.monotonic_ok)
                self.assertIsNone(overlay.validation.duration_match_ok)
        self.assertIs(self.ocr_failed.validation.format_ok, False,
                      "읽었는데 형식이 아니었던 것은 검증한 결과다")

    def test_samples_are_kept_only_where_there_was_something_to_read(self):
        self.assertEqual(self.absent.validation.sample_count, 0)
        self.assertEqual(self.undetermined.validation.sample_count, 0)
        self.assertEqual(self.ocr_failed.validation.sample_count, len(self.ocr_failed.samples))
        self.assertEqual(self.ocr_failed.validation.sample_count, 3)
        self.assertTrue(all(s.parsed_at is None for s in self.ocr_failed.samples))

    def test_reason_codes_are_registered(self):
        for overlay in (self.absent, self.undetermined, self.ocr_failed):
            with self.subTest(readout=overlay.readout_id):
                self.assertIn(overlay.observation.reason.code, registry.OVERLAY_REASON_CODES)

    def test_validation_failure_does_not_fail_the_run(self):
        """`OVERLAY_VALIDATION`은 run 실패가 아니다 — 시간이 역행해도 outcome은 내려가지 않는다."""
        class BackwardsProvider(providers.OcrProvider):
            def read_overlay_time(self, input_ref):
                return providers.OverlayReading(
                    presence=providers.PRESENT,
                    samples=[
                        providers.OverlaySampleReading("fr_a", 1.0, "2026-08-24 18:05:20"),
                        providers.OverlaySampleReading("fr_b", 2.0, "2026-08-24 18:05:10"),
                    ],
                )

        run, overlay = api.read_overlay_time(request_for("clip_h001"),
                                             provider=BackwardsProvider())
        self.assertEqual(run.outcome, "SUCCEEDED")
        self.assertIsNone(run.failure)
        self.assertIs(overlay.validation.monotonic_ok, False)
        self.assertIs(overlay.validation.duration_match_ok, False)


class TargetHintOptionalTest(unittest.TestCase):
    """`target_hint`는 optional이다 — 없어도 실행되고 association 결과는 남는다."""

    def test_runs_without_hint(self):
        run, plate = api.read_plate(request_for("clip_h001"), provider=fresh_provider())
        self.assertEqual(run.outcome, "SUCCEEDED")
        self.assertFalse(plate.target_association.target_hint_used)
        self.assertEqual(plate.target_association.association_method, "FALLBACK_ONLY")
        self.assertIn(plate.target_association.status, registry.ASSOCIATION_STATUSES)
        self.assertTrue(plate.target_association.evidence, "실제 association 근거가 남는다")

    def test_hint_use_is_not_taken_on_trust(self):
        """hint 없이 불렀는데 provider가 썼다고 하면 실패 run으로 닫는다."""
        class LyingProvider(providers.OcrProvider):
            def read_plate(self, input_ref, target_hint):
                reading = providers.FixtureOcrProvider().read_plate(input_ref, target_hint)
                reading.association.target_hint_used = True
                return reading

        run, plate = api.read_plate(request_for("clip_h001"), None, provider=LyingProvider())
        self.assertIsNone(plate)
        self.assertEqual(run.outcome, "FAILED")
        self.assertEqual(run.failure.kind, "INFRA")


class ProviderContractBreachTest(unittest.TestCase):
    """provider를 **부른 뒤에** 발견한 위반은 예외로 되돌리지 않는다.

    이미 실행이 일어났고 비용도 나갔다. 예외로 run을 날리면 worker가 `JobExecution.produced`와
    `UsageRecord` 발행 근거를 통째로 잃고, 「public 함수 호출 1회 = run 1건」도 깨진다.
    """

    def _breach(self, reading):
        class BreachingProvider(providers.OcrProvider):
            def read_overlay_time(self, input_ref):
                return reading

        return api.read_overlay_time(request_for("clip_h001"), provider=BreachingProvider())

    def _breach_plate(self, reading):
        class BreachingProvider(providers.OcrProvider):
            def read_plate(self, input_ref, target_hint):
                return reading

        return api.read_plate(request_for("clip_h001"), HINT, provider=BreachingProvider())

    def test_unknown_presence_becomes_a_failed_run(self):
        run, overlay = self._breach(providers.OverlayReading(presence="MAYBE"))
        self.assertIsNone(overlay)
        self.assertEqual(run.outcome, "FAILED")
        self.assertEqual(run.failure.kind, "INFRA")
        self.assertEqual(run.failure.code, "READOUT_PIPELINE_ERROR")
        self.assertIn(run.failure.code, registry.FAILURE_CODES)
        self.assertIsNotNone(run.ended_at, "언제 실행됐는지가 UsageRecord 발행 근거다")

    def test_samples_without_presence_becomes_a_failed_run(self):
        run, overlay = self._breach(providers.OverlayReading(
            presence=providers.NOT_PRESENT,
            samples=[providers.OverlaySampleReading("fr_a", 1.0, "2026-08-24 18:05:12")],
        ))
        self.assertIsNone(overlay)
        self.assertEqual(run.outcome, "FAILED")

    def test_the_run_is_still_contract_shaped(self):
        run, _ = self._breach(providers.OverlayReading(presence="MAYBE"))
        self.assertEqual(round_trip(run).to_dict(), run.to_dict())

    def test_bad_tz_offset_becomes_a_failed_run(self):
        """`tz_offset`은 clip 메타데이터에서 오는 값이라 비어 있거나 ISO가 아닐 수 있다.

        그대로 이어 붙이면 시각이 아닌 문자열이 만들어지고, 파싱에서 `TypeError`/`ValueError`가
        **provider를 부른 뒤에** 튀어나온다 — run 없이 예외만 남으면 worker가 발행 근거를 잃는다.
        """
        def reading(tz):
            return providers.OverlayReading(
                presence=providers.PRESENT,
                tz_offset=tz,
                samples=[providers.OverlaySampleReading("fr_a", 0.0, "2026-08-24 18:05:12")],
            )

        for tz in (None, "", "KST", "+0900"):
            with self.subTest(tz_offset=tz):
                run, overlay = self._breach(reading(tz))
                self.assertIsNone(overlay)
                self.assertEqual(run.outcome, "FAILED")
                self.assertEqual(run.failure.kind, "INFRA")
                self.assertEqual(run.failure.code, "READOUT_PIPELINE_ERROR")
                self.assertIsNotNone(run.ended_at)

    def test_iso_offsets_still_pass(self):
        for tz in ("+09:00", "Z"):
            with self.subTest(tz_offset=tz):
                run, overlay = self._breach(providers.OverlayReading(
                    presence=providers.PRESENT,
                    tz_offset=tz,
                    samples=[providers.OverlaySampleReading("fr_a", 0.0, "2026-08-24 18:05:12")],
                ))
                self.assertEqual(run.outcome, "SUCCEEDED")
                self.assertEqual(overlay.observation.value, f"2026-08-24T18:05:12{tz}")

    def test_unreal_tz_offset_becomes_a_failed_run(self):
        """표기는 맞는데 시각이 아닌 offset — 정규식만으로는 걸리지 않던 자리다.

        `+25:99`는 `±HH:MM` 패턴을 통과한다. 그대로 이어 붙이면 `fromisoformat`이 해석
        단계에서 죽고, 그때는 이미 provider를 부른 뒤라 예외로 되돌릴 수 없다.
        """
        for tz in ("+25:99", "+09:60", "+24:00", "-24:00"):
            with self.subTest(tz_offset=tz):
                run, overlay = self._breach(providers.OverlayReading(
                    presence=providers.PRESENT,
                    tz_offset=tz,
                    samples=[providers.OverlaySampleReading("fr_a", 0.0, "2026-08-24 18:05:12")],
                ))
                self.assertIsNone(overlay)
                self.assertEqual(run.outcome, "FAILED")
                self.assertEqual(run.failure.kind, "INFRA")
                self.assertEqual(run.failure.code, "READOUT_PIPELINE_ERROR")
                self.assertIsNotNone(run.ended_at)

    def test_unreadable_plate_response_becomes_a_failed_run(self):
        """plate도 overlay와 같아야 한다 — `ProviderError`만 잡으면 나머지가 그대로 튄다.

        `bbox_xywh`가 비어 오면 `list(...)`에서 `TypeError`가 난다. provider를 부른 **뒤**라
        예외로 되돌리면 run 없이 비용만 나간 상태가 되고 「호출 1회 = run 1건」이 깨진다.
        """
        broken = [
            providers.PlateReading(
                association=providers.AssociationReading(
                    status="OK", target_hint_used=True, track_ref="track_test",
                    association_method="HINT", evidence=[],
                ),
                frames=[providers.PlateFrameReading("fr_a", None, "12가3456", 0.9, {})],
            ),
            providers.PlateReading(
                association=providers.AssociationReading(
                    status="OK", target_hint_used=True, track_ref="track_test",
                    association_method="HINT", evidence=[("kind", "detail", "extra")],
                ),
                frames=[providers.PlateFrameReading("fr_a", [0, 0, 10, 10], "12가3456", 0.9, {})],
            ),
        ]
        for i, reading in enumerate(broken):
            with self.subTest(case=i):
                run, plate = self._breach_plate(reading)
                self.assertIsNone(plate)
                self.assertEqual(run.outcome, "FAILED")
                self.assertEqual(run.failure.kind, "INFRA")
                self.assertEqual(run.failure.code, "READOUT_PIPELINE_ERROR")
                self.assertIn(run.failure.code, registry.FAILURE_CODES)
                self.assertIsNotNone(run.ended_at, "언제 실행됐는지가 UsageRecord 발행 근거다")
                self.assertEqual(round_trip(run).to_dict(), run.to_dict())


class FailureIsRegisteredTest(unittest.TestCase):
    """`ReadoutRun.failure`에 실리는 값은 **우리가 발행하는 값**이다 — provider 말을 그대로 싣지 않는다.

    Merge 중단 기준 1 — 「미등재 `failure.kind`/`code` 사용」. readout이 이 계약의 Producer라
    방어가 여기 있어야 한다. 등재 조합이 아니면 `INFRA`/`READOUT_PIPELINE_ERROR`로 닫는다.
    """

    def _failing(self, kind, code):
        class Failing(providers.OcrProvider):
            def read_plate(self, input_ref, target_hint):
                raise providers.ProviderError(kind, code, "stub")

            def read_overlay_time(self, input_ref):
                raise providers.ProviderError(kind, code, "stub")

        return Failing()

    def test_registered_infra_failure_passes_through(self):
        run, _ = api.read_plate(request_for("clip_h001"), HINT,
                                provider=self._failing("INFRA", "READOUT_FRAME_ACCESS_FAILED"))
        self.assertEqual((run.failure.kind, run.failure.code),
                         ("INFRA", "READOUT_FRAME_ACCESS_FAILED"))

    def test_unregistered_values_are_closed_as_pipeline_error(self):
        run, plate = api.read_plate(request_for("clip_h001"), HINT,
                                    provider=self._failing("DISK_ON_FIRE", "NOT_A_CODE"))
        self.assertIsNone(plate)
        self.assertEqual(run.failure.kind, "INFRA")
        self.assertEqual(run.failure.code, "READOUT_PIPELINE_ERROR")
        self.assertIn(run.failure.kind, registry.FAILURE_KINDS)
        self.assertIn(run.failure.code, registry.FAILURE_CODES)

    def test_overlay_validation_never_closes_a_run(self):
        """`OVERLAY_VALIDATION`은 등재 kind지만 **값을 읽은 뒤의 검증 결과**라 run 실패가 아니다.

        provider가 그것을 error 채널로 올리는 것 자체가 파이프라인 오류다
        (failure-taxonomy.md 「kind와 outcome은 1:1이 아니다」).
        """
        run, overlay = api.read_overlay_time(
            request_for("clip_h001"),
            provider=self._failing("OVERLAY_VALIDATION", "READOUT_PIPELINE_ERROR"))
        self.assertIsNone(overlay)
        self.assertEqual(run.failure.kind, "INFRA")
        self.assertEqual(
            [str(v) for v in invariants.check_all(
                [ReadoutFixture("generated-failure", "readout", [run], [], [])])],
            [], "R2가 사후에 잡기 전에 api가 그 조합을 만들지 않는다")


class AbstainWithCompleteValueTest(unittest.TestCase):
    """보류 사유 4종 중 셋은 **온전한 문자열과 함께** 나온다 — 그것이 정상이다.

    계약 §5: 「OCR 문자열이 정확해 보여도 `target_association`이 `LOW_CONFIDENCE`,
    `AMBIGUOUS`, `FAILED`이면 `evidence`는 최종 번호판 확정을 보류할 수 있다.」 확정 여부는
    `status`가 나르고 `?` 마스킹은 프레임 불일치 표현 수단이다(§11-1 선택 C).

    fixture에 있는 abstain은 `FRAME_DISAGREEMENT` 하나뿐이라 이 경로는 fixture로는 안 밟힌다.
    """

    def _provider(self, status, confidence, px_height):
        class Unanimous(providers.OcrProvider):
            def read_plate(self, input_ref, target_hint):
                quality = {"plate_px_height": px_height, "sharpness": 0.9}
                return providers.PlateReading(
                    association=providers.AssociationReading(
                        status, False, None, "FALLBACK_ONLY", []),
                    frames=[
                        providers.PlateFrameReading("fr_a", [0, 0, 10, 40], "17나2867",
                                                    confidence, quality),
                        providers.PlateFrameReading("fr_b", [0, 0, 10, 40], "17나2867",
                                                    confidence, quality),
                    ],
                )

        return Unanimous()

    def _read(self, status="ASSOCIATED", confidence=0.9, px_height=40):
        return api.read_plate(request_for("clip_h001"),
                              provider=self._provider(status, confidence, px_height))

    def test_low_confidence_keeps_the_observed_value(self):
        run, plate = self._read(confidence=0.30)
        self.assertTrue(plate.abstained)
        self.assertEqual(plate.abstain_reason, "OCR_LOW_CONFIDENCE")
        self.assertEqual(plate.observation.status, "NEEDS_REVIEW")
        self.assertEqual(plate.observation.value, "17나2867",
                         "보류했다고 관찰값을 지우지 않는다 — evidence가 그것을 본다")
        self.assertEqual(plate.consensus.disagree_positions, [])

    def test_low_resolution_and_ambiguous_target_do_the_same(self):
        _, low_res = self._read(px_height=10)
        _, ambiguous = self._read(status="AMBIGUOUS")
        self.assertEqual(low_res.abstain_reason, "LOW_RESOLUTION")
        self.assertEqual(ambiguous.abstain_reason, "TARGET_AMBIGUOUS")
        for plate in (low_res, ambiguous):
            self.assertEqual(plate.observation.value, "17나2867")
            self.assertEqual(plate.observation.status, "NEEDS_REVIEW")

    def test_generated_output_holds_the_invariants(self):
        """구현이 만든 것을 구현의 검사기에 그대로 건다 — 둘이 어긋나면 여기서 죽는다."""
        cases = [self._read(confidence=0.30), self._read(px_height=10),
                 self._read(status="AMBIGUOUS")]
        generated = ReadoutFixture(
            "generated-abstain", "readout",
            [run for run, _ in cases], [plate for _, plate in cases], [])
        self.assertEqual([str(v) for v in invariants.check_all([generated])], [])

    def test_frame_disagreement_still_requires_masking(self):
        """좁힌 뒤에도 합의 실패 갈래는 그대로 잡힌다."""
        _, plate = api.read_plate(request_for("clip_p001"), HINT, provider=fresh_provider())
        self.assertEqual(plate.abstain_reason, "FRAME_DISAGREEMENT")
        self.assertIn("?", plate.observation.value)
        plate.observation.value = "17나2867"      # 마스킹을 지운다
        plate.consensus.text = "17나2867"
        plate.consensus.disagree_positions = []
        violations = invariants.check_plate(
            ReadoutFixture("broken", "readout", [], [plate], []))
        self.assertIn("R11", sorted({v.rule for v in violations}))


class CropIdentityTest(unittest.TestCase):
    """crop identity는 `(frame_ref, bbox, source_profile)`이다 — frame_ref 하나가 아니다."""

    def _provider_with(self, frames):
        class Regions(providers.OcrProvider):
            def read_plate(self, input_ref, target_hint):
                return providers.PlateReading(
                    association=providers.AssociationReading(
                        "ASSOCIATED", False, None, "FALLBACK_ONLY", []),
                    frames=frames,
                )

        return Regions()

    def test_two_regions_in_one_frame_get_two_crops(self):
        """같은 프레임에서 영역을 둘 떠서 읽으면 서로 다른 crop이다.

        합쳐 버리면 한 `crop_ref`가 서로 다른 픽셀을 가리키게 되고, `eval`이 run을 가로질러
        `crop_ref`로 「입력이 같았다」를 판정할 수 없게 된다.
        """
        _, plate = api.read_plate(request_for("clip_h001"), provider=self._provider_with([
            providers.PlateFrameReading("fr_a", [0, 0, 10, 10], "12가3456", 0.9,
                                        {"plate_px_height": 40}),
            providers.PlateFrameReading("fr_a", [500, 300, 10, 10], "99허9999", 0.8, {}),
        ]))
        crops = [f.crop_ref for f in plate.frame_results]
        self.assertEqual(len(set(crops)), 2, "bbox가 다르면 다른 crop이다")

    def test_same_frame_and_bbox_share_one_crop(self):
        """같은 프레임의 같은 영역이면 같은 crop이다 — best_frame이 그것을 나눠 쓴다."""
        _, plate = api.read_plate(request_for("clip_h001"), provider=self._provider_with([
            providers.PlateFrameReading("fr_a", [0, 0, 10, 10], "12가3456", 0.9,
                                        {"plate_px_height": 40}),
            providers.PlateFrameReading("fr_a", [0, 0, 10, 10], "12가3456", 0.7, {}),
        ]))
        crops = {f.crop_ref for f in plate.frame_results}
        self.assertEqual(len(crops), 1)
        self.assertIn(plate.best_frame.crop_ref, crops)

    def test_best_frame_crop_follows_the_chosen_region(self):
        """두 영역 중 고른 쪽의 crop이 `best_frame`에 붙는다."""
        _, plate = api.read_plate(request_for("clip_h001"), provider=self._provider_with([
            providers.PlateFrameReading("fr_a", [0, 0, 10, 10], "12가3456", 0.4, {}),
            providers.PlateFrameReading("fr_a", [500, 300, 10, 10], "99허9999", 0.95,
                                        {"plate_px_height": 40}),
        ]))
        chosen = [f for f in plate.frame_results if f.confidence == 0.95]
        self.assertEqual(plate.best_frame.crop_ref, chosen[0].crop_ref)
        self.assertEqual(plate.best_frame.quality, {"plate_px_height": 40})


class InputRefIsolationTest(unittest.TestCase):
    """결과 객체는 자기 `input_ref`를 갖는다 — request를 뒤에 고쳐도 흔들리지 않는다."""

    def test_mutating_the_request_does_not_rewrite_a_finished_result(self):
        """재판독은 같은 request의 profile만 바꿔 다시 부르는 모양이 자연스럽다."""
        provider = fresh_provider()
        request = request_for("clip_p001")
        _, first = api.read_plate(request, HINT, provider=provider)
        snapshot = first.to_dict()

        request.input_ref.source_profile = "readout-native-hires"
        _, second = api.read_plate(request, HINT, provider=provider)

        self.assertEqual(first.to_dict(), snapshot, "앞 판독이 그대로 남아 있다")
        self.assertEqual(first.input_ref.source_profile, "readout-native")
        self.assertEqual(second.input_ref.source_profile, "readout-native-hires")

    def test_two_functions_sharing_one_request_do_not_share_one_input_ref(self):
        provider = fresh_provider()
        request = request_for("clip_h001")
        _, plate = api.read_plate(request, HINT, provider=provider)
        _, overlay = api.read_overlay_time(request, provider=provider)
        self.assertIsNot(plate.input_ref, overlay.input_ref)
        self.assertIsNot(plate.input_ref, request.input_ref)
        self.assertEqual(plate.input_ref.to_dict(), overlay.input_ref.to_dict())


class DefaultProviderTest(unittest.TestCase):
    """`provider=`를 넘기지 않는 호출자도 대본 진행을 본다."""

    def setUp(self):
        providers.reset_default_provider()

    def tearDown(self):
        providers.reset_default_provider()

    def test_script_advances_across_calls(self):
        """`clip_x001`의 overlay 두 번째 갈래(`ocr_failed`)는 증빙 JSON 3건 중 하나다."""
        first = api.read_overlay_time(request_for("clip_x001")).overlay
        second = api.read_overlay_time(request_for("clip_x001")).overlay
        self.assertEqual(first.observation.reason.code,
                         "readout.overlay.presence_undetermined")
        self.assertEqual(second.observation.reason.code, "readout.overlay.ocr_failed")

    def test_one_instance_is_reused(self):
        self.assertIs(providers.default_provider(), providers.default_provider())


class InputContractTest(unittest.TestCase):
    """입력도 계약 형식으로 받는다. 실행 전에 걸러지므로 run이 만들어지지 않는다."""

    def test_incident_clip_ref_is_required(self):
        with self.assertRaises(ValueError):
            api.read_plate(request_for(""), HINT, provider=fresh_provider())

    def test_unregistered_source_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            api.read_plate(request_for("clip_h001", "readout-experimental"), HINT,
                           provider=fresh_provider())

    def test_derived_provenance_is_required(self):
        """사후 Timestamp가 삽입된 영상을 근거로 삼는 경로를 값 층위에서 막는다."""
        request = api.ReadRequest(
            case_id="case_test", candidate_id="candidate_test",
            input_ref=InputRef("clip_h001", "readout-native", "REPORT_VIDEO"),
        )
        with self.assertRaises(ValueError):
            api.read_overlay_time(request, provider=fresh_provider())


class GeneratedOutputHoldsInvariantsTest(unittest.TestCase):
    """구현이 만든 출력에 불변조건 18개를 그대로 건다."""

    def test_no_violation(self):
        provider = fresh_provider()
        calls = [
            ("clip_h001", "readout-native"),
            ("clip_p001", "readout-native"),
            ("clip_p001", "readout-native-hires"),
            ("clip_u001", "readout-native"),
            ("clip_r001", "readout-native"),
            ("clip_x001", "readout-native"),
        ]
        runs, plates, overlays = [], [], []
        for clip, profile in calls:
            run, plate = api.read_plate(request_for(clip, profile), HINT, provider=provider)
            runs.append(run)
            if plate is not None:
                plates.append(plate)
        for clip, profile in calls + [("clip_x001", "readout-native")]:
            run, overlay = api.read_overlay_time(request_for(clip, profile), provider=provider)
            runs.append(run)
            if overlay is not None:
                overlays.append(overlay)

        self.assertTrue(plates and overlays)
        generated = ReadoutFixture("generated", "readout", runs, plates, overlays)
        violations = invariants.check_all([generated])
        self.assertEqual([str(v) for v in violations], [])


if __name__ == "__main__":
    unittest.main()
