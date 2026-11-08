// 마지막으로 연 case를 이 브라우저에 기억한다 — 창을 닫았다가 첫 주소로 다시 와도 진행 중인 분석·결과로 이어진다.
// case id만 둔다(영상 · 결과는 서버에 있다). 다른 기기 · 브라우저로는 넘어가지 않는다(로그인 없음).
// 저장소를 못 쓰는 환경(사생활 보호 모드 등)에서는 조용히 기억하지 않는다 — 주소의 `?case=`로는 여전히 이어진다.
const KEY = 'daesingo.lastCase'

export function rememberedCase(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function rememberCase(caseId: string): void {
  try {
    localStorage.setItem(KEY, caseId)
  } catch {
    // 기억하지 못해도 흐름은 그대로다
  }
}

export function forgetCase(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // 위와 같다
  }
}
