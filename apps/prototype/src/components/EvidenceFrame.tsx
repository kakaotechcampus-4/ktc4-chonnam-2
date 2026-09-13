import type { CSSProperties, JSX } from 'react';
import type { Candidate } from '../types';

/**
 * Global Constraint: 실제 영상·이미지를 쓰지 않는다 — 항상 인라인 SVG.
 * 도로/차량 실루엣 좌표는 DESIGN-stage1-mockups.html 1544–1562행(화면 5 메인
 * 뷰어)·1620–1627행(후보 카드 썸네일)의 값을 그대로 옮겨 세 장면이 목업과
 * 같은 "블랙박스 대시캠" 그림 언어를 쓰게 했다.
 */
const ROAD_BASE = (
  <>
    <rect width="320" height="180" fill="#5d6b7d" />
    <rect width="320" height="86" fill="#7d8b9c" />
    <rect y="30" width="46" height="56" fill="#4e5a68" />
    <rect y="18" x="52" width="34" height="68" fill="#596675" />
    <rect y="86" width="320" height="94" fill="#3f464e" />
    <path d="M0 180 L138 86 L152 86 L60 180 Z" fill="#474e57" />
    <path d="M320 180 L196 86 L182 86 L268 180 Z" fill="#474e57" />
  </>
);

/**
 * 차선 표시. `solid-cross`/`dark-car`는 실선(확신) — 목업 1553–1555행의 3조각
 * 사다리꼴을 그대로 쓴다. `ambiguous-line`은 점선(불확실)을 stroke-dasharray로
 * 그려 "일부러 덜 확실해 보이게" 한다 — 색도 순백(#e8ecf0)이 아니라 흐린
 * 회청색(#aeb8c4)을 써서 실선과 눈에 띄게 다르게 만든다.
 */
function LaneLine({ dashed }: { dashed: boolean }): JSX.Element {
  if (dashed) {
    return (
      <path
        d="M150 88 L98 178"
        fill="none"
        stroke="#aeb8c4"
        strokeWidth="7"
        strokeDasharray="12 11"
        strokeLinecap="round"
      />
    );
  }
  return (
    <>
      <path d="M148 86 L142 104 L136 104 L143 86 Z" fill="#e8ecf0" />
      <path d="M134 112 L124 138 L114 138 L127 112 Z" fill="#e8ecf0" />
      <path d="M110 148 L94 180 L80 180 L100 148 Z" fill="#e8ecf0" />
    </>
  );
}

/** SUV 실루엣. `dark-car`는 전체를 어둡게(칙칙한 톤 + 검은 오버레이) 만들어
 * "차량 색이 더 어둡습니다"(후보 3 근거)를 그림으로도 말한다. */
function CarSilhouette({ dark }: { dark: boolean }): JSX.Element {
  const body = dark ? '#7a828c' : '#eef1f4';
  const glass = dark ? '#3c434b' : '#5b6672';
  const flank = dark ? '#c7ccd2' : '#fdfefe';
  return (
    <>
      <path d="M172 86 L232 180 L246 180 L178 86 Z" fill={flank} />
      <rect x="196" y="96" width="72" height="48" rx="5" fill={body} />
      <rect x="200" y="100" width="64" height="19" rx="3" fill={glass} />
      <rect x="203" y="136" width="12" height="9" rx="2" fill="#2a2f36" />
      <rect x="249" y="136" width="12" height="9" rx="2" fill="#2a2f36" />
      <rect x="214" y="127" width="34" height="9" rx="2" fill="#d5dae0" />
    </>
  );
}

const SCENE_LABEL: Record<Candidate['scene'], string> = {
  'solid-cross': '블랙박스 영상 — 백색 실선을 넘는 흰색 SUV',
  'ambiguous-line': '블랙박스 영상 — 실선인지 점선인지 불분명한 차선',
  'dark-car': '블랙박스 영상 — 어두워서 차량 색이 잘 보이지 않는 장면',
};

function Scene(props: { scene: Candidate['scene']; labelled: boolean }): JSX.Element {
  const dark = props.scene === 'dark-car';
  const dashed = props.scene === 'ambiguous-line';
  return (
    <svg
      viewBox="0 0 320 180"
      preserveAspectRatio="none"
      role={props.labelled ? 'img' : undefined}
      aria-label={props.labelled ? SCENE_LABEL[props.scene] : undefined}
      aria-hidden={props.labelled ? undefined : true}
    >
      {ROAD_BASE}
      <LaneLine dashed={dashed} />
      <CarSilhouette dark={dark} />
      {/* 어두운/야간 톤 — DESIGN.md는 다크 배경을 UI 표면으로 쓰지 않지만, 영상
          프레임 안(§Shapes "영상 프레임")은 예외다. */}
      {dark && <rect width="320" height="180" fill="#000" opacity="0.38" />}
    </svg>
  );
}

export function EvidenceFrame(props: {
  scene: Candidate['scene'];
  time?: string;
  file?: string;
  annotations?: string[];
  size?: 'small' | 'large';
}): JSX.Element {
  const small = props.size === 'small';
  // small = 후보 카드 썸네일(.cand-th), large(기본) = 메인 뷰어(.ev) — 둘 다
  // Task 1이 이미 포팅한 16:9/어두운 배경 컨테이너 클래스라 새로 만들지 않는다.
  const containerClass = small ? 'cand-th' : 'ev';

  return (
    <div className={containerClass}>
      <Scene scene={props.scene} labelled={!small} />
      {small ? (
        props.time && <span className="ev-chip bl">{props.time}</span>
      ) : (
        <>
          {props.time && <span className="ev-chip tl">{props.time}</span>}
          {props.file && <span className="ev-chip tr">{props.file}</span>}
        </>
      )}
      {/* annotations는 위치 정보가 없는 순수 문자열 목록(브리프의 계약대로) —
          아래에서 위로 쌓아 올린다. Global Constraint: 주석은 전부 초록,
          오렌지 금지 — `.ev-tag`는 이미 --green-solid 배경/흰 글자다. */}
      {props.annotations?.map((text, i) => {
        const style: CSSProperties = { left: '12px', bottom: `${12 + i * 34}px`, right: 'auto', top: 'auto' };
        return (
          <span key={text} className="ev-tag" style={style}>
            {text}
          </span>
        );
      })}
    </div>
  );
}
