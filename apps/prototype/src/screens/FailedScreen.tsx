import { TriangleAlert } from 'lucide-react';
import type { JSX } from 'react';
import type { Action, AppState } from '../types';
import { Button } from '../components/Button';

/**
 * PROTOTYPE-SPEC.md §5.8 — this screen has no stage-1 mockup (it's screen 8 of the 9-screen set,
 * but wasn't among the mockups DESIGN-stage1-mockups.html actually built). Built from the spec's
 * prose plus DESIGN.md's token conventions, reusing the same `.empty`/`.empty-ic`/`.empty-t`/
 * `.empty-s` recovery-screen shell NoResultScreen uses (global.css already comments that shell
 * as shared between "NoResultScreen, FailedScreen") so this doesn't invent a new visual style.
 *
 * Global Constraint: this is the ONLY screen in the whole app allowed to use `--red` — confined
 * here to the one alert element (the icon roundel: `--red-soft` fill, `--red-bd` border,
 * `--red` icon stroke). Title/body text stay on the normal `--ink`/`--muted` tokens (tokens.css's
 * own comment notes raw `--red` fails AA for text on white), so the "one alert element" carries
 * all the red, not the whole screen's copy.
 */
export function FailedScreen(props: { state: AppState; dispatch: (a: Action) => void }): JSX.Element {
  const { dispatch } = props;

  return (
    <div className="pbody">
      <div className="empty">
        <div className="empty-ic" style={{ background: 'var(--red-soft)', border: '1px solid var(--red-bd)' }}>
          <TriangleAlert size={34} color="var(--red)" strokeWidth={2} />
        </div>
        <h2 className="empty-t">영상 분석 중 문제가 발생했습니다</h2>
        <p className="empty-s">
          처리 서버에서 일시적인 오류가 발생했습니다. 지금까지 완료된 작업은 저장되어 있습니다 — 처음부터 다시 하지
          않아도 됩니다.
        </p>
        <div className="btnrow" style={{ justifyContent: 'center' }}>
          <Button variant="primary" size="large" onClick={() => dispatch({ type: 'RETRY' })}>
            다시 시도
          </Button>
          <Button size="large" onClick={() => dispatch({ type: 'SHOW_PARTIAL' })}>
            현재까지의 후보 보기
          </Button>
        </div>
      </div>
    </div>
  );
}
