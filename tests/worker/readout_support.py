"""Explicit offline OCR at the provider boundary; no fixture or network fallback."""
from daesingo.readout import providers as p


class OfflineOcr(p.OcrProvider):
    label = "offline-test"

    def __init__(self, mode="success", observe=lambda: None):
        self.mode, self.observe, self.calls = mode, observe, []

    def _call(self, kind, ref):
        self.observe()
        self.calls.append((kind, ref.incident_clip_ref))
        if self.mode == "failed":
            raise p.ProviderError("INFRA", "READOUT_PROVIDER_TIMEOUT", "private provider detail")

    def read_plate(self, input_ref, target_hint):
        self._call("PLATE_READ", input_ref)
        return p.PlateReading(p.AssociationReading("ASSOCIATED", False, None, "offline"), [
            p.PlateFrameReading(f"frame-{i}", [1, 1, 80, 30],
                "12가3456", .1 if self.mode == "abstain" else .99, {"plate_px_height": 30})
            for i in range(3)])

    def read_overlay_time(self, input_ref):
        self._call("OVERLAY_TIME_READ", input_ref)
        if self.mode == "not_present": return p.OverlayReading(p.NOT_PRESENT)
        if self.mode == "undetermined": return p.OverlayReading(p.UNDETERMINED)
        if self.mode == "ocr_failed":
            return p.OverlayReading(p.PRESENT, [p.OverlaySampleReading("frame-0", 0, "unreadable")])
        return p.OverlayReading(p.PRESENT, [
            p.OverlaySampleReading("frame-0", 0, "2026-06-20 14:19:56"),
            p.OverlaySampleReading("frame-1", 1, "2026-06-20 14:19:57")])


class ObservedUsage:
    def __init__(self, events=None, fail=None):
        self.events = events if events is not None else []
        self.fail, self.begins, self.finishes = fail, [], []

    def begin(self, operation, provider_label, pricing_context, **kw):
        self.events.append("begin")
        if self.fail == "begin":
            from daesingo.common.usage.port import UsagePersistenceError
            raise UsagePersistenceError()
        self.begins.append(dict(operation=operation, provider_label=provider_label,
            pricing_context=pricing_context, **kw))
        return "usage-test"

    def finish(self, identity, **kw):
        self.events.append("finish")
        if self.fail == "finish":
            from daesingo.common.usage.port import UsagePersistenceError
            raise UsagePersistenceError()
        self.finishes.append((identity, kw))

    def finalize(self, *args, **kw):
        raise AssertionError("T1 reconciliation owns final Run linkage")
