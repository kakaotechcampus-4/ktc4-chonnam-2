import sys,json,time,random,re,unicodedata
from pathlib import Path
sys.path.insert(0,r'C:\tmp\paddle-ocr')
from paddleocr import TextRecognition
IMG=Path(r'C:\Users\ymshin\Downloads\자동차 차종-연식-번호판 인식용 영상\Validation\[원천]자동차번호판OCR데이터')
LAB=Path(r'C:\Users\ymshin\Downloads\자동차 차종-연식-번호판 인식용 영상\Validation\[라벨]자동차번호판OCR_valid')
OUT=Path(r'C:\Users\ymshin\Documents\카테캠\ocr-dataset-eval')
def norm(s): return re.sub(r'[\s\-_·.]','',unicodedata.normalize('NFC',str(s))).upper()
def valid(s):
 s=norm(s)
 return bool(re.fullmatch(r'(?:\d{2,3}[가-힣]\d{4}|[가-힣]{2}\d{1,2}[가-힣]\d{4})',s))
def lev(a,b):
 prev=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  cur=[i]
  for j,y in enumerate(b,1):cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
  prev=cur
 return prev[-1]
labels=[]
for p in LAB.glob('*.json'):
 try:
  o=json.loads(p.read_text(encoding='utf-8')); ip=IMG/o['imagePath']
  if ip.exists(): labels.append((ip,norm(o['value']),o['id']))
 except Exception: pass
random.Random(20260915).shuffle(labels); sample=labels[:500]
model=TextRecognition(model_name='korean_PP-OCRv5_mobile_rec',enable_mkldnn=False)
rows=[]; start=time.time()
for offset in range(0,len(sample),32):
 batch=sample[offset:offset+32]
 results=list(model.predict([str(x[0]) for x in batch],batch_size=len(batch)))
 for (p,truth,rid),res in zip(batch,results):
  rr=res.json['res']; pred=norm(rr.get('rec_text','')); score=float(rr.get('rec_score',0) or 0)
  rows.append({'file':p.name,'id':rid,'truth':truth,'prediction':pred,'score':score,'exact':pred==truth,'format_valid':valid(pred),'edit_distance':lev(truth,pred),'truth_length':len(truth)})
 print(f'PROGRESS={len(rows)}/500 ELAPSED={time.time()-start:.1f}',flush=True)
thresholds=[0,.5,.6,.7,.8,.9,.95,.98]
def calc(t,use_format):
 acc=[r for r in rows if r['score']>=t and (r['format_valid'] or not use_format)]
 wrong=[r for r in acc if not r['exact']]
 return {'threshold':t,'format_gate':use_format,'accepted':len(acc),'coverage':len(acc)/len(rows),'correct':len(acc)-len(wrong),'wrong_accepts':len(wrong),'wrong_accept_rate_all':len(wrong)/len(rows),'accepted_precision':(len(acc)-len(wrong))/len(acc) if acc else None}
summary={'sample_size':len(rows),'seed':20260915,'elapsed_seconds':time.time()-start,'exact_count':sum(r['exact'] for r in rows),'exact_accuracy':sum(r['exact'] for r in rows)/len(rows),'cer':sum(r['edit_distance'] for r in rows)/sum(r['truth_length'] for r in rows),'empty_predictions':sum(not r['prediction'] for r in rows),'format_valid_predictions':sum(r['format_valid'] for r in rows),'mean_confidence':sum(r['score'] for r in rows)/len(rows),'thresholds_confidence_only':[calc(t,False) for t in thresholds],'thresholds_with_format_gate':[calc(t,True) for t in thresholds]}
(OUT/'paddleocr_500_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'paddleocr_500_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print('SUMMARY='+json.dumps(summary,ensure_ascii=True))
