import sys,json,time
from pathlib import Path
sys.path.insert(0,r'C:\tmp\paddle-ocr')
from paddleocr import TextRecognition
imgdir=Path(r'C:\Users\ymshin\Downloads\자동차 차종-연식-번호판 인식용 영상\Validation\[원천]자동차번호판OCR데이터')
paths=sorted(imgdir.glob('*.jpg'))[:10]
model=TextRecognition(model_name='korean_PP-OCRv5_mobile_rec',enable_mkldnn=False)
t=time.time(); results=list(model.predict([str(p) for p in paths],batch_size=10)); print('SECONDS',time.time()-t,'N',len(results))
for p,r in zip(paths,results): print(p.name,json.dumps(r.json,ensure_ascii=False)[:500])
