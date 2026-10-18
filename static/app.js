let selectedFile = null;

document.addEventListener("DOMContentLoaded", () => {
  console.log("[PAGE] Study Note AI 로드 완료");
  initHealthCheck();
  initUploadListeners();
  initActionListeners();
});

// 1. 서버 상태 및 API Key 상하 2줄 배지 업데이트
async function initHealthCheck() {
  const serverBadge = document.getElementById("serverBadge");
  const apiKeyBadge = document.getElementById("apiKeyBadge");

  try {
    const res = await fetch("/health");
    const data = await res.json();

    if (data.status === "ok") {
      serverBadge.className = "status-badge connected";
      serverBadge.innerHTML = `
        <span class="badge-title">서버 상태</span>
        <span class="badge-sub">정상 작동중</span>
      `;

      if (data.has_api_key) {
        apiKeyBadge.className = "status-badge connected";
        apiKeyBadge.innerHTML = `
          <span class="badge-title">AI 모델 연동됨</span>
          <span class="badge-sub">${data.model}</span>
        `;
      } else {
        apiKeyBadge.className = "status-badge error";
        apiKeyBadge.innerHTML = `
          <span class="badge-title">AI 모델</span>
          <span class="badge-sub">API 키 미설정</span>
        `;
        showError(".env 파일에 GEMINI_API_KEY가 설정되지 않았습니다.");
      }
    }
  } catch (err) {
    serverBadge.className = "status-badge error";
    serverBadge.innerHTML = `
      <span class="badge-title">서버 상태</span>
      <span class="badge-sub">연결 실패</span>
    `;
    showError("서버와의 통신이 원활하지 않습니다.");
  }
}

// 2. 파일 업로드 리스너
function initUploadListeners() {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("pdfFileInput");
  const btnStartGenerate = document.getElementById("btnStartGenerate");
  const selectedFileInfo = document.getElementById("selectedFileInfo");

  dropZone.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  function handleFileSelected(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showError("강의 자료 파일은 PDF(.pdf) 형식만 업로드할 수 있습니다.");
      return;
    }
    selectedFile = file;
    selectedFileInfo.textContent = `선택된 파일: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
    selectedFileInfo.classList.remove("hidden");
    btnStartGenerate.disabled = false;
    hideError();
    console.log(`[UPLOAD] 파일 선택: ${file.name}, 크기: ${file.size} bytes`);
  }
}

// 3. 버튼 이벤트 리스너 등록
function initActionListeners() {
  const btnStartGenerate = document.getElementById("btnStartGenerate");
  const btnGenerateQuiz = document.getElementById("btnGenerateQuiz");
  const btnPrintNote = document.getElementById("btnPrintNote");
  const closeErrorBtn = document.getElementById("closeErrorBtn");

  // 채팅 요소
  const chatInput = document.getElementById("chatInput");
  const btnSendChat = document.getElementById("btnSendChat");

  closeErrorBtn.addEventListener("click", hideError);

  // 업로드 후 바로 코넬식 노트 생성 파이프라인 시작
  btnStartGenerate.addEventListener("click", startFullCornellProcess);

  // 퀴즈 생성
  btnGenerateQuiz.addEventListener("click", generateQuiz);

  // 인쇄
  btnPrintNote.addEventListener("click", () => window.print());

  // 채팅 질문 전송
  btnSendChat.addEventListener("click", sendChatMessage);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendChatMessage();
    }
  });
}

// 4. 업로드 및 코넬식 노트 즉시 생성 파이프라인
async function startFullCornellProcess() {
  if (!selectedFile) return;

  const btn = document.getElementById("btnStartGenerate");
  btn.disabled = true;
  btn.textContent = "⏳ 강의 PDF 분석 및 코넬식 노트 작성 중...";
  hideError();

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    console.log("[PIPELINE] 1단계: PDF 업로드 및 텍스트 추출...");
    const inspectRes = await fetch("/inspect", {
      method: "POST",
      body: formData
    });

    const inspectData = await inspectRes.json();
    if (!inspectRes.ok) {
      throw new Error(inspectData.error || "강의 자료 분석에 실패했습니다.");
    }

    console.log("[PIPELINE] 2단계: 코넬식 노트 자동 생성 요청...");
    const noteRes = await fetch("/cornell_notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });

    const noteJson = await noteRes.json();
    if (!noteRes.ok) {
      throw new Error(noteJson.error || "코넬 노트 생성 실패");
    }

    console.log("[PIPELINE] 완료: 코넬 노트 렌더링 시작");
    renderCornellSheet(noteJson.data);

    // 코넬 노트 섹션 표시
    const sectionCornell = document.getElementById("sectionCornell");
    sectionCornell.classList.remove("hidden");

    // 채팅 Q&A 섹션 표시
    const sectionChat = document.getElementById("sectionChat");
    sectionChat.classList.remove("hidden");

    // 코넬 노트 섹션으로 부드럽게 스크롤
    sectionCornell.scrollIntoView({ behavior: "smooth" });

  } catch (err) {
    console.error("[ERROR]", err);
    showError(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "✨ 코넬식 노트 바로 생성하기";
  }
}

// 5. 코넬 노트 화면 렌더링
function renderCornellSheet(data) {
  document.getElementById("cornellHeaderTitle").textContent = data.title || "강의 핵심 요약 노트";
  document.getElementById("cornellDate").textContent = `정리 일시: ${new Date().toLocaleDateString()}`;

  const cueList = document.getElementById("cueList");
  const notesList = document.getElementById("notesList");
  cueList.innerHTML = "";
  notesList.innerHTML = "";

  (data.cornell_notes || []).forEach((item, idx) => {
    // Left: Cue Question & Keyword
    const cueDiv = document.createElement("div");
    cueDiv.className = "cue-item";
    cueDiv.innerHTML = `
      <div class="cue-keyword">Q${idx + 1}. [${item.cue_keyword || "핵심 개념"}]</div>
      <div class="cue-question">${item.cue_question}</div>
    `;
    cueList.appendChild(cueDiv);

    // Right: Detailed Notes
    const noteDiv = document.createElement("div");
    noteDiv.className = "note-item";
    noteDiv.innerHTML = `
      <h4>📌 ${item.cue_keyword || `섹션 ${idx + 1}`}</h4>
      <div class="note-content">${marked.parse(item.notes_content || "")}</div>
    `;
    notesList.appendChild(noteDiv);
  });

  // Bottom: Summary & Takeaways
  document.getElementById("summaryText").innerHTML = marked.parse(data.summary || "");
  const takeawaysList = document.getElementById("takeawaysList");
  takeawaysList.innerHTML = "";
  (data.key_takeaways || []).forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    takeawaysList.appendChild(li);
  });

  // Vocabulary
  const vocabGrid = document.getElementById("vocabGrid");
  vocabGrid.innerHTML = "";
  (data.vocabulary || []).forEach((v) => {
    const card = document.createElement("div");
    card.className = "vocab-card";
    card.innerHTML = `
      <div class="vocab-term">🏷️ ${v.term}</div>
      <div class="vocab-def">${v.definition}</div>
    `;
    vocabGrid.appendChild(card);
  });
}

// 6. 대화형 채팅 말풍선 Q&A 전송 및 응답 처리
async function sendChatMessage() {
  const chatInput = document.getElementById("chatInput");
  const btnSend = document.getElementById("btnSendChat");
  const message = chatInput.value.trim();

  if (!message) return;

  chatInput.value = "";
  chatInput.disabled = true;
  btnSend.disabled = true;

  const chatMessages = document.getElementById("chatMessages");

  // 사용자 말풍선 추가
  const userBubble = document.createElement("div");
  userBubble.className = "chat-bubble user";
  userBubble.innerHTML = `
    <div class="bubble-sender">나의 질문</div>
    <div class="bubble-content">${escapeHtml(message)}</div>
  `;
  chatMessages.appendChild(userBubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  // AI 타이핑 중 말풍선 추가
  const typingBubble = document.createElement("div");
  typingBubble.className = "chat-bubble ai typing";
  typingBubble.innerHTML = `
    <div class="bubble-sender">🤖 AI 학습 튜터</div>
    <div class="bubble-content">답변을 작성하는 중입니다... ✍️</div>
  `;
  chatMessages.appendChild(typingBubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });

    const resJson = await res.json();
    if (!res.ok) {
      throw new Error(resJson.error || "답변 생성 실패");
    }

    // 타이핑 말풍선을 실제 응답으로 치환
    typingBubble.querySelector(".bubble-content").innerHTML = marked.parse(resJson.reply || "");
    chatMessages.scrollTop = chatMessages.scrollHeight;

  } catch (err) {
    typingBubble.querySelector(".bubble-content").textContent = `⚠️ 오류: ${err.message}`;
  } finally {
    chatInput.disabled = false;
    btnSend.disabled = false;
    chatInput.focus();
  }
}

// 7. 퀴즈 생성 요청 (/quiz)
async function generateQuiz() {
  const btn = document.getElementById("btnGenerateQuiz");
  btn.disabled = true;
  btn.textContent = "⏳ 예상 문제를 출제하는 중입니다...";
  hideError();

  try {
    console.log("[QUIZ] 예상 문제 출제 요청...");
    const res = await fetch("/quiz", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });

    const resJson = await res.json();
    if (!res.ok) {
      throw new Error(resJson.error || "퀴즈 생성 실패");
    }

    console.log("[QUIZ] 출제 완료:", resJson.data);
    renderQuiz(resJson.data.quizzes || []);

    const section = document.getElementById("sectionQuiz");
    section.classList.remove("hidden");
    section.scrollIntoView({ behavior: "smooth" });

  } catch (err) {
    console.error("[ERROR]", err);
    showError(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "🎯 복습용 시험 예상 문제 출제하기";
  }
}

// 8. 퀴즈 렌더링
function renderQuiz(quizzes) {
  const container = document.getElementById("quizContainer");
  container.innerHTML = "";

  quizzes.forEach((q, idx) => {
    const item = document.createElement("div");
    item.className = "quiz-item";

    if (q.type === "multiple_choice") {
      let optionsHtml = "";
      (q.options || []).forEach((opt, optIdx) => {
        optionsHtml += `
          <li>
            <button class="quiz-option-btn" data-qidx="${idx}" data-optidx="${optIdx}">
              ${optIdx + 1}. ${escapeHtml(opt)}
            </button>
          </li>
        `;
      });

      item.innerHTML = `
        <span class="quiz-type-badge">객관식 (문항 ${idx + 1})</span>
        <div class="quiz-question">${escapeHtml(q.question)}</div>
        <ul class="quiz-options">${optionsHtml}</ul>
        <div id="expl-${idx}" class="quiz-explanation hidden">
          <strong>정답: ${q.answer_index + 1}번</strong><br>
          ${escapeHtml(q.explanation || "")}
        </div>
      `;
    } else {
      item.innerHTML = `
        <span class="quiz-type-badge">서술형/단답형 (문항 ${idx + 1})</span>
        <div class="quiz-question">${escapeHtml(q.question)}</div>
        <button class="btn btn-outline btn-sm show-answer-btn" data-qidx="${idx}">💡 모범 답안 및 채점 기준 확인</button>
        <div id="expl-${idx}" class="quiz-explanation hidden" style="margin-top: 0.75rem;">
          <strong>[모범 답안]</strong><br>${escapeHtml(q.model_answer)}<br><br>
          <strong>[채점 기준]</strong><br>${escapeHtml(q.grading_criteria || "")}
        </div>
      `;
    }

    container.appendChild(item);
  });

  // 객관식 선택 이벤트
  container.querySelectorAll(".quiz-option-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const qIdx = parseInt(e.target.getAttribute("data-qidx"));
      const optIdx = parseInt(e.target.getAttribute("data-optidx"));
      const quiz = quizzes[qIdx];

      const parentUl = e.target.closest(".quiz-options");
      const buttons = parentUl.querySelectorAll(".quiz-option-btn");
      buttons.forEach((b) => (b.disabled = true));

      if (optIdx === quiz.answer_index) {
        e.target.classList.add("correct");
      } else {
        e.target.classList.add("wrong");
        buttons[quiz.answer_index].classList.add("correct");
      }

      const expl = document.getElementById(`expl-${qIdx}`);
      if (expl) expl.classList.remove("hidden");
    });
  });

  // 서술형 답안 보기 이벤트
  container.querySelectorAll(".show-answer-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const qIdx = e.target.getAttribute("data-qidx");
      const expl = document.getElementById(`expl-${qIdx}`);
      if (expl) expl.classList.toggle("hidden");
    });
  });
}

// 텍스트 HTML 이스케이프
function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showError(msg) {
  const banner = document.getElementById("errorBanner");
  const text = document.getElementById("errorMessage");
  text.textContent = msg;
  banner.classList.remove("hidden");
}

function hideError() {
  document.getElementById("errorBanner").classList.add("hidden");
}
