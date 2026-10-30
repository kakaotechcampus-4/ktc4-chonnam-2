"""Real deployed-image acceptance. No pytest, provider, DB or private-media output.

Run with old tools for RED, with the pinned runtime for GREEN. MP4 generation uses
ordinary 30fps/default muxer timescale, never PR #467's 1/10-tick fixture.
"""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from daesingo.recording import (
    AnalysisProfile, IncidentClipEncoding, LocalAnalysisMaterializer,
    LocalIncidentMaterializer, RecordingService,
)
from daesingo.recording.exports import LocalExportMaterializer, PostStamp


def generate(path):
    codec = "mpeg4" if path.suffix == ".avi" else "libx264"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "testsrc2=s=320x240:r=30:d=2", "-c:v", codec, "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True, timeout=30)


def fingerprint(path):
    with path.open("rb") as stream:
        return path.stat().st_size, path.stat().st_mtime_ns, hashlib.file_digest(stream, "sha256").digest()


def exercise(paths, root, *, synthetic=True):
    before = [fingerprint(path) for path in paths]
    work = root / "materialization"
    work.mkdir()
    engine = LocalAnalysisMaterializer({"smoke": AnalysisProfile(48, "veryfast", 23)}, temp_root=work)
    with RecordingService(analysis_materializer=engine,
            incident_materializer=LocalIncidentMaterializer(IncidentClipEncoding(48, "veryfast", 23), temp_root=work)) as service:
        registered = [service.register_local_source(path) for path in paths]
        rows = []
        for i, result in enumerate(registered):
            video = next(s for s in result.media_streams if s.media_type == "VIDEO")
            rows.append(dict(source_asset_ref=result.source_asset.source_asset_ref,
                media_stream_ref=video.media_stream_ref,
                timeline_start_sec=float(i), timeline_end_sec=float(i + 1)))
        if len(rows) == 1:
            timeline = service.create_relative_timeline(registered[0].source_asset.source_asset_ref)
        else:
            timeline = service.create_relative_timeline_from_placements(rows)
        ref = dict(timeline_id=timeline.timeline_id, revision=timeline.revision)
        resolution = service.resolve_span(ref, dict(start_sec=0.0, end_sec=float(len(rows))),
            media_stream_refs=[r["media_stream_ref"] for r in rows])
        assert resolution.status == "COMPLETE" and len(resolution.spans) == len(rows)
        analysis = service.prepare_analysis_source_from_resolution(resolution, "smoke")
        if synthetic:
            assert analysis.duration_sec == float(len(rows))
            assert analysis.timeline_range == resolution.requested_range
        with service.open_analysis_source(analysis.analysis_source_ref).stream as stream:
            content = stream.read()
        assert len(content) == analysis.byte_size > 0
        output = root / "analysis.mp4"
        output.write_bytes(content)
        raw = engine._probe(output)
        # Independent explicit tail evidence: no expected_coverage/fps/container inference.
        assert any(int(raw["frames"][-1].get(k, 0)) > 0 for k in ("duration", "pkt_duration"))
        expected = None
        if len(paths) == 1 and paths[0].suffix == ".mkv":
            # Preserve Recording's existing verified millisecond-MKV coverage rule.
            _, source_frames = engine._frames(engine._probe(paths[0], 0))
            expected = [(at, length) for at, length in source_frames if at < 1]
        _, frames = engine._frames(raw, expected_coverage=expected)
        assert frames[0][0] == 0
        assert float(frames[-1][0] + frames[-1][1]) == analysis.duration_sec
        if synthetic:
            assert len(frames) == 30 * len(rows)
        engine._strict_decode(output)
        clip = service.build_incident_clip(resolution)
        assert clip.availability == "AVAILABLE" and clip.byte_size > 0
        assert clip.duration_sec == analysis.duration_sec
        assert clip.source_provenance.asset_spans == resolution.spans
        # The source build must retain #467's existing report/plate capabilities.
        export = LocalExportMaterializer(temp_root=work)
        stamped, operations = export.report(content,
            PostStamp(needed=True, value="2026-10-30T00:00:00+09:00"))
        assert stamped and stamped != content and operations[0]["post_stamp_applied"]
        frame = service.resolve_frame(dict(kind="STREAM_POSITION",
            media_stream_ref=rows[0]["media_stream_ref"], source_offset_sec=0.0))
        cropped, _ = export.plate(service.read_frame(frame.frame_ref), [0, 0, 32, 24], 30000)
        assert cropped.startswith(b"\x89PNG\r\n\x1a\n")
    assert before == [fingerprint(path) for path in paths]
    assert not list(work.iterdir())


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    with TemporaryDirectory(prefix="issue465-media-") as directory:
        root = Path(directory)
        if args:
            # Optional externally mounted actual source; never print its name/content.
            assert len(args) == 1
            exercise([Path(args[0])], root, synthetic=False)
            return {"actual_source": "PASS"}
        results = {}
        for suffix in ("mp4", "avi", "mkv"):
            case = root / suffix
            case.mkdir()
            source = case / ("synthetic." + suffix)
            generate(source)
            if suffix == "mp4":
                raw = LocalAnalysisMaterializer({})._probe(source, 0)
                assert Fraction(raw["streams"][0]["time_base"]) != Fraction(1, 10)
            exercise([source], case)
            results[suffix] = "PASS"
        case = root / "chain"
        case.mkdir()
        sources = [case / (name + ".mp4") for name in ("first", "second")]
        for path in sources:
            generate(path)
        exercise(sources, case)
        results["mp4_chain_analysis_incident"] = "PASS"
        return results


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception:
        # Avoid subprocess argv / original paths in acceptance logs, including private inputs.
        print("media acceptance: FAIL", file=sys.stderr)
        raise SystemExit(1)
