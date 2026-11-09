import { createApi, INVALID_RESPONSE, NETWORK_ERROR, type ApiResult } from './client'
import type { CaseView } from '../contracts/caseView'
import { STAGES } from '../contracts/registry'

function validView(value: any, caseId?: string): value is CaseView {
  const record = (v: any) => v !== null && typeof v === 'object' && !Array.isArray(v)
  return value !== null && typeof value === 'object'
    && typeof value.case_id === 'string' && (caseId === undefined || value.case_id === caseId)
    && Number.isSafeInteger(value.case_rev) && value.case_rev >= 0 && STAGES.includes(value.stage)
    && value.manifest_summary !== null && typeof value.manifest_summary === 'object'
    && ['file_count', 'ok_file_count', 'failed_file_count'].every(k => Number.isSafeInteger(value.manifest_summary[k]) && value.manifest_summary[k] >= 0)
    && (value.description === null || typeof value.description === 'string')
    && record(value.hints)
    && ['time', 'vehicle', 'situation', 'location'].every(k => value.hints[k] === null || typeof value.hints[k] === 'string')
    && ['progress', 'candidates', 'running_jobs', 'notices'].every(k => Array.isArray(value[k]) && value[k].every(record))
    && value.progress.every((v: any) => typeof v.step === 'string' && typeof v.state === 'string')
    && value.candidates.every((v: any) => typeof v.candidate_id === 'string' && typeof v.selected === 'boolean')
    && value.running_jobs.every((v: any) => typeof v.job_id === 'string' && typeof v.kind === 'string' && typeof v.label_key === 'string' && typeof v.status === 'string')
    && value.notices.every((v: any) => typeof v.code === 'string' && typeof v.message_key === 'string' && typeof v.severity === 'string' && Array.isArray(v.actions) && v.actions.every((a: any) => typeof a === 'string'))
}

export interface OfficialSample {
  sample_id: string
  label: string
  example_hint: string
  duration_ms: number
  byte_size: number
  file_count: number
}
export function createPublicSamplesApi(options: { fetch?: typeof fetch } = {}) {
  const transport = options.fetch ?? ((...args: Parameters<typeof fetch>) => fetch(...args))
  // Same-origin browser cookies only. This adapter does not accept a URL or session token.
  const authenticated: typeof fetch = (input, init) => transport(input, { ...init, credentials: 'same-origin' })
  const original = createApi({ fetch: authenticated })
  const failed = (status: number, code: string): ApiResult<never> => ({
    ok: false, status, error: { code, message_key: code }, caseView: null,
  })
  function checkedView(result: ApiResult<CaseView>, id: string): ApiResult<CaseView> {
    if (result.ok) return validView(result.data, id) ? result : failed(result.status, INVALID_RESPONSE)
    return result.caseView && !validView(result.caseView, id) ? failed(result.status, INVALID_RESPONSE) : result
  }
  const cases = {
    ...original,
    async createCase() {
      const result = await original.createCase()
      return result.ok && (!result.data || typeof result.data.case_id !== 'string' || !validView(result.data.case_view, result.data.case_id))
        ? failed(result.status, INVALID_RESPONSE) : result
    },
    getView: async (id: string) => checkedView(await original.getView(id), id),
    sendCommand: async (...args: Parameters<typeof original.sendCommand>) => checkedView(await original.sendCommand(...args), args[0]),
  }
  async function call<T>(url: string, init?: RequestInit, bounded = true): Promise<ApiResult<T>> {
    let response: Response
    try { response = await authenticated(url, { ...init, signal: bounded ? AbortSignal.timeout(15000) : undefined, cache: 'no-store' }) }
    catch { return failed(0, NETWORK_ERROR) }
    let body: any
    try { body = await response.json() } catch { return failed(response.status, INVALID_RESPONSE) }
    if (response.ok) return { ok: true, status: response.status, data: body as T }
    if (typeof body?.error?.code !== 'string' || typeof body?.error?.message_key !== 'string') return failed(response.status, INVALID_RESPONSE)
    return { ok: false, status: response.status, error: body.error, caseView: body.case_view ?? null }
  }
  return {
    cases,
    async intakeMode() {
      const result = await call<{ upload_enabled: boolean }>('/public/intake-mode')
      return result.ok && typeof result.data?.upload_enabled !== 'boolean'
        ? failed(result.status, INVALID_RESPONSE) : result
    },
    async listSamples(): Promise<ApiResult<{ samples: OfficialSample[] }>> {
      const result = await call<{ samples: OfficialSample[] }>('/public/samples')
      if (!result.ok) return result
      const values = result.data?.samples
      if (!Array.isArray(values) || !values.every(s =>
        s !== null && typeof s === 'object' && typeof s.sample_id === 'string' && /^[a-z0-9][a-z0-9_-]{0,63}$/.test(s.sample_id)
        && typeof s.label === 'string' && typeof s.example_hint === 'string'
        && Number.isInteger(s.duration_ms) && s.duration_ms > 0 && s.duration_ms <= 600000
        && Number.isSafeInteger(s.byte_size) && s.byte_size > 0
        && Number.isInteger(s.file_count) && s.file_count > 0 && s.file_count <= 64)
        || new Set(values.map(s => s.sample_id)).size !== values.length) return failed(result.status, INVALID_RESPONSE)
      return result
    },
    async ensureSession() {
      const result = await call<{ ok: true }>('/public/session', { method: 'POST' })
      return result.ok && result.data?.ok !== true ? failed(result.status, INVALID_RESPONSE) : result
    },
    async registerSample(caseId: string, sampleId: string) {
      const result = await call<{ case_id: string; case_view: CaseView }>(`/cases/${encodeURIComponent(caseId)}/official-samples`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sample_id: sampleId }),
      })
      return result.ok && (!result.data || result.data.case_id !== caseId || !validView(result.data.case_view, caseId))
        ? failed(result.status, INVALID_RESPONSE) : result
    },
    async uploadBundle(caseId: string, files: File[]) {
      const form = new FormData()
      for (const file of files) form.append('file', file)
      const result = await call<{ case_id: string; case_view: CaseView }>(`/cases/${encodeURIComponent(caseId)}/official-uploads`,
        { method: 'POST', body: form }, false)
      return result.ok && (!result.data || result.data.case_id !== caseId || !validView(result.data.case_view, caseId))
        ? failed(result.status, INVALID_RESPONSE) : result
    },
    deleteCase: (caseId: string) => call<{ state: 'DELETING' | 'DELETED' }>(`/cases/${encodeURIComponent(caseId)}`, { method: 'DELETE' }),
  }
}
export type PublicSamplesApi = ReturnType<typeof createPublicSamplesApi>
