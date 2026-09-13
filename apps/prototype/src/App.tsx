import { useReducer } from 'react';
import { createInitialState, reduce } from './machine';
import { AppBar } from './components/AppBar';
import { ScenarioBar } from './components/ScenarioBar';
import { UploadScreen } from './screens/UploadScreen';
import { DescribeScreen } from './screens/DescribeScreen';
import { ScopeScreen } from './screens/ScopeScreen';
import { SearchingScreen } from './screens/SearchingScreen';
import { CandidatesScreen } from './screens/CandidatesScreen';
import { NoResultScreen } from './screens/NoResultScreen';
import { FailedScreen } from './screens/FailedScreen';
import { PrepareScreen } from './screens/PrepareScreen';
import { ReviewScreen } from './screens/ReviewScreen';
import { HandoffScreen } from './screens/HandoffScreen';

export default function App() {
  const [state, dispatch] = useReducer(reduce, undefined, createInitialState);

  let screen: React.ReactNode;
  switch (state.step) {
    case 'upload': screen = <UploadScreen state={state} dispatch={dispatch} />; break;
    case 'describe': screen = <DescribeScreen state={state} dispatch={dispatch} />; break;
    case 'scope': screen = <ScopeScreen state={state} dispatch={dispatch} />; break;
    case 'searching': screen = <SearchingScreen state={state} dispatch={dispatch} />; break;
    case 'candidates': screen = <CandidatesScreen state={state} dispatch={dispatch} />; break;
    case 'no-result': screen = <NoResultScreen state={state} dispatch={dispatch} />; break;
    case 'failed': screen = <FailedScreen state={state} dispatch={dispatch} />; break;
    case 'prepare': screen = <PrepareScreen state={state} dispatch={dispatch} />; break;
    case 'review': screen = <ReviewScreen state={state} dispatch={dispatch} />; break;
    case 'handoff': screen = <HandoffScreen state={state} dispatch={dispatch} />; break;
  }

  return (
    <div className="app-shell">
      <AppBar step={state.step} />
      {screen}
      <ScenarioBar state={state} dispatch={dispatch} />
    </div>
  );
}
