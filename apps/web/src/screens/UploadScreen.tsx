import { useState, type JSX } from 'react'

export type UploadState = 'idle' | 'uploading' | 'done' | 'fail'

const DROP_TEXT: Record<UploadState, string> = {
  idle: '여기에 영상 파일을 끌어다 놓으세요',
  uploading: '올리는 중',
  done: '올리기 완료',
  fail: '업로드 실패',
}

// Figma 01_Home_Upload · 01_Uploading · 01_UploadComplete · 01_UploadFail.
// 네 프레임은 같은 틀이고 끌어다 놓는 영역만 상태에 따라 바뀐다.
export function UploadScreen(props: {
  state: UploadState
  file: File | null
  situation: string
  onFile: (file: File) => void
  onSituation: (text: string) => void
  onSearch: () => void
}): JSX.Element {
  const [over, setOver] = useState(false)
  const pick = (files: FileList | null) => {
    if (files?.[0]) props.onFile(files[0])
  }

  return (
    <div className="stack">
      <div>
        <h1 className="page-title">블랙박스 영상을 올려주세요</h1>
        <p className="kv-src">여러 파일을 한 번에 올리셔도 됩니다. 촬영 시각은 파일에서 자동으로 읽습니다.</p>
      </div>
      <label
        className={`dropzone dz-${props.state}${over ? ' over' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          pick(e.dataTransfer.files)
        }}
      >
        {props.state !== 'idle' && <span className={`dz-ring dz-ring-${props.state}`} aria-hidden />}
        <b>{DROP_TEXT[props.state]}</b>
        {props.file && <span className="kv-src">{props.file.name}</span>}
        {props.state === 'idle' && <span className="btn sm pri">파일 선택</span>}
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
      <button type="button" className="btn pri cta" disabled={props.state !== 'done'} onClick={props.onSearch}>
        영상에서 찾아보기
      </button>
    </div>
  )
}
