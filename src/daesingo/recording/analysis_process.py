"""Poll encode/mux output; always reap children on budget, timeout or cancellation."""
import subprocess
from threading import Thread
from time import monotonic

from .analysis_limits import check_output_size, checkpoint


def run_output(args, output, timeout):
    checkpoint()
    # Drain stderr concurrently to avoid pipe backpressure, retain bounded diagnostics.
    diagnostic = bytearray()
    # The existing strict AVI-tail classifier needs these exact observations
    # even when they occur after the retained prefix or across read boundaries.
    markers = (b"No start code is found", b"Error submitting packet to decoder")
    observed = set()
    def drain(pipe):
        suffix = b""
        while chunk := pipe.read(4096):
            diagnostic.extend(chunk[:max(0, 8192 - len(diagnostic))])
            window = suffix + chunk
            observed.update(marker for marker in markers if marker in window)
            suffix = window[-(max(map(len, markers)) - 1):]

    process = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    reader = Thread(target=drain, args=(process.stderr,))
    started = monotonic()
    try:
        reader.start()
        while True:
            checkpoint()
            if output.exists():
                check_output_size(output.stat().st_size)
            if process.poll() is not None:
                break
            if monotonic() - started >= timeout:
                raise subprocess.TimeoutExpired("recording media tool", timeout)
            try:
                process.wait(timeout=min(.05, max(.001, timeout - (monotonic() - started))))
            except subprocess.TimeoutExpired:
                pass
        checkpoint()
        if output.exists():
            check_output_size(output.stat().st_size)
        reader.join()
        summary = b"\n".join(marker for marker in markers if marker in observed)
        return process.returncode, bytes(diagnostic[:8192 - len(summary)]) + summary
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        if reader.ident is not None:
            reader.join()
        process.stderr.close()
