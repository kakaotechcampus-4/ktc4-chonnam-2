import sys
sys.path.insert(0, r"C:\tmp\paddle-ocr")
from paddleocr import PaddleOCR

ocr = PaddleOCR(lang="korean", text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
                enable_mkldnn=False,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False, use_textline_orientation=False)
path = r"C:\Users\ymshin\Documents\카테캠\ocr-test\20260806_192353_EVT_1\frame_12_010.42s.jpg"
for item in ocr.predict(path):
    print(item.json)
