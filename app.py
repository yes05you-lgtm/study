import io
import os
import re
import math
import json
import logging
import pandas as pd
from pypdf import PdfReader
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("lecture-note-builder")

app = Flask(__name__)

def get_clean_env(key, default=""):
    val = os.getenv(key, default)
    if val is None:
        return default
    cleaned = str(val).strip().strip('"').strip("'").strip()
    return cleaned if cleaned else default

DEPRECATED_MODELS = {
    "gemini-2.5-flash", "models/gemini-2.5-flash",
    "gemini-2.0-flash", "models/gemini-2.0-flash",
    "gemini-1.5-flash", "models/gemini-1.5-flash"
}

def get_model_name():
    name = get_clean_env("GEMINI_MODEL", "gemini-3.8-flash")
    if not name or name in DEPRECATED_MODELS:
        return "gemini-3.8-flash"
    return name

GEMINI_API_KEY = get_clean_env("GEMINI_API_KEY")
GEMINI_MODEL = get_model_name()
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", 20))
ACCESS_PIN = get_clean_env("ACCESS_PIN", "0909")

app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# 메모리에 현재 업로드된 강의 자료 보관
current_lecture = {}


def extract_text_from_pdf(file_bytes):
    """PDF 바이트 데이터에서 페이지별 텍스트를 추출하고 통계를 생성"""
    reader = PdfReader(io.BytesIO(file_bytes))
    num_pages = len(reader.pages)
    pages_text = []
    full_text = ""
    page_stats = []

    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.strip()
        pages_text.append({"page": idx + 1, "text": text})
        full_text += f"\n--- [Page {idx + 1}] ---\n" + text
        word_count = len(text.split())
        char_count = len(text)
        page_stats.append({
            "page": idx + 1,
            "char_count": char_count,
            "word_count": word_count
        })

    # Pandas를 이용한 통계 계산
    df_stats = pd.DataFrame(page_stats)
    total_chars = int(df_stats["char_count"].sum())
    total_words = int(df_stats["word_count"].sum())
    avg_chars = round(float(df_stats["char_count"].mean()), 1) if num_pages > 0 else 0
    empty_pages = int((df_stats["char_count"] == 0).sum())

    # 숫자나 표가 포함된 페이지 탐지
    numeric_pattern = re.compile(r'\b\d+(\.\d+)?%?\b')
    pages_with_numbers = []
    for p in pages_text:
        nums = numeric_pattern.findall(p["text"])
        if len(nums) >= 3:
            pages_with_numbers.append(p["page"])

    return {
        "num_pages": num_pages,
        "full_text": full_text,
        "pages_text": pages_text,
        "total_chars": total_chars,
        "total_words": total_words,
        "avg_chars_per_page": avg_chars,
        "empty_pages": empty_pages,
        "pages_with_numbers": pages_with_numbers,
        "page_stats": page_stats
    }


def extract_numbers_summary(text):
    """강의 자료 내 포함된 주요 숫자/통계/비율 데이터를 Pandas로 집계"""
    # 백분율(%), 연도, 일반 수치 패턴 추출
    pct_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', text)
    year_matches = re.findall(r'\b(19\d\d|20\d\d)\b', text)
    
    summary = {}
    if pct_matches:
        s_pct = pd.Series([float(x) for x in pct_matches])
        summary["percentages"] = {
            "count": int(len(s_pct)),
            "min": float(s_pct.min()),
            "max": float(s_pct.max()),
            "mean": round(float(s_pct.mean()), 2),
            "samples": [f"{x}%" for x in s_pct.head(5).tolist()]
        }

    if year_matches:
        s_year = pd.Series([int(x) for x in year_matches])
        summary["years"] = {
            "count": int(len(s_year)),
            "min": int(s_year.min()),
            "max": int(s_year.max()),
            "common_years": s_year.value_counts().head(3).to_dict()
        }

    return summary


@app.route("/", methods=["GET"])
def index():
    logger.info("[REQUEST] GET /")
    return render_template("index.html")


@app.route("/api/verify_pin", methods=["POST"])
def verify_pin():
    """클라이언트가 입력한 PIN 코드가 일치하는지 검증"""
    req_json = request.get_json(silent=True) or {}
    client_pin = str(req_json.get("pin", "")).strip()
    logger.info("[REQUEST] POST /api/verify_pin")
    if client_pin == ACCESS_PIN:
        return jsonify({"status": "success", "message": "인증에 성공했습니다."}), 200
    return jsonify({"status": "error", "error": "비밀번호가 올바르지 않습니다."}), 401


PROTECTED_ENDPOINTS = {"/inspect", "/cornell_notes", "/quiz", "/chat"}


@app.before_request
def check_pin_auth():
    """핵심 API에 대해 4자리 입장 비밀번호 헤더(X-Access-Pin) 검증"""
    if request.path in PROTECTED_ENDPOINTS:
        client_pin = request.headers.get("X-Access-Pin", "").strip()
        if client_pin != ACCESS_PIN:
            logger.warning(f"[AUTH] 비인가 요청 차단: path={request.path}")
            return jsonify({
                "status": "unauthorized",
                "error": "접근 권한이 없습니다. 4자리 입장 비밀번호를 입력해주세요."
            }), 401


@app.route("/health", methods=["GET"])
def health():
    logger.info("[REQUEST] GET /health")
    has_api_key = bool(GEMINI_API_KEY and GEMINI_API_KEY.strip() and GEMINI_API_KEY != "your_gemini_api_key_here")
    return jsonify({
        "status": "ok",
        "has_api_key": has_api_key,
        "model": GEMINI_MODEL
    })


@app.route("/inspect", methods=["POST"])
def inspect_pdf():
    """PDF 강의자료 업로드 및 기본 텍스트/통계 진단"""
    logger.info("[REQUEST] POST /inspect (PDF 강의자료 진단)")

    if "file" not in request.files:
        return jsonify({"error": "강의 자료 파일(PDF)을 선택해주세요."}), 400

    uploaded_file = request.files["file"]
    if not uploaded_file or uploaded_file.filename == "":
        return jsonify({"error": "파일이 선택되지 않았습니다."}), 400

    filename = uploaded_file.filename
    if not filename.lower().endswith(".pdf"):
        return jsonify({"error": "강의 자료는 PDF 형식(.pdf)만 업로드 가능합니다."}), 400

    file_bytes = uploaded_file.read()
    file_size = len(file_bytes)
    logger.info(f"[FILE] name={filename} size={file_size} bytes")

    if file_size == 0:
        return jsonify({"error": "내용이 비어 있는 빈 파일입니다."}), 400

    try:
        extracted = extract_text_from_pdf(file_bytes)
    except Exception as e:
        logger.error(f"[ERROR] PDF 파싱 실패: {e}", exc_info=True)
        return jsonify({"error": f"PDF 파일을 분석하는 중 오류가 발생했습니다: {str(e)}"}), 400

    if extracted["total_chars"] == 0:
        return jsonify({"error": "PDF에서 텍스트를 추출할 수 없습니다. (스캔된 이미지 전용 PDF일 수 있습니다)"}), 400

    # 숫자 집계
    num_summary = extract_numbers_summary(extracted["full_text"])

    # 메모리에 보관
    current_lecture.clear()
    current_lecture["filename"] = filename
    current_lecture["extracted"] = extracted
    current_lecture["num_summary"] = num_summary

    # 차트용 데이터 (페이지별 단어수 분포)
    chart_data = {
        "type": "bar",
        "labels": [f"{s['page']}p" for s in extracted["page_stats"][:20]],
        "datasets": [{
            "label": "페이지별 텍스트 분량 (단어 수)",
            "data": [s["word_count"] for s in extracted["page_stats"][:20]],
            "backgroundColor": "#4f46e5"
        }]
    }

    warnings = []
    if extracted["empty_pages"] > 0:
        warnings.append(f"텍스트가 없는 빈 페이지가 {extracted['empty_pages']}장 포함되어 있습니다.")
    if extracted["avg_chars_per_page"] < 50:
        warnings.append("페이지당 텍스트 분량이 매우 적습니다. 다이어그램 위주의 자료일 수 있습니다.")

    return jsonify({
        "status": "success",
        "filename": filename,
        "file_size": file_size,
        "num_pages": extracted["num_pages"],
        "total_chars": extracted["total_chars"],
        "total_words": extracted["total_words"],
        "avg_chars_per_page": extracted["avg_chars_per_page"],
        "numeric_summary": num_summary,
        "warnings": warnings,
        "chart_data": chart_data,
        "preview_pages": extracted["pages_text"][:3]
    }), 200


@app.route("/cornell_notes", methods=["POST"])
def generate_cornell_notes():
    """강의 자료 텍스트를 기반으로 표준 코넬식 노트 필기(Cornell Notes) 생성"""
    logger.info("[REQUEST] POST /cornell_notes (코넬식 노트 생성)")

    global current_lecture
    if not current_lecture or "extracted" not in current_lecture:
        return jsonify({"error": "먼저 강의 자료(PDF)를 업로드해주세요."}), 400

    api_key = get_clean_env("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        return jsonify({"error": "Gemini API Key가 설정되지 않았습니다."}), 400

    model_name = get_model_name()
    extracted = current_lecture["extracted"]
    num_summary = current_lecture.get("num_summary", {})

    # 긴 문서는 최대 30,000자로 요약 클립
    text_content = extracted["full_text"][:35000]

    prompt = f"""
당신은 최고의 명문대 수석 학습 코치이자 강의 자료 정리 전문가입니다.
사용자가 업로드한 강의 자료 전문을 정밀 분석하여, 학생들이 시험 직전과 복습에 가장 효율적으로 활용할 수 있는 **[코넬식 노트(Cornell Notes)]** 포맷으로 완벽히 정리해주세요.

[강의 자료 개요]
- 강의 파일명: {current_lecture['filename']}
- 총 페이지 수: {extracted['num_pages']}장 (총 단어 수: {extracted['total_words']})
- 포함된 주요 수치 지표: {json.dumps(num_summary, ensure_ascii=False)}

[강의 내용 원문 발췌]
{text_content}

---

[코넬식 노트(Cornell Notes) 작성 지침]
코넬식 노트의 표준 3분할 구조를 지켜 JSON 형식으로 작성해주세요:

1. **cue_column (단서/키워드/핵심 질문 영역 - 좌측)**:
   - 복습할 때 질문을 보고 우측 노트를 가리고 답할 수 있는 날카로운 핵심 질문 5~8개
   - 각 질문에 매핑되는 필수 암기 핵심 개념어(Keywords)

2. **notes_column (본문 필기/상세 정리 영역 - 우측)**:
   - 각 단서/질문에 대응하는 체계적인 본문 정리
   - 강의 내용의 핵심 개념, 정의, 원리, 작동 과정, 예시
   - 번호 매기기(Bullet points), 강조(Bold), 비교 대조 구조화
   - 중요한 통계/숫자가 있다면 정확히 인용

3. **summary_column (하단 최종 요약 영역 - 하단)**:
   - 이 강의 자료 전체를 3~5문장으로 압축한 핵심 테제 요약
   - "이 강의에서 반드시 가져가야 할 핵심 교훈 3가지"

4. **key_terms (용어 사전)**:
   - 시험에 출제될 수 있는 전문 용어 4~6개의 명확한 1줄 정의

반드시 다음 JSON 형식으로만 응답하세요:
{{
  "title": "강의 주제 제목",
  "cornell_notes": [
    {{
      "cue_question": "복습용 핵심 질문 (예: 머신러닝의 과적합(Overfitting)이란 무엇이며 왜 발생하는가?)",
      "cue_keyword": "핵심 개념어 (예: 과적합, 일반화 오차)",
      "notes_content": "상세한 본문 필기 내용 (개념 정의, 원인, 해결책 등을 읽기 쉽게 구조화)"
    }}
  ],
  "summary": "강의 전체를 아우르는 3~5줄 최종 요약",
  "key_takeaways": [
    "핵심 교훈 1",
    "핵심 교훈 2",
    "핵심 교훈 3"
  ],
  "vocabulary": [
    {{"term": "용어명", "definition": "쉬운 1줄 정의"}}
  ]
}}
"""

    logger.info(f"[AI] 코넬식 노트 생성 요청 (model={model_name})")

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        logger.info("[AI] 코넬식 노트 응답 수신 완료")

        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\n?", "", raw_text)
            raw_text = re.sub(r"\n?```$", "", raw_text)

        result_json = json.loads(raw_text)

        current_lecture["last_notes"] = result_json

        return jsonify({
            "status": "success",
            "model": model_name,
            "data": result_json
        }), 200

    except Exception as e:
        logger.error(f"[ERROR] 코넬 노트 생성 실패: {e}", exc_info=True)
        return jsonify({"error": f"코넬식 노트를 생성하는 중 오류가 발생했습니다: {str(e)}"}), 500


@app.route("/quiz", methods=["POST"])
def generate_quiz():
    """강의 자료 기반 복습용 시험 예상 문제 (객관식 & 서술형) 생성"""
    logger.info("[REQUEST] POST /quiz (예상 문제 생성)")

    global current_lecture
    if not current_lecture or "extracted" not in current_lecture:
        return jsonify({"error": "먼저 강의 자료를 업로드해주세요."}), 400

    api_key = get_clean_env("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "Gemini API Key가 필요합니다."}), 400

    model_name = get_model_name()
    extracted = current_lecture["extracted"]

    prompt = f"""
당신은 대학교 교수이자 출제 위원입니다.
아래 강의 자료 원문을 바탕으로, 학생들의 학습 이해도를 점검할 수 있는 **[복습 시험 문제 5문항]**을 출제해주세요.

[강의 원문 발췌]
{extracted['full_text'][:30000]}

[출제 기준]
- 객관식 3문항 (4지선다, 정답 번호, 상세 해설 포함)
- 서술형/단답형 2문항 (모범 답안 및 채점 기준 포함)

반드시 다음 JSON 형식으로만 응답하세요:
{{
  "quizzes": [
    {{
      "type": "multiple_choice",
      "question": "문제 내용",
      "options": ["1번 보기", "2번 보기", "3번 보기", "4번 보기"],
      "answer_index": 0,
      "explanation": "해설"
    }},
    {{
      "type": "short_answer",
      "question": "서술형 문제 내용",
      "model_answer": "모범 답안",
      "grading_criteria": "채점 기준"
    }}
  ]
}}
"""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\n?", "", raw_text)
            raw_text = re.sub(r"\n?```$", "", raw_text)

        quiz_data = json.loads(raw_text)
        return jsonify({
            "status": "success",
            "data": quiz_data
        }), 200

    except Exception as e:
        logger.error(f"[ERROR] 퀴즈 생성 실패: {e}", exc_info=True)
        return jsonify({"error": f"문제 생성 중 오류가 발생했습니다: {str(e)}"}), 500


@app.route("/chat", methods=["POST"])
def chat_with_lecture():
    """강의 자료 및 코넬 노트를 기반으로 사용자의 질문에 답변하는 대화형 질의응답"""
    logger.info("[REQUEST] POST /chat (강의 Q&A 질문)")

    global current_lecture
    if not current_lecture or "extracted" not in current_lecture:
        return jsonify({"error": "먼저 강의 자료를 업로드해주세요."}), 400

    api_key = get_clean_env("GEMINI_API_KEY")
    if not api_key:
        return jsonify({"error": "Gemini API Key가 필요합니다."}), 400

    model_name = get_model_name()
    req_json = request.get_json(silent=True) or {}
    user_message = req_json.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "질문 내용을 입력해주세요."}), 400

    extracted = current_lecture["extracted"]
    notes_summary = json.dumps(current_lecture.get("last_notes", {}), ensure_ascii=False)

    prompt = f"""
당신은 학생이 업로드한 강의 자료의 내용을 완벽하게 숙지하고 있는 친절한 전담 AI 튜터입니다.
학생이 방금 정리된 강의 내용과 코넬식 노트를 보면서 궁금한 점을 질문했습니다.

[강의 원문 발췌 (앞부분 25,000자)]
{extracted['full_text'][:25000]}

[정리된 코넬식 노트 요약]
{notes_summary[:5000]}

[학생의 질문]
"{user_message}"

[답변 지침 - 가독성 극대화]
1. 단순 줄글이 아닌, 가독성이 뛰어난 구조화된 마크다운으로 작성하세요.
2. 중요한 핵심 개념, 키워드, 법칙은 반드시 **볼드체** 또는 `인라인 코드`로 강조하세요.
3. 단계별 설명이나 주요 특징은 숫자 리스트(1, 2, 3) 또는 글머리 기호(bullet points)로 일목요연하게 정리하세요.
4. 핵심 요약이나 시험 꿀팁, 주의사항이 있다면 다음 인용구 박스를 활용해 시각적으로 돋보이게 하세요:
   > 💡 **핵심 포인트:** 중요한 개념 요약
   또는
   > ⚠️ **주의할 점 / 시험 빈출:** 헷갈리기 쉬운 부분
5. 친절하고 명쾌하게 중학생도 이해할 수 있는 쉬운 비유와 예시를 곁들여 설명하세요.

"""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3)
        )
        return jsonify({
            "status": "success",
            "reply": response.text.strip()
        }), 200

    except Exception as e:
        logger.error(f"[ERROR] 채팅 답변 생성 실패: {e}", exc_info=True)
        return jsonify({"error": f"답변을 생성하는 중 오류가 발생했습니다: {str(e)}"}), 500



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Study Note Server on port {port}... Debug={FLASK_DEBUG}, Model={GEMINI_MODEL}")
    app.run(host="0.0.0.0", port=port, debug=FLASK_DEBUG)

