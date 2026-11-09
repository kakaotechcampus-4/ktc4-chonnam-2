import { useEffect, useId, useRef, useState } from 'react'
import { createPublicSamplesApi, type OfficialSample, type PublicSamplesApi } from '../api/publicSamples'
import type { CaseView } from '../contracts/caseView'
import { forgetCase, rememberCase } from '../state/lastCase'
import { ApiFlow } from './ApiFlow'
import { errorMessage } from '../contracts/labels'

function message(code: string) {
  if (code === 'http.not_found') return '이 브라우저에서 접근할 수 있는 체험을 찾지 못했어요.'
  return errorMessage(code)
}

/** A-1 intake only; existing CaseView-driven results/downloads remain in ApiFlow. */
export function OfficialSampleEntry(props: { client?: PublicSamplesApi; caseId?: string | null; remembered?: boolean; upload?: boolean }) {
  const [client] = useState(() => props.client ?? createPublicSamplesApi())
  const [samples, setSamples] = useState<OfficialSample[] | null>(null)
  const [selected, select] = useState('')
  const [caseId, setCaseId] = useState(props.upload ? null : props.caseId ?? null)
  const [view, setView] = useState<CaseView | null>(null)
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [deletion, setDeletion] = useState<'DELETING' | 'DELETED' | null>(null)
  const pending = useRef(false)
  const deleteDialog = useRef<HTMLDialogElement>(null)
  const deleteTitle = useId()
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
  async function remove() {
    if (!caseId) return
    await perform(async () => {
      const result = await client.deleteCase(caseId)
      if (!result.ok) return setError(message(result.error.code))
      if ((result.status === 200 && result.data.state === 'DELETED') || (result.status === 202 && result.data.state === 'DELETING')) {
        setDeletion(result.data.state)
        if (result.data.state === 'DELETED') {
          forgetCase(); setView(null)
          const url = new URL(location.href); url.searchParams.delete('case'); history.replaceState(null, '', url)
        }
      } else setError(message('web.invalid_response'))
    })
  }
  const ready = !!view && view.manifest_summary.ok_file_count > 0
  const uploadFlow = props.upload && !deletion
  const deleteButton = caseId && deletion !== 'DELETED' && <>
    <button type="button" className="rs-btn sec" disabled={busy} onClick={() => {
      if (pending.current) return
      if (deletion === 'DELETING') void remove()
      else if (!deleteDialog.current?.open) deleteDialog.current?.showModal()
    }}>
      {deletion === 'DELETING' ? '삭제 다시 확인' : '체험 데이터 삭제'}
    </button>
    <dialog ref={deleteDialog} className="rs-consent" aria-labelledby={deleteTitle} aria-describedby={`${deleteTitle}-description`}>
      <h2 id={deleteTitle}>체험 데이터를 삭제할까요?</h2>
      <p id={`${deleteTitle}-description`}>삭제하면 분석 결과와 신고자료를 다시 볼 수 없어요</p>
      <div className="rs-consent-actions">
        <button type="button" className="rs-btn sec" onClick={() => deleteDialog.current?.close()}>취소</button>
        <button type="button" className="rs-btn pri" disabled={busy} onClick={() => {
          if (pending.current) return
          deleteDialog.current?.close()
          void remove()
        }}>삭제하기</button>
      </div>
    </dialog>
  </>
  return <>
    {uploadFlow ? <ApiFlow api={uploadApi} caseId={props.caseId} remembered={props.remembered}
      uploadBundle={client.uploadBundle} onCase={setCaseId} caseActions={deleteButton} /> : view && view.stage !== 'INTAKE' && !deletion ? <ApiFlow api={client.cases} caseId={caseId}
      intake={<p role="status">체험 진행 정보를 확인하고 있어요.</p>} /> : <main className="web-main rs-page">
      <h1>공식 샘플로 체험하기</h1>
      <p>공식 샘플만 이용할 수 있어요. 직접 영상 업로드는 지원하지 않아요.</p>
      {deletion === 'DELETED' ? <><p role="status">삭제했어요.</p>
        {props.upload && <a href="/">처음으로</a>}</> : deletion === 'DELETING' ? <p role="status">삭제 중이에요. 완료 여부를 다시 확인할 수 있어요.</p> : ready && view ? <>
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
        <p>보관·삭제 기간과 반복 횟수는 아직 확정되지 않았어요. 현재는 공개 준비 중이에요.</p>
        <button type="button" className="rs-btn pri" disabled={busy || !selected} onClick={() => void prepare()}>샘플 준비</button>
      </>}
    </main>}
    {(error || (!uploadFlow && deleteButton)) && <div className="web-main">
      {error && <p role="alert">{error}</p>}
      {!uploadFlow && deleteButton && <div className="rs-case-actions">{deleteButton}</div>}
    </div>}
  </>
}
