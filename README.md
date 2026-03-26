# QuizPDF QCM (Arabic + French)

موقع جاهز للنشر على Render لتحويل ملفات PDF إلى أسئلة QCM عالية الجودة.

## المميزات
- رفع PDF واستخراج النص تلقائيًا
- توليد أسئلة QCM بالعربية أو الفرنسية
- 4 اختيارات لكل سؤال
- إجابة صحيحة + تفسير مختصر
- واجهة ثنائية اللغة
- جاهز للنشر على Render

## تشغيل محلي
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# ضع مفتاح OpenAI API داخل .env
python app.py
```

## النشر على Render
1. ارفع المشروع إلى GitHub
2. من Render اختر New > Blueprint
3. اختر المستودع
4. أضف متغير البيئة OPENAI_API_KEY
5. اضغط Deploy

أو يمكنك رفع الملفات مباشرة كـ Web Service واستخدام:
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`

## ملاحظات
- الملفات المصورة فقط قد تحتاج OCR مستقبلاً.
- جودة الأسئلة تعتمد على جودة النص داخل PDF.
- يوجد endpoint للفحص الصحي: `/health`
