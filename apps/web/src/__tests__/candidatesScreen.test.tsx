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
import { SNAPSHOTS } from '../contracts/fixtures'
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
// 값을 손으로 베껴 두지 않고 로더가 읽는 실제 산출물을 그대로 먹인다
// (`data/real/case/*.json` — `scripts/dump_real_caseview.py`가 쓴다).
// 베껴 두면 파이프라인이 고쳐져도 테스트만 옛 상태를 붙들고 조용히 통과한다 —
// 실제로 그럴 뻔했다. 2026-09-20 실측 당시 `at_provenance`와 `hints`가 비어
// 있었고 그 공백을 단언해 뒀는데, #103·#104로 둘 다 채워졌다.
//
// 이 산출물은 `stage=READY`라 화면 선택은 확인 화면으로 간다(#102). 그래도
// 후보 화면에 직접 먹이는 이유는, 실제 값이 후보 카드에 닿았을 때 무엇이
// 보이는지가 시연에서 실제로 물어볼 질문이기 때문이다.
describe('CandidatesScreen — 실제 case.get_view() 산출물', () => {
  const real = SNAPSHOTS.find((s) => s.scenarioId === 'real_e2e_happy_001')

  it('실제 산출물이 로더에 들어와 있다', () => {
    expect(real).toBeDefined()
    expect(real!.view.candidates.length).toBeGreaterThan(0)
  })

  it('절대시각이 없어도 카드가 비지 않는다 — 「시각 미확정」을 적는다', () => {
    // 실제 파이프라인에서 `candidates[].at`은 계속 null이다. search
    // `CandidateEvent`에 절대시각이 없고, `view.py`가 evidence의 `occurred_at`을
    // 후보로 덮어쓰지 않는다(#103 조사 결과). mock fixture가 READY에서 값을
    // 들고 있는 것과 다르다.
    expect(real!.view.candidates[0].at).toBeNull()
    const { container } = render(<CandidatesScreen view={real!.view} />)
    expect(container.textContent).toContain('시각 미확정')
  })

  it('시각 출처는 fallback이 아니라 등재된 문구로 뜬다', () => {
    // #104에서 고친 자리다. `recording.timeline_relative_only`는 「절대시각을
    // 못 구한 후보」를 위해 계약이 이미 등재해 둔 값이다. 여기가 fallback으로
    // 새면 그 수정이 되돌아간 것이다.
    const { container } = render(<CandidatesScreen view={real!.view} />)
    expect(container.textContent).toContain('영상 안 위치만 확인')
    expect(container.textContent).not.toContain('시각 출처 확인 중')
  })

  it('선택된 후보를 테두리 색만으로 알리지 않는다', () => {
    const { container } = render(<CandidatesScreen view={real!.view} />)
    expect(container.querySelector('.cand')!.classList.contains('sel')).toBe(true)
    expect(container.textContent).toContain('선택된 장면')
  })

  it('후보 1건이면 카드가 패널을 채운다 — 고정 3열의 빈 칸이 남지 않는다', () => {
    const { container } = render(<CandidatesScreen view={real!.view} />)
    const grid = container.querySelector('.cands')
    expect(grid).not.toBeNull()
    expect(grid!.children).toHaveLength(1)
  })
})
