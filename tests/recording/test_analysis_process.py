"""Real bounded subprocesses, including a deliberately slow synthetic producer."""
import subprocess
import shutil
import sys

import pytest

from daesingo.common.jobs.cancel import CancelSignal, CancellationRequested
from daesingo.recording import RecordingCapabilityError


def test_output_growth_stops_before_process_completion_and_reaps(tmp_path):
    from daesingo.recording.analysis_limits import AnalysisSourceLimits, analysis_source_scope
    from daesingo.recording.analysis_process import run_output
    output, marker = tmp_path / "output", tmp_path / "completed"
    script = ("import pathlib,time,sys; p=pathlib.Path(sys.argv[1]); "
              "p.write_bytes(b'x'*10000); time.sleep(3); pathlib.Path(sys.argv[2]).touch()")
    with analysis_source_scope(AnalysisSourceLimits(100, 1000), lambda: None):
        with pytest.raises(RecordingCapabilityError) as caught:
            run_output([sys.executable, "-c", script, str(output), str(marker)], output, 10)
    assert caught.value.code == "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED"
    assert not marker.exists()
    # On Windows an open child handle prevents rename/delete, too.
    output.unlink()


@pytest.mark.parametrize("mode", ["cancel", "timeout"])
def test_subprocess_cancel_timeout_reap_and_restore_scope(tmp_path, mode):
    from daesingo.recording.analysis_limits import AnalysisSourceLimits, analysis_source_scope, byte_budget
    from daesingo.recording.analysis_process import run_output
    output = tmp_path / "output"
    signal = CancelSignal()
    def checkpoint():
        if mode == "cancel" and output.exists():
            signal.request()
        signal.checkpoint()
    script = "import pathlib,time,sys; pathlib.Path(sys.argv[1]).touch(); time.sleep(3)"
    with pytest.raises(CancellationRequested if mode == "cancel" else subprocess.TimeoutExpired):
        with analysis_source_scope(AnalysisSourceLimits(100, 1000), checkpoint):
            run_output([sys.executable, "-c", script, str(output)], output, .3)
    assert byte_budget() is None
    output.unlink(missing_ok=True)


def test_encode_diagnostics_are_drained_and_bounded(tmp_path):
    from daesingo.recording.analysis_limits import AnalysisSourceLimits, analysis_source_scope
    from daesingo.recording.analysis_process import run_output
    script = "import sys; sys.stderr.buffer.write(b'x'*1000000); sys.exit(1)"
    with analysis_source_scope(AnalysisSourceLimits(100, 1000), lambda: None):
        code, stderr = run_output([sys.executable, "-c", script], tmp_path / "absent", 10)
    assert code == 1 and stderr == b"x" * 8192


def test_real_ffmpeg_growth_interrupts_before_encode_finishes(tmp_path):
    from daesingo.recording.analysis_limits import AnalysisSourceLimits, analysis_source_scope
    from daesingo.recording.analysis_process import run_output
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required")
    output, progress = tmp_path / "prepared.mp4", tmp_path / "progress.txt"
    args = ["ffmpeg", "-nostdin", "-v", "error", "-re", "-f", "lavfi", "-i",
            "testsrc2=s=320x240:r=30:d=5", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "10",
            "-pix_fmt", "yuv420p", "-progress", str(progress), "-movflags", "+faststart", str(output)]
    with analysis_source_scope(AnalysisSourceLimits(1024, 5000), lambda: None):
        with pytest.raises(RecordingCapabilityError) as caught:
            run_output(args, output, 15)
    assert caught.value.code == "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED"
    assert progress.exists() and "progress=end" not in progress.read_text()
    output.unlink()


def test_tail_failure_classification_survives_bounded_stderr(tmp_path):
    from daesingo.recording import LocalAnalysisMaterializer
    from daesingo.recording.analysis_limits import AnalysisSourceLimits, analysis_source_scope
    from daesingo.recording.analysis_tail import TailDecodeFailure
    # Long tool stderr, including markers beyond the retained prefix and across
    # drain chunks, must preserve the strict AVI-tail classifier.
    script = ("import sys; sys.stderr.buffer.write(b'x'*16380 + b'No start code is found' + "
              "b'x'*5000 + b'Error submitting packet to decoder'); sys.exit(1)")
    args = [sys.executable, "-c", script, "-vf", "ignored", "-xerror", "-movflags", "+faststart",
            str(tmp_path / "absent.mp4")]
    engine = LocalAnalysisMaterializer({})
    with pytest.raises(TailDecodeFailure):
        engine._run(args)
    with analysis_source_scope(AnalysisSourceLimits(1024, 1000), lambda: None):
        with pytest.raises(TailDecodeFailure):
            engine._run(args)
