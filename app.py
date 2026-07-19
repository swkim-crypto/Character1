"""
인터뷰 화자 분석기 (Interview Speaker Profiler)
- 여러 개의 인터뷰 녹음파일 업로드
- OpenAI Whisper API로 전사(STT)
- Anthropic Claude API로 화자 특성 추론 (나이대/성별/직업/교육수준 + 사용자 정의 질문)

환경변수 (Render 대시보드에서 설정):
  OPENAI_API_KEY     - 음성 전사용
  ANTHROPIC_API_KEY  - 분석용
"""

import os
import json

import httpx
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

OPENAI_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"

MAX_FILE_MB = 25  # Whisper API 파일당 제한
ALLOWED_EXT = {".mp3", ".m4a", ".wav", ".webm", ".mp4", ".mpga", ".mpeg", ".ogg", ".flac"}

app = FastAPI(title="인터뷰 화자 분석기")


@app.get("/")
async def index():
    return FileResponse("templates/index.html")


@app.get("/health")
async def health():
    return {
        "ok": True,
        "openai_key": bool(OPENAI_API_KEY),
        "anthropic_key": bool(ANTHROPIC_API_KEY),
    }


async def transcribe_file(client: httpx.AsyncClient, filename: str, data: bytes) -> str:
    """OpenAI Whisper API로 오디오 파일 하나를 전사한다."""
    files = {"file": (filename, data)}
    form = {"model": "whisper-1"}
    resp = await client.post(
        OPENAI_TRANSCRIBE_URL,
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        data=form,
        files=files,
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json().get("text", "")


async def analyze_transcripts(client: httpx.AsyncClient, transcripts: list[dict], extra_question: str) -> dict:
    """Claude API로 전사문을 분석해 화자 특성을 추론한다."""
    combined = "\n\n".join(
        f"[파일 {i+1}: {t['filename']}]\n{t['text']}" for i, t in enumerate(transcripts)
    )

    extra_block = (
        f"\n\n또한 사용자가 추가로 알고 싶어하는 내용이 있습니다:\n{extra_question}\n"
        "이 질문에 대해서도 전사문에 근거해 분석해 주세요."
        if extra_question.strip()
        else ""
    )

    prompt = f"""아래는 인터뷰 녹음파일을 전사한 텍스트입니다. 인터뷰 대상자(주 화자)의 특성을 발화 내용, 어휘 선택, 말투, 언급된 경험 등을 근거로 추론해 주세요.

기본 추론 항목: 나이대, 성별, 직업(또는 직업군), 교육수준.{extra_block}

주의사항:
- 반드시 전사문에 나타난 구체적 근거를 함께 제시하세요.
- 근거가 부족한 항목은 억지로 단정하지 말고 확신도를 '낮음'으로 표시하세요.
- 이것은 텍스트 기반 추정이며 오류 가능성이 있음을 전제로 합니다.

반드시 아래 JSON 형식으로만 응답하세요 (마크다운 코드블록 없이 순수 JSON):
{{
  "attributes": [
    {{"name": "나이대", "estimate": "추정 결과", "confidence": "높음|중간|낮음", "evidence": "근거 요약"}},
    {{"name": "성별", "estimate": "...", "confidence": "...", "evidence": "..."}},
    {{"name": "직업", "estimate": "...", "confidence": "...", "evidence": "..."}},
    {{"name": "교육수준", "estimate": "...", "confidence": "...", "evidence": "..."}}
  ],
  "custom_analysis": "사용자 추가 질문에 대한 분석 (추가 질문이 없으면 빈 문자열)",
  "summary": "화자에 대한 2-3문장 종합 프로필"
}}

--- 전사문 ---
{combined}"""

    resp = await client.post(
        ANTHROPIC_MESSAGES_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": ANTHROPIC_MODEL,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    text = "".join(block.get("text", "") for block in data.get("content", []))
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


@app.post("/analyze")
async def analyze(
    files: list[UploadFile] = File(...),
    extra_question: str = Form(""),
):
    if not OPENAI_API_KEY or not ANTHROPIC_API_KEY:
        return JSONResponse(
            status_code=500,
            content={"error": "서버에 API 키가 설정되지 않았습니다. Render 환경변수에서 OPENAI_API_KEY와 ANTHROPIC_API_KEY를 확인하세요."},
        )

    transcripts = []
    async with httpx.AsyncClient() as client:
        for f in files:
            ext = os.path.splitext(f.filename or "")[1].lower()
            if ext not in ALLOWED_EXT:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"'{f.filename}'은(는) 지원하지 않는 형식입니다. 지원: {', '.join(sorted(ALLOWED_EXT))}"},
                )
            data = await f.read()
            if len(data) > MAX_FILE_MB * 1024 * 1024:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"'{f.filename}' 파일이 {MAX_FILE_MB}MB를 초과합니다."},
                )
            try:
                text = await transcribe_file(client, f.filename, data)
            except httpx.HTTPStatusError as e:
                return JSONResponse(
                    status_code=502,
                    content={"error": f"'{f.filename}' 전사 실패 (STT API 오류 {e.response.status_code})"},
                )
            transcripts.append({"filename": f.filename, "text": text})

        try:
            result = await analyze_transcripts(client, transcripts, extra_question)
        except httpx.HTTPStatusError as e:
            return JSONResponse(
                status_code=502,
                content={"error": f"분석 실패 (Claude API 오류 {e.response.status_code})"},
            )
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=502,
                content={"error": "분석 결과 파싱에 실패했습니다. 다시 시도해 주세요."},
            )

    return {
        "transcripts": transcripts,
        "analysis": result,
    }
