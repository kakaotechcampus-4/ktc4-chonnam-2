import json,re,statistics
from pathlib import Path
from PIL import Image
base=Path(r'C:\Users\ymshin\Documents\카테캠\ocr-dataset-eval'); imgdir=Path(r'C:\Users\ymshin\Downloads\자동차 차종-연식-번호판 인식용 영상\Validation\[원천]자동차번호판OCR데이터')
rows=json.loads((base/'paddleocr_500_results.json').read_text(encoding='utf-8')); s=json.loads((base/'paddleocr_500_summary.json').read_text(encoding='utf-8'))
groups={'wide (w/h>=2.5)':[],'medium (1.3<=w/h<2.5)':[],'tall (w/h<1.3)':[]}
for r in rows:
 with Image.open(imgdir/r['file']) as im:w,h=im.size
 r['width']=w;r['height']=h;r['aspect_ratio']=w/h
 k='wide (w/h>=2.5)' if w/h>=2.5 else ('medium (1.3<=w/h<2.5)' if w/h>=1.3 else 'tall (w/h<1.3)')
 groups[k].append(r)
def pct(x):return f'{100*x:.1f}%'
lines=['# AI Hub 번호판 OCR PaddleOCR 기준선','', '- 데이터: AI Hub 172 번호판 OCR Validation', '- 표본: 고정 seed `20260915`, 500장', '- 모델: `korean_PP-OCRv5_mobile_rec` (번호판 crop에 recognition만 적용)', f"- 실행시간: {s['elapsed_seconds']:.1f}초", f"- Exact Plate Accuracy: **{pct(s['exact_accuracy'])}** ({s['exact_count']}/500)", f"- CER: **{pct(s['cer'])}**", f"- 빈 출력: {s['empty_predictions']}/500", '', '## Threshold 결과', '', '| Gate | Confidence | Coverage | Wrong Accept/전체 | 채택 정밀도 |','|---|---:|---:|---:|---:|']
for gate,key in [('confidence only','thresholds_confidence_only'),('confidence + 번호판 형식','thresholds_with_format_gate')]:
 for x in s[key]:
  if x['threshold'] in (.8,.9,.95,.98):
   ap='-' if x['accepted_precision'] is None else pct(x['accepted_precision'])
   lines.append(f"| {gate} | {x['threshold']:.2f} | {pct(x['coverage'])} ({x['accepted']}/500) | {pct(x['wrong_accept_rate_all'])} ({x['wrong_accepts']}/500) | {ap} |")
lines += ['', '## 이미지 종횡비별 결과','', '| 그룹 | 수 | Exact | CER | 빈 출력 |','|---|---:|---:|---:|---:|']
for k,rs in groups.items():
 exact=sum(x['exact'] for x in rs); cer=sum(x['edit_distance'] for x in rs)/sum(x['truth_length'] for x in rs); empty=sum(not x['prediction'] for x in rs)
 lines.append(f'| {k} | {len(rs)} | {pct(exact/len(rs))} | {pct(cer)} | {empty} |')
wrong=sorted((r for r in rows if not r['exact']),key=lambda x:x['score'],reverse=True)[:15]
lines += ['', '## 높은 confidence 오답 예시','', '| 정답 | 예측 | confidence | 형식 통과 |','|---|---|---:|---:|']
for r in wrong:lines.append(f"| `{r['truth']}` | `{r['prediction'] or '(empty)'}` | {r['score']:.3f} | {'Y' if r['format_valid'] else 'N'} |")
lines += ['', '## 해석','', '1. 이 수치는 PaddleOCR 범용 한국어 모바일 recognizer의 **기준선**이며 프로젝트 목표치가 아니다.', '2. confidence만으로는 0.98에서도 오답이 남았다. 형식 gate와 0.90을 같이 적용한 표본에서는 Wrong Accept 0이었지만 Coverage가 3.6%라 대부분 abstain한다.', '3. crop 종횡비에 따라 성능 차이가 크면 한 줄/두 줄 번호판 분기와 rectification이 필요하다.', '4. 다음 모델 실험은 번호판 전용 recognizer 또는 글자 segmentation, 두 줄 plate layout 분리, multi-frame consensus 순서가 적절하다.', '5. AI Hub 정적 crop은 OCR recognizer sanity용이다. 실제 영상의 detection·tracking·거리·야간 조건은 앞서 확보한 원본 AVI로 별도 C-tier 평가해야 한다.', '', '## 담당 경계','', '- OCR 모델 학습·교체: 모델/OCR 실험 담당', '- 번호판 문자열 정규화·형식 검사·multi-frame 합의·abstain·evidence 전달: readout 담당', '- 실촬영 정답 라벨과 평가 승인: 팀 공동 데이터셋/평가 계획']
(base/'OCR_BASELINE_REPORT_2026-09-15.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(base/'paddleocr_500_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('\n'.join(lines))
