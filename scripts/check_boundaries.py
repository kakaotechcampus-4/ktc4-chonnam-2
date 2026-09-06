#!/usr/bin/env python3
"""모듈 경계 · 계약 정합성 점검.

명세는 두 문서가 소유한다. 이 스크립트는 규칙을 새로 만들지 않는다.
  - 모듈 경계 grep 목록  → docs/management/ownership.md §6
  - 계약 번호·enum 정답지 → docs/architecture/module-architecture.md §5-1 · §3-5

사용:
    python scripts/check_boundaries.py            # 전체
    python scripts/check_boundaries.py --only=contracts
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCH = os.path.join(ROOT, "docs", "architecture", "module-architecture.md")
CDIR = os.path.join(ROOT, "docs", "architecture", "contracts")
ADIR = os.path.join(CDIR, "adr")

CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".sql", ".yaml", ".yml", ".toml")

# ── 모듈 경계 — ownership.md §6 ────────────────────────────────
# 모듈 폴더 안에 등장하면 안 되는 문자열. 0건이어야 한다.
BOUNDARIES = [
    ("case",      "src/daesingo/case",      ["130MB", "기한", "프롬프트", "VIDEO_OVERLAY"]),
    ("recording", "src/daesingo/recording", ["신호위반", "중앙선", "신고"]),
    ("search",    "src/daesingo/search",    ["130MB", "신고유형", "if eval_mode"]),
    ("readout",   "src/daesingo/readout",   ["신고유형", "기한"]),
    ("evidence",  "src/daesingo/evidence",  ["ffmpeg", "프롬프트",
                                             "import search", "import readout",
                                             "from daesingo.search", "from daesingo.readout"]),
    ("eval",      "eval",                   ["import case", "import evidence",
                                             "from daesingo.case", "from daesingo.evidence"]),
    ("web",       "apps/web",               ["threshold", "130MB", "기한"]),
]

# ── 계약 헤더 필수 항목 ────────────────────────────────────────
REQUIRED_HEADERS = ["Status:", "Architecture Contract:", "Contract Version:"]

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"

fails = []
notes = []


def fail(check, msg):
    fails.append((check, msg))


def note(check, msg):
    notes.append((check, msg))


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def walk_code(rel):
    base = os.path.join(ROOT, rel)
    if not os.path.isdir(base):
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames
                       if d not in ("node_modules", "__pycache__", "dist", ".venv")]
        for name in filenames:
            if name.endswith(CODE_EXT):
                yield os.path.join(dirpath, name)


# ══ 1. 모듈 경계 ══════════════════════════════════════════════
def check_boundaries():
    for module, rel, banned in BOUNDARIES:
        checked = 0
        for path in walk_code(rel):
            checked += 1
            body = read(path)
            for lineno, line in enumerate(body.splitlines(), 1):
                for token in banned:
                    if token in line:
                        shown = os.path.relpath(path, ROOT).replace(os.sep, "/")
                        fail("boundary/" + module,
                             "%s:%d — 금지 문자열 %r" % (shown, lineno, token))
        if checked == 0:
            note("boundary/" + module, "%s 아래에 검사할 코드 파일이 없다 (골격 단계)" % rel)


# ══ 2. 계약 헤더 ══════════════════════════════════════════════
def contract_files():
    return sorted(f for f in os.listdir(CDIR)
                  if f.startswith("contract-") and f.endswith(".md"))


def check_headers():
    for name in contract_files():
        head = read(os.path.join(CDIR, name))[:1500]
        for key in REQUIRED_HEADERS:
            if key not in head:
                fail("header", "%s — 헤더에 %s 가 없다" % (name, key))
        if "Architecture Contract:" in head:
            line = [l for l in head.splitlines() if "Architecture Contract:" in l][0]
            if not any(c in line for c in CIRCLED):
                fail("header", "%s — Architecture Contract 포인터에 §5-1 번호가 없다" % name)


# ══ 3. 계약 문서에 번호를 되넣지 않았는가 (드리프트 재발 방지) ══
def check_no_renumber():
    """번호는 v4 §5-1이 소유한다(adr-consistency-2026-09 C1-2).
    계약 문서에서 번호가 허용되는 곳은 Architecture Contract 포인터 줄뿐이다."""
    for name in contract_files():
        for lineno, line in enumerate(read(os.path.join(CDIR, name)).splitlines(), 1):
            if not any(c in line for c in CIRCLED):
                continue
            if "Architecture Contract:" in line:
                continue
            if line.lstrip().startswith("#"):
                fail("renumber", "%s:%d — 제목에 계약 번호가 다시 들어갔다: %s"
                     % (name, lineno, line.strip()[:60]))


# ══ 4. 위반유형 enum — v4 §3-5가 정답지 ═══════════════════════
def check_event_enum():
    arch = read(ARCH)
    m = re.search(r"^\s*(SIGNAL / [A-Z_ /]+)$", arch, re.M)
    if not m:
        fail("enum/event", "v4에서 위반유형 baseline enum 줄을 찾지 못했다 (§3-5)")
        return
    allowed = set(t.strip() for t in m.group(1).split("/") if t.strip())
    # baseline 4종과 혼동되기 쉬운 변형
    variants = {"LANE_CHANGE": "SOLID_LINE_LANE_CHANGE"}
    for name in contract_files():
        body = read(os.path.join(CDIR, name))
        for lineno, line in enumerate(body.splitlines(), 1):
            for bad, good in variants.items():
                for hit in re.finditer(r"(?<![A-Z_])%s(?![A-Z_])" % bad, line):
                    if good in line[max(0, hit.start() - 20):hit.end()]:
                        continue
                    fail("enum/event", "%s:%d — %r 는 v4 §3-5 baseline이 아니다 (→ %r)"
                         % (name, lineno, bad, good))
    if "SOLID_LINE_LANE_CHANGE" not in allowed:
        fail("enum/event", "v4 baseline enum이 바뀌었다. 이 스크립트의 variants 표를 갱신하라")


# ══ 5. ADR 짝 ════════════════════════════════════════════════
def check_adr_pairs():
    adrs = set(f for f in os.listdir(ADIR) if f.startswith("adr-") and f.endswith(".md"))
    for name in contract_files():
        slug = name[len("contract-"):-len(".md")]
        if "adr-%s.md" % slug not in adrs:
            note("adr-pair", "%s — 짝 ADR(adr/adr-%s.md)이 없다" % (name, slug))


# ══ 6. v4 §5-1 커버리지 ══════════════════════════════════════
def check_coverage():
    arch = read(ARCH)
    table = arch[arch.index("## 5-1. 계약 목록"):arch.index("## 5-2.")]
    corpus = "\n".join(read(os.path.join(CDIR, n)) for n in contract_files())
    types = set()
    for row in table.splitlines():
        if not row.startswith("| ") or "---" in row:
            continue
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) < 2 or cells[0] not in CIRCLED:
            continue
        for t in re.findall(r"`([A-Za-z][A-Za-z0-9<>]*)`", cells[1]):
            types.add(t)
    for t in sorted(types):
        if not re.search(r"(?<![A-Za-z])%s(?![A-Za-z])" % re.escape(t), corpus):
            fail("coverage", "v4 §5-1의 %s 가 어느 계약에도 없다" % t)
        elif not re.search(r"^#+.*`?%s`?" % re.escape(t), corpus, re.M):
            note("coverage", "%s — 언급만 있고 전용 절이 없다 (스키마 미작성 가능)" % t)


CHECKS = {
    "boundaries": check_boundaries,
    "contracts": lambda: (check_headers(), check_no_renumber(),
                          check_event_enum(), check_adr_pairs(), check_coverage()),
}


def main():
    only = None
    for arg in sys.argv[1:]:
        if arg.startswith("--only="):
            only = arg.split("=", 1)[1]
    for key, fn in CHECKS.items():
        if only in (None, key):
            fn()

    if notes:
        print("NOTE — 확인 대상 (실패는 아니다)")
        for check, msg in notes:
            print("  [%s] %s" % (check, msg))
        print()
    if fails:
        print("FAIL — %d건" % len(fails))
        for check, msg in fails:
            print("  [%s] %s" % (check, msg))
        print("\n규칙 원문: docs/management/ownership.md §6 · "
              "docs/architecture/module-architecture.md §5-1 · §3-5")
        return 1
    print("PASS — 경계·계약 정합성 위반 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
