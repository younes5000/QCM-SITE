import io
import json
import os
import re
from typing import Dict

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI
from pypdf import PdfReader

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB

SUPPORTED_LANGS = {
    "ar": {
        "label": "العربية",
        "dir": "rtl",
        "system_prompt": """
You are an expert assessment designer.
Create high-quality Arabic multiple-choice questions (QCM/MCQ) from the lesson text.
Rules:
1) Base questions only on the supplied lesson.
2) Questions should test understanding, not only memorization.
3) Use clear Modern Standard Arabic.
4) Provide exactly 4 choices per question.
5) Only one correct answer per question.
6) Include a short explanation for why the answer is correct.
7) Mix difficulty levels: easy, medium, hard.
8) Avoid duplicate or trivial questions.
9) Output strict JSON only in this shape:
{
  "title": "string",
  "questions": [
    {
      "question": "string",
      "choices": ["A", "B", "C", "D"],
      "correct_index": 0,
      "explanation": "string",
      "difficulty": "easy|medium|hard"
    }
  ]
}
""".strip(),
        "user_prompt": "أنشئ {count} أسئلة اختيار من متعدد عالية الجودة من الدرس التالي. اجعل الصياغة بالعربية.",
    },
    "fr": {
        "label": "Français",
        "dir": "ltr",
        "system_prompt": """
You are an expert assessment designer.
Create high-quality French multiple-choice questions (QCM/MCQ) from the lesson text.
Rules:
1) Base questions only on the supplied lesson.
2) Questions should test understanding, not only memorization.
3) Use clear academic French.
4) Provide exactly 4 choices per question.
5) Only one correct answer per question.
6) Include a short explanation for why the answer is correct.
7) Mix difficulty levels: easy, medium, hard.
8) Avoid duplicate or trivial questions.
9) Output strict JSON only in this shape:
{
  "title": "string",
  "questions": [
    {
      "question": "string",
      "choices": ["A", "B", "C", "D"],
      "correct_index": 0,
      "explanation": "string",
      "difficulty": "easy|medium|hard"
    }
  ]
}
""".strip(),
        "user_prompt": "Crée {count} questions QCM de haute qualité à partir de la leçon suivante. Rédige toutes les questions en français.",
    },
}


def extract_pdf_text(file_stream: io.BytesIO) -> str:
    reader = PdfReader(file_stream)
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    text = "\n".join(pages)
    text = re.sub(r"\s+", " ", text).strip()
    return text



def chunk_text(text: str, max_chars: int = 18000) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.3):]
    return head + "\n\n[...content truncated for model budget...]\n\n" + tail



def normalize_quiz_payload(data: Dict) -> Dict:
    questions = data.get("questions", [])
    cleaned = []
    for q in questions:
        choices = q.get("choices", [])[:4]
        if len(choices) < 4:
            continue
        correct_index = q.get("correct_index", 0)
        try:
            correct_index = int(correct_index)
        except Exception:
            correct_index = 0
        correct_index = max(0, min(correct_index, 3))
        difficulty = str(q.get("difficulty", "medium")).lower()
        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "medium"
        cleaned.append(
            {
                "question": str(q.get("question", "")).strip(),
                "choices": [str(c).strip() for c in choices],
                "correct_index": correct_index,
                "explanation": str(q.get("explanation", "")).strip(),
                "difficulty": difficulty,
            }
        )

    return {
        "title": str(data.get("title", "Quiz")).strip() or "Quiz",
        "questions": cleaned,
    }



def generate_questions(lesson_text: str, question_count: int = 10, language: str = "ar") -> Dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    language = language if language in SUPPORTED_LANGS else "ar"
    lang_meta = SUPPORTED_LANGS[language]

    client = OpenAI(api_key=api_key)
    content = chunk_text(lesson_text)

    prompt = f"""
{lang_meta['user_prompt'].format(count=question_count)}

الدرس / Leçon:
{content}
""".strip()

    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
        input=[
            {"role": "system", "content": lang_meta["system_prompt"]},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    raw_text = response.output_text
    data = json.loads(raw_text)
    return normalize_quiz_payload(data)


@app.get('/')
def index():
    return render_template('index.html', languages=SUPPORTED_LANGS)


@app.get('/health')
def health():
    return jsonify({"status": "ok"})


@app.post('/api/generate')
def api_generate():
    if 'pdf' not in request.files:
        return jsonify({"error": "يرجى رفع ملف PDF / Veuillez téléverser un PDF."}), 400

    file = request.files['pdf']
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "الملف يجب أن يكون بصيغة PDF / Le fichier doit être au format PDF."}), 400

    try:
        file_bytes = io.BytesIO(file.read())
        text = extract_pdf_text(file_bytes)
        if len(text) < 100:
            return jsonify({"error": "تعذر استخراج نص كافٍ من ملف PDF / Impossible d'extraire suffisamment de texte du PDF."}), 400

        question_count = int(request.form.get('question_count', 10))
        question_count = max(5, min(question_count, 25))
        language = request.form.get('language', 'ar').strip().lower()
        result = generate_questions(text, question_count, language)
        result['language'] = language if language in SUPPORTED_LANGS else 'ar'
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({"error": "فشل في قراءة استجابة النموذج. حاول مرة أخرى / Échec de lecture de la réponse du modèle. Réessayez."}), 500
    except Exception as e:
        return jsonify({"error": f"حدث خطأ / Une erreur s'est produite: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
