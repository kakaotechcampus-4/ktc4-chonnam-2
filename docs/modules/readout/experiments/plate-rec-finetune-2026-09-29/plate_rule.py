"""번호 형식 검사 — 고시(국토교통부고시 제2025-121호) 제5조·제6조 표로 번호 형식을 검사한다."""
import re
PRIVATE = set("가나다라마거너더러머버서어저고노도로모보소오조구누두루무부수우주")
BIZ = set("바사아자배"); RENT = set("하허호"); HANGUL = PRIVATE | BIZ | RENT
REGION = "서울 부산 대구 인천 광주 대전 울산 세종 경기 강원 충북 충남 전북 전남 경북 경남 제주".split()
PAT = re.compile(r"^(?P<r>[가-힣]{2})?(?P<n>\d{2,3})(?P<h>[가-힣])\d{4}$")
def valid(t):
    m = PAT.match(t or "")
    if not m: return False
    r, n, h = m["r"], m["n"], m["h"]
    if h not in HANGUL: return False
    if n == "00" or (len(n) == 3 and n[0] == "0"): return False
    if r: return r in REGION and h in BIZ and len(n) == 2   # 지역명은 운수사업용에만, 사업용은 2자리
    if h in BIZ and len(n) == 3: return False
    return True
def demo():
    for t in ["123가4567","12가3456","서울12바3456","05하1234","125호1234"]: assert valid(t), t
    for t in ["123쿠4567","서울12가3456","서울123바4567","123바4567","012가3456","한국12바3456","083고1234"]: assert not valid(t), t
if __name__ == "__main__":
    demo()
