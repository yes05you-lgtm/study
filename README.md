# 🎓 Study Note AI (스마트 강의 자료 요약 & 코넬식 노트)

> 강의 자료(PDF)를 업로드하면 **코넬식 노트(Cornell Notes)**로 자동 정리하고, **AI 튜터 실시간 Q&A** 및 **복습 퀴즈**를 제공하는 AI 학습 보조 웹 서비스입니다.

---

## 🌟 주요 기능

### 1. 📄 PDF 강의 자료 자동 추출 & 분석
- 슬라이드, 교재, 강의록 PDF를 업로드하면 텍스트를 추출하고 페이지/단어 통계를 계산합니다.
- 업로드된 파일은 서버 디스크에 저장되지 않고 메모리에서 안전하게 처리됩니다.

### 2. 📝 코넬식 노트(Cornell Notes) 자동 생성
- **단서 영역 (Cue Questions)**: 핵심 질문과 키워드를 좌측에 배치하여 가리고 복습할 수 있는 환경 제공
- **필기 영역 (Notes)**: 핵심 개념, 정의, 단계별 상세 내용을 구조화하여 정리
- **요약 영역 (Summary)**: 강의 전체의 핵심 요약과 꼭 기억할 3가지 교훈(Takeaways) 제공
- **필수 어휘 사전 (Glossary)**: 시험 전 필수 암기 키워드 카드 제공
- **인쇄 및 PDF 저장**: 브라우저 인쇄 기능을 통해 깔끔하게 출력 및 PDF 저장 가능

### 3. 💬 AI 학습 튜터와의 1:1 실시간 Q&A
- 업로드된 강의 내용에 대해 궁금한 점이나 어려운 개념을 자유롭게 질문
- 학생 눈높이에 맞춘 친절한 설명, 비유 및 마크다운 기반의 시각적 가독성 제공

### 4. 🎯 자가 진단 복습 퀴즈
- 학습한 강의 자료를 바탕으로 예상 객관식/주관식 문제 출제
- 보기를 클릭하여 즉시 정답 및 상세 해설 확인 가능

---

## 🛠️ 기술 스택

- **Backend**: Python 3.10+, Flask
- **AI Model**: Google Gemini API (`google-genai`, `gemini-2.5-flash` / `gemini-3.8-flash`)
- **Document Processing**: `pypdf`, `pandas`
- **Frontend**: HTML5, Modern CSS (Responsive), Vanilla JavaScript, Marked.js (Markdown 렌더링)

---

## 📁 프로젝트 구조

```text
C:\AI-study\study\
├── app.py              # Flask 메인 애플리케이션 및 Gemini API 연동 라우트
├── tools.py            # 데이터 분석 및 도구 함수 모음
├── templates/
│   └── index.html      # 반응형 단일 페이지 웹 인터페이스
├── static/
│   ├── style.css       # 모던 디자인 시스템 및 코넬식 레이아웃 스타일시트
│   └── app.js          # 파일 업로드, API 비동기 통신, 퀴즈/채팅 클라이언트 로직
├── requirements.txt    # 파이썬 의존성 패키지 목록
├── .env.example        # 환경 변수 설정 예시
├── .gitignore          # Git 추적 제외 설정 (가상환경, .env 등)
└── README.md           # 프로젝트 안내 문서
```

---

## 🚀 빠른 시작 가이드 (Getting Started)

### 1. 필수 조건
- Python 3.10 이상
- Google Gemini API Key ([Google AI Studio](https://aistudio.google.com/)에서 발급)

### 2. 가상환경 생성 및 활성화

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

프로젝트 루트 디렉터리에 `.env` 파일을 생성하고 아래와 같이 설정합니다:

```env
# Gemini API 설정
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Flask 서버 설정
FLASK_DEBUG=true
MAX_UPLOAD_MB=20
```

### 5. 서버 실행

```bash
python app.py
```

### 6. 웹 브라우저 접속

웹 브라우저를 열고 다음 주소로 이동합니다:
- **[http://localhost:5000](http://localhost:5000)**

---

## 🔒 보안 주의사항
- `.env` 파일에 기록된 API 키는 절대 공개 저장소(GitHub 등)에 커밋하지 마세요.
- 본 프로젝트의 `.gitignore`에는 `.env` 및 가상환경(`.venv`)이 기본적으로 제외 등록되어 있습니다.
