import { useState, type JSX } from 'react'

export function UploadScreen(props: {
  file: File | null
  situation: string
  onFile: (file: File | null) => void
  onSituation: (text: string) => void
  onSubmit: () => void
}): JSX.Element {
  const [over, setOver] = useState(false)
  const pick = (files: FileList | null) => props.onFile(files?.[0] ?? null)

  return (
    <div className="stack">
      <div>
        <h1 className="page-title">블랙박스 영상을 올려주세요</h1>
        <p className="kv-src">무슨 일이 있었는지 함께 적어주시면 그 장면을 찾아요.</p>
      </div>
      <label
        className={`dropzone${over ? ' over' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files) }}
      >
        <b>{props.file ? props.file.name : '여기에 영상 파일을 끌어다 놓으세요'}</b>
        <span className="btn sm">파일 선택</span>
        <input type="file" accept="video/*" hidden onChange={(e) => pick(e.target.files)} />
      </label>
      <textarea
        className="field situation"
        rows={4}
        aria-label="어떤 상황이었나요?"
        placeholder="예: 6시 반쯤, 흰색 SUV, 실선 침범, 미금역 근처"
        value={props.situation}
        onChange={(e) => props.onSituation(e.target.value)}
      />
      <button
        type="button"
        className="btn pri cta"
        disabled={!props.file || !props.situation.trim()}
        onClick={props.onSubmit}
      >
        영상에서 찾아보기
      </button>
    </div>
  )
}
