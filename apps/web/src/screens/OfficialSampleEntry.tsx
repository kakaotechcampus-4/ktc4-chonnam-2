import { useEffect, useRef, useState } from 'react'
import { createPublicSamplesApi, type OfficialSample, type PublicSamplesApi } from '../api/publicSamples'
import type { CaseView } from '../contracts/caseView'
import { forgetCase, rememberCase } from '../state/lastCase'
import { ApiFlow } from './ApiFlow'
import { errorMessage } from '../contracts/labels'

function message(code: string) {
  if (code === 'http.not_found') return '이 브라우저에서 접근할 수 있는 체험을 찾지 못했어요.'
  return errorMessage(code)
}

function retentionNotice(seconds: number) {
  const parts: [number, string][] = [
    [Math.floor(seconds / 3600), '시간'],
    [Math.floor(seconds % 3600 / 60), '분'],
    [seconds % 60, '초'],
  ]
  const duration = parts.filter(([value]) => value > 0).map(([value, unit]) => `${value}${unit}`).join(' ')
  return `체험을 시작한 뒤 ${duration}부터 이 체험의 영상·분석 결과·신고자료를 서버에서 자동으로 정리해요. 정리된 자료는 다시 볼 수 없어요.`
}

/** A-1 intake only; existing CaseView-driven results/downloads remain in ApiFlow. */
export function OfficialSampleEntry(props: { client?: PublicSamplesApi; caseId?: string | null; remembered?: boolean; upload?: boolean; retentionSeconds: number }) {
  const [client] = useState(() => props.client ?? createPublicSamplesApi())
  const [samples, setSamples] = useState<OfficialSample[] | null>(null)
  const [selected, select] = useState('')
  const [caseId, setCaseId] = useState(props.caseId ?? null)
  const [view, setView] = useState<CaseView | null>(null)
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const [uploadApi] = useState(() => ({
    ...client.cases,
    async createCase() {
      const session = await client.ensureSession()
      return session.ok ? client.cases.createCase() : session
    },
  }))

  useEffect(() => {
    if (props.upload) return
    let active = true
    void client.listSamples().then(result => {
      if (!active) return
      if (result.ok) setSamples(result.data.samples)
      else { setSamples([]); setError(message(result.error.code)) }
    })
    if (props.caseId) void client.cases.getView(props.caseId).then(result => {
      if (!active) return
      if (result.ok) { setView(result.data); setDescription(result.data.description ?? '') }
      else if (result.status === 404 && props.remembered) {
        forgetCase(); setCaseId(null)
      } else setError(message(result.error.code))
    })
    return () => { active = false }
  }, [client, props.caseId, props.remembered, props.upload])

  function retain(id: string) {
    setCaseId(id); rememberCase(id)
    const url = new URL(location.href); url.searchParams.set('case', id)
    history.replaceState(history.state, '', url)
  }
  async function perform(action: () => Promise<void>) {
    if (pending.current) return
    pending.current = true; setBusy(true); setError(null)
    try { await action() } catch { setError(message('web.network_error')) }
    finally { pending.current = false; setBusy(false) }
  }
  async function prepare() {
    const sample = samples?.find(s => s.sample_id === selected)
    if (!sample) return
    await perform(async () => {
      const session = await client.ensureSession()
      if (!session.ok) return setError(message(session.error.code))
      let id = caseId
      if (!id) {
        const created = await client.cases.createCase()
        if (!created.ok) return setError(message(created.error.code))
        id = created.data.case_id; retain(id); setView(created.data.case_view)
      }
      const registered = await client.registerSample(id, sample.sample_id)
      if (!registered.ok) return setError(message(registered.error.code))
      setView(registered.data.case_view); setDescription(sample.example_hint)
    })
  }
  async function start() {
    if (!caseId || !view || !description.trim()) return
    await perform(async () => {
      const result = await client.cases.sendCommand(caseId, view.case_rev, { kind: 'START_ANALYSIS', payload: { description } })
      if (result.ok) return setView(result.data)
      if (result.caseView) setView(result.caseView)
      // Unknown outcome: read only. Never automatically repeat a paid command.
      if (result.status === 0 || (result.status >= 500 && result.status !== 503)) {
        const latest = await client.cases.getView(caseId)
        if (latest.ok) {
          setView(latest.data)
          if (latest.data.stage !== 'INTAKE') return
        }
      }
      setError(message(result.error.code))
    })
  }
  const notice = retentionNotice(props.retentionSeconds)
  if (props.upload) return <ApiFlow api={uploadApi} caseId={props.caseId} remembered={props.remembered}
    uploadBundle={client.uploadBundle} retentionNotice={notice} />

  const ready = !!view && view.manifest_summary.ok_file_count > 0
  return <>
    {view && view.stage !== 'INTAKE' ? <ApiFlow api={client.cases} caseId={caseId}
      intake={<p role="status">체험 진행 정보를 확인하고 있어요.</p>} /> : <main className="web-main rs-page">
      <h1>공식 샘플로 체험하기</h1>
      <p>공식 샘플만 이용할 수 있어요. 직접 영상 업로드는 지원하지 않아요.</p>
      <p>{notice}</p>
      {ready && view ? <>
        <p>서버에 등록된 영상 {view.manifest_summary.ok_file_count}개를 준비했어요.</p>
        <label>찾을 장면 설명<textarea value={description} onChange={e => setDescription(e.target.value)} disabled={busy} /></label>
        <button type="button" className="rs-btn pri" disabled={busy || !description.trim()} onClick={() => void start()}>분석 시작</button>
      </> : caseId && !view ? <p>체험 준비 결과를 확인해 주세요. 새 체험을 자동으로 시작하지 않아요.</p> : <>
        {samples === null ? <p>샘플 목록을 확인하고 있어요.</p> : samples.length === 0 ? <p>지금 이용할 수 있는 샘플이 없어요.</p> : <fieldset disabled={busy}>
          <legend>체험할 샘플</legend>
          {samples.map(s => <label key={s.sample_id}><input type="radio" name="official-sample" checked={selected === s.sample_id} onChange={() => select(s.sample_id)} />
            {s.label} · {Math.ceil(s.duration_ms / 1000)}초 · 영상 {s.file_count}개
          </label>)}
        </fieldset>}
        <p>공식 샘플은 한 번에 합계 10분까지 이용할 수 있어요.</p>
        <button type="button" className="rs-btn pri" disabled={busy || !selected} onClick={() => void prepare()}>샘플 준비</button>
      </>}
    </main>}
    {error && <div className="web-main"><p role="alert">{error}</p></div>}
  </>
}
