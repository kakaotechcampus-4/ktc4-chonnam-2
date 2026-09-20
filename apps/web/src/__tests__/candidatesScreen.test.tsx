// @vitest-environment jsdom
//
// 후보 비교 화면(A-1) 렌더 테스트.
//
// 앱이 읽는 16 스냅샷에는 후보가 최대 1건뿐이라(mock 카탈로그 설계) 나란히
// 비교하는 모습을 실물 데이터로 볼 수 없다. 여기서 조립하는 CaseView는
// **테스트 전용**이며 `data/mock`에 사본을 만들지 않는다 — 화면이 CaseView를
// 그대로 소비한다는 증빙 대상은 계속 저장소 원본 하나다(fixtures.ts 주석).

import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Candidate, CaseView } from '../contracts/caseView'
import { CandidatesScreen } from '../screens/CandidatesScreen'

afterEach(cleanup)

function candidate(over: Partial<Candidate> & { candidate_id: string }): Candidate {
  return {
    at: '18:31:48',
    at_provenance: 'recording.filename_time',
    at_provenance_label_key: 'candidate.at_provenance.filename_time',
    observed: '흰색 SUV가 백색 실선을 넘어 인접 차로로 이동',
    thumb_ref: 'fr_7c2e91',
    selected: false,
    timeline_revision: 1,
    stale_revision: false,
    stale_revision_label_key: null,
    situation_confirmation: 'NOT_ASKED',
    ...over,
  }
}

function view(candidates: Candidate[]): CaseView {
  return {
    case_id: 'case_test',
    case_rev: 1,
    stage: 'CANDIDATE_REVIEW',
    user_reviewed: false,
    manifest_summary: { file_count: 1, ok_file_count: 1, failed_file_count: 0, duration_sec: 600, range: null },
    hints: { time: '18시쯤', vehicle: '흰색 SUV', situation: null, location: null },
    progress: [],
    candidates,
    evidence: null,
    requirements_evidence: null,
    requirements_package: null,
    package: null,
    running_jobs: [],
    notices: [],
  }
}

describe('CandidatesScreen — 나란히 비교(A-1)', () => {
  it('후보를 그리드에 나란히 놓는다', () => {
    const { container } = render(
      <CandidatesScreen view={view([candidate({ candidate_id: 'c1' }), candidate({ candidate_id: 'c2' }), candidate({ candidate_id: 'c3' })])} />,
    )
    expect(container.querySelectorAll('.cands')).toHaveLength(1)
    expect(container.querySelectorAll('.cand')).toHaveLength(3)
  })

  it('후보 순서를 화면이 다시 정하지 않는다 — 배열 순서 그대로 번호를 매긴다', () => {
    // 시각이 뒤죽박죽인 배열을 넣는다. 화면이 시각순으로 재정렬하거나 점수를
    // 다시 매기면 이 단언이 깨진다(판정 재계산 금지).
    const { container } = render(
      <CandidatesScreen
        view={view([
          candidate({ candidate_id: 'c_late', at: '18:31:48' }),
          candidate({ candidate_id: 'c_early', at: '18:19:03' }),
          candidate({ candidate_id: 'c_mid', at: '18:25:40' }),
        ])}
      />,
    )
    expect([...container.querySelectorAll('.cnum')].map((n) => n.textContent)).toEqual(['1', '2', '3'])
    expect([...container.querySelectorAll('.cand-tc')].map((n) => n.textContent)).toEqual(['18:31:48', '18:19:03', '18:25:40'])
  })

  it('selected인 후보만 강조한다', () => {
    const { container } = render(
      <CandidatesScreen
        view={view([
          candidate({ candidate_id: 'c1' }),
          candidate({ candidate_id: 'c2', selected: true }),
          candidate({ candidate_id: 'c3' }),
        ])}
      />,
    )
    const cards = [...container.querySelectorAll('.cand')]
    expect(cards.map((c) => c.classList.contains('sel'))).toEqual([false, true, false])
  })

  it('썸네일 자리는 후보마다 비워 둔다 — 계약(A-5)이 열리기 전까지', () => {
    const { container } = render(
      <CandidatesScreen view={view([candidate({ candidate_id: 'c1' }), candidate({ candidate_id: 'c2' })])} />,
    )
    expect(container.querySelectorAll('.cand-th')).toHaveLength(2)
    expect(container.textContent).toContain('미리보기 준비 중')
  })

  it('후보 1건에서도 깨지지 않는다 — relative_rebase 스냅샷 회귀', () => {
    const { container } = render(<CandidatesScreen view={view([candidate({ candidate_id: 'c1', selected: true })])} />)
    expect(container.querySelectorAll('.cand')).toHaveLength(1)
    expect(container.querySelectorAll('.cands')).toHaveLength(1)
  })

  it('기존 카드 내용을 잃지 않는다 — 관찰 문장·상황 확인·시각 출처', () => {
    const { container } = render(
      <CandidatesScreen view={view([candidate({ candidate_id: 'c1', situation_confirmation: 'CONFIRMED' })])} />,
    )
    expect(container.textContent).toContain('흰색 SUV가 백색 실선을 넘어 인접 차로로 이동')
    expect(container.textContent).toContain('사용자 확인됨')
    expect(container.textContent).toContain('파일명 시각')
  })
})

// ── 실제 데이터 회귀 ──────────────────────────────────────────────
//
// 아래 값은 지어낸 것이 아니라 `tests/case/test_real_e2e.py`가 돌린 실제
// 파이프라인(recording → search → readout → evidence)의 `case.get_view()`
// 산출물을 2026-09-20에 떠온 것이다. mock 스냅샷과 달리 `at`·`at_provenance`가
// 전부 null이고 `hints`가 통째로 비어 있다 — 후보 화면이 이 상태에서
// 무엇을 그리는지가 월요일 Real E2E 시연에서 실제로 보일 모습이다.
//
// 값이 채워지면 이 테스트는 갱신 대상이다. 그때까지는 「빈 값이어도 화면이
// 거짓말하지 않는다」를 지키는 자리다.
describe('CandidatesScreen — 실제 E2E 산출물(2026-09-20 실측)', () => {
  // 계약 타입은 `at_provenance: string`(non-null)인데 실제 파이프라인은 null을
  // 내린다. 이 캐스트가 그 불일치의 증거다 — 고치는 건 case/계약 쪽 몫이라
  // 여기서는 실제로 오는 값을 그대로 둔다.
  const realCandidate = {
    candidate_id: 'candidate_h001',
    at: null,
    at_provenance: null,
    at_provenance_label_key: null,
    observed: '흰 SUV가 백색 실선을 넘어 인접 차로로 이동하는 장면',
    thumb_ref: 'fr_h001_thumb',
    selected: false,
    timeline_revision: 1,
    stale_revision: false,
    stale_revision_label_key: null,
    situation_confirmation: 'NOT_ASKED',
  } as unknown as Candidate

  // 실제 산출물의 `hints`는 4개 키가 있는 객체가 아니라 `{}`다.
  const realView = { ...view([realCandidate]), hints: {} } as unknown as CaseView

  it('시각이 없어도 카드가 비지 않는다 — 「시각 미확정」을 적는다', () => {
    const { container } = render(<CandidatesScreen view={realView} />)
    expect(container.textContent).toContain('시각 미확정')
  })

  it('시각 출처가 없어도 빈 칸으로 두지 않는다 — fallback 문구를 쓴다', () => {
    const { container } = render(<CandidatesScreen view={realView} />)
    expect(container.textContent).toContain('시각 출처 확인 중')
  })

  it('hints가 비어 있어도 화면이 깨지지 않는다', () => {
    const { container } = render(<CandidatesScreen view={realView} />)
    expect(container.querySelectorAll('.cand')).toHaveLength(1)
    expect(container.textContent).toContain('흰 SUV가 백색 실선을 넘어 인접 차로로 이동하는 장면')
  })

  it('후보 1건이면 카드가 패널을 채운다 — 고정 3열의 빈 칸이 남지 않는다', () => {
    const { container } = render(<CandidatesScreen view={realView} />)
    const grid = container.querySelector('.cands')
    expect(grid).not.toBeNull()
    expect(grid!.children).toHaveLength(1)
  })
})
