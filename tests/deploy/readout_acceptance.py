"""Real CPU OCR acceptance, mounted into the production image (network none).

Font is mounted separately; no fixture/media/pytest is installed in the image.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from daesingo import readout
from daesingo.readout.contracts import InputRef
from daesingo.readout.paddle_provider import PaddleOcrProvider, RecordingFrameSource
from daesingo.recording import IncidentClipEncoding, LocalIncidentMaterializer, RecordingService
from daesingo.worker.readout_runtime import CACHE_ROOT, load_production_ocr_engine, quiet_ocr_startup


def generate(root, font):
    from PIL import Image, ImageDraw, ImageFont
    plate = ImageFont.truetype(str(font), 84)
    # Use a Latin font for the numeric timestamp; Korean glyphs belong to the plate.
    overlay = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
    for i in range(30):
        image = Image.new("RGB", (1280, 720), "#555555")
        draw = ImageDraw.Draw(image)
        draw.rectangle((300, 280, 980, 430), fill="white")
        draw.text((350, 300), "12가3456", font=plate, fill="black")
        draw.text((100, 600), f"2026-06-20 14:19:{56 + i // 10:02d}", font=overlay, fill="white")
        image.save(root / f"frame-{i:02d}.png")
    path = root / "synthetic.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-framerate", "10", "-i",
        str(root / "frame-%02d.png"), "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, check=True, timeout=30)
    return path


def cache_state():
    paths = [CACHE_ROOT / "models.json", *(CACHE_ROOT / "official_models").rglob("*")]
    return {str(p.relative_to(CACHE_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file()}


def main():
    assert os.getuid() == os.getgid() == 10001
    network = []
    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            network.append(event)
            raise RuntimeError("acceptance forbids network access")
    sys.addaudithook(audit)
    before = cache_state()
    with quiet_ocr_startup():
        engine = load_production_ocr_engine()
        with TemporaryDirectory(prefix="readout-acceptance-") as directory:
            root = Path(directory)
            source = generate(root, Path(sys.argv[1]))
            work = root / "work"
            work.mkdir()
            with RecordingService(incident_materializer=LocalIncidentMaterializer(
                    IncidentClipEncoding(720, "veryfast", 10), temp_root=work)) as recording:
                registered = recording.register_local_source(source)
                video, = [s for s in registered.media_streams if s.media_type == "VIDEO"]
                timeline = recording.create_relative_timeline(registered.source_asset.source_asset_ref)
                resolution = recording.resolve_span(dict(timeline_id=timeline.timeline_id, revision=timeline.revision),
                    dict(start_sec=0., end_sec=3.), media_stream_ref=video.media_stream_ref)
                clip = recording.build_incident_clip(resolution)
                provider = PaddleOcrProvider(RecordingFrameSource(recording), engine=engine)
                request = readout.ReadRequest(case_id="acceptance", candidate_id="candidate", input_ref=InputRef(
                    incident_clip_ref=clip.incident_clip_ref, source_profile="readout-native",
                    provenance="SOURCE_DERIVED_INCIDENT_CLIP"))
                plate_run, plate = readout.read_plate(request, provider=provider)
                time_run, overlay = readout.read_overlay_time(request, provider=provider)
                assert plate_run.outcome == time_run.outcome == "SUCCEEDED", (
                    plate_run.outcome, time_run.outcome,
                    plate_run.failure.code if plate_run.failure else None,
                    time_run.failure.code if time_run.failure else None)
                assert plate.observation.status == "OK" and plate.observation.value == "12가3456", (
                    plate.observation.status, plate.observation.value)
                assert overlay.observation.status == "OK", overlay.observation.status
                assert all(s.parsed_at.endswith("+09:00") for s in overlay.samples if s.parsed_at)
                assert overlay.validation.monotonic_ok and overlay.validation.duration_match_ok
            assert not list(work.iterdir())
    assert not network, "network attempt occurred even if provider swallowed its failure"
    assert before == cache_state()
    return {"uid": 10001, "plate": "PASS", "overlay": "PASS", "network_attempts": 0, "cache_unchanged": True}


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except BaseException:
        print("readout acceptance: FAIL", file=sys.stderr)
        raise SystemExit(1)
