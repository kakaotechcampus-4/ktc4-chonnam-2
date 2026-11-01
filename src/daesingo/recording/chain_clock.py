"""Exact MP4 clock projection for mixed-clock chains (FFmpeg 8.1).

Only derived bytes are remuxed. Source facts and public provenance are untouched.
concatdec uses microsecond offsets; setts restores their exact rational values.
"""
from fractions import Fraction
import json
from math import gcd

from .analysis_limits import checkpoint, check_output, remaining_bytes
from .errors import RecordingCapabilityError


# movenc's video_track_timescale is AV_OPT_TYPE_INT. setts evaluates doubles.
_INT_MAX = (1 << 31) - 1
_EXACT_INT_MAX = (1 << 53) - 1


def _reject():
    raise RecordingCapabilityError('UNSUPPORTED_MEDIA', '공통 출력 시간축을 정확히 표현할 수 없습니다')


def _ticks(value, base, maximum=_EXACT_INT_MAX):
    ticks = Fraction(value) / base
    if ticks.denominator != 1 or abs(ticks.numerator) > maximum:
        _reject()
    return ticks.numerator


def common_time_base(parts, packet_sets=()):
    scale = 1
    for part in parts:
        if part.time_base is None or part.time_base <= 0 or not part.frames:
            _reject()
        if (part.source_frames != part.frames
                or any((value / part.time_base).denominator != 1
                       for frame in part.frames for value in frame)):
            _reject()
    # Preserve observed instants/intervals, not unused ticks of a stream clock.
    # Packet DTS can require a finer grid than decoded presentation frames.
    values = (value for part in parts for frame in part.frames for value in frame)
    packet_values = (value for packets in packet_sets for packet in packets for value in packet)
    from itertools import chain
    for value in chain(values, packet_values):
        denominator = Fraction(value).denominator
        factor = denominator // gcd(scale, denominator)
        if scale > _INT_MAX // factor:
            _reject()
        scale *= factor
    base, offset = Fraction(1, scale), Fraction(0)
    for part in parts:
        if part.frames[0][0] != 0 or part.source_frames != part.frames:
            _reject()
        end = Fraction(0)
        for at, duration in part.frames:
            if at != end or duration <= 0:
                _reject()
            _ticks(at, base)
            _ticks(duration, base, _INT_MAX)
            end = at + duration
            _ticks(offset + end, base)
        offset += end
    return base


def _check_packet_ranges(packets):
    if (not packets
            or any(abs(value) > _EXACT_INT_MAX for packet in packets for value in packet)
            or any(d <= 0 or d > _INT_MAX or abs(p-t) > _INT_MAX for p, t, d in packets)
            # movenc check_pkt rewrites a DTS delta >= INT_MAX, not only >.
            or any(not 0 < b[1]-a[1] < _INT_MAX for a, b in zip(packets, packets[1:]))):
        _reject()


def _packets(engine, path, base=None):
    raw = json.loads(engine._run([engine._ffprobe, '-v', 'error', '-protocol_whitelist', 'file',
        '-select_streams', 'v:0', '-show_packets', '-show_entries',
        'stream=time_base,start_pts:packet=pts,dts,duration', '-of', 'json', str(path)]))
    stream = raw['streams'][0]
    clock = Fraction(stream['time_base'])
    if clock <= 0 or int(stream['start_pts']) != 0:
        _reject()
    packets = [tuple(int(p[k])*clock for k in ('pts', 'dts', 'duration'))
               for p in raw['packets']]
    if base is None:
        return packets
    packets = [tuple(_ticks(value, base) for value in packet) for packet in packets]
    _check_packet_ranges(packets)
    return packets


def validate_packets(engine, path, base, expected):
    if _packets(engine, path, base) != expected:
        _reject()


def _offset_expression(corrections):
    # Both linear nesting and a flat sum produce an AVExpr tree of linear depth.
    # A balanced lookup has logarithmic depth and no arithmetic intermediate.
    for count, correction in corrections:
        if max(abs(correction), abs(count)) > _EXACT_INT_MAX:
            _reject()
    if (not corrections or corrections[0][0] != 0
            or any(a[0] >= b[0] for a, b in zip(corrections, corrections[1:]))):
        _reject()

    def lookup(start, end):
        if end-start == 1:
            return str(corrections[start][1])
        middle = (start+end)//2
        return f'if(lt(N,{corrections[middle][0]}),{lookup(start, middle)},{lookup(middle, end)})'

    return lookup(0, len(corrections)).replace(',', r'\,')


def prepare_mixed_parts(engine, parts, root):
    """Return manifest lines, BSF options and exact expected packet timeline."""
    lines, expected, corrections = ['ffconcat version 1.0'], [], []
    offset, microseconds, count, used = Fraction(0), 0, 0, 0
    packet_sets = []
    for i, part in enumerate(parts):
        checkpoint()
        source = root / f'encoded-{i}.mp4'
        source.write_bytes(part.content)
        packet_sets.append(_packets(engine, source))
    base = common_time_base(parts, packet_sets)
    for i, part in enumerate(parts):
        checkpoint()
        source, target = root / f'encoded-{i}.mp4', root / f'part-{i}.mp4'
        packets = [tuple(_ticks(value, base) for value in packet) for packet in packet_sets[i]]
        _check_packet_ranges(packets)
        if sorted(p for p, _, _ in packets) != [_ticks(at, base) for at, _ in part.frames]:
            _reject()
        with remaining_bytes(used):
            engine._run([engine._ffmpeg, '-nostdin', '-v', 'error', '-xerror', '-n',
                '-copyts', '-protocol_whitelist', 'file', '-i', str(source),
                '-map', '0:v:0', '-an', '-sn', '-dn', '-map_metadata', '-1', '-map_chapters', '-1',
                '-c:v', 'copy', '-copytb', '1', '-video_track_timescale', str(base.denominator),
                '-avoid_negative_ts', 'disabled', '-movflags', '+faststart', str(target)])
            check_output(target)
        used += target.stat().st_size
        source.unlink()
        raw = engine._probe(target)
        clock, frames = engine._frames(raw, expected_coverage=part.frames)
        if (clock != base or tuple(frames) != part.frames
                or int(raw['frames'][0]['best_effort_timestamp']) != 0):
            _reject()
        validate_packets(engine, target, base, packets)
        exact = _ticks(offset, base)
        # av_rescale_q for nonnegative microsecond offset: nearest, ties away.
        transported = (microseconds * base.denominator * 2 + 1000000) // 2000000
        correction = exact - transported
        decode_origin = packets[0][1]
        corrections.append((count, correction, correction-decode_origin))
        length = part.frames[-1][0] + part.frames[-1][1]
        if (any(a[1]+a[2] != b[1] for a, b in zip(packets, packets[1:]))
                or packets[-1][1]+packets[-1][2]-decode_origin != _ticks(length, base)):
            _reject()
        for pts, dts, duration in packets:
            for value in (pts+transported, dts+transported, pts+exact, dts+exact):
                if abs(value) > _EXACT_INT_MAX:
                    _reject()
            expected.append((pts+exact, dts+exact-decode_origin, duration))
        count += len(packets)
        if count > _EXACT_INT_MAX:
            _reject()
        # This is only concat transport metadata, never the expected coverage.
        duration_us = length * 1000000 // 1
        if duration_us <= 0 or microseconds + duration_us > _EXACT_INT_MAX:
            _reject()
        lines.extend([f'file {target.name}', f'duration {duration_us//1000000}.{duration_us%1000000:06d}'])
        microseconds += duration_us
        offset += length
    # Piecewise constant correction by actual packet ordinal, not nominal FPS.
    # Different reorder delays must not change the previous segment's final
    # sample duration. Join decode intervals separately, with one shared delay
    # large enough that every PTS >= DTS. Presentation coverage is unchanged.
    delay = max(0, max(dts-pts for pts, dts, _ in expected))
    expected = [(pts, dts-delay, duration) for pts, dts, duration in expected]
    for count, pts_correction, dts_correction in corrections:
        if max(abs(pts_correction), abs(dts_correction-delay)) > _EXACT_INT_MAX:
            _reject()
    pts_expression = _offset_expression([(n, p) for n, p, _ in corrections])
    dts_expression = _offset_expression([(n, d-delay) for n, _, d in corrections])
    _check_packet_ranges(expected)
    options = ['-copyts', '-bsf:v',
        f'setts=pts=PTS+{pts_expression}:dts=DTS+{dts_expression}:duration=DURATION:time_base={base}',
        '-avoid_negative_ts', 'disabled']
    return lines, options, expected, base
