# 인터뷰 화자 분석기

인터뷰 녹음파일(여러 개 가능)을 업로드하면:

1. **Groq Whisper API**(무료 티어)로 음성을 텍스트로 전사하고
2. **Anthropic Claude API**가 발화 내용을 근거로 화자의 **나이대 / 성별 / 직업 / 교육수준**을 추정합니다.
3. 추가로 알고 싶은 내용을 입력창에 적으면 그 질문에 대한 분석도 함께 제공합니다.

각 항목마다 확신도(높음/중간/낮음)와 전사문 기반 근거를 표시합니다.

## 필요한 것

- Groq API 키 (전사용, 무료): https://console.groq.com/keys
- Anthropic API 키 (분석용): https://console.anthropic.com
- GitHub 계정, Render 계정 (https://render.com)

## 배포 방법 (Git → Render)

### 1. GitHub에 올리기

```bash
cd interview-analyzer
git init
git add .
git commit -m "인터뷰 화자 분석기 초기 버전"
git branch -M main
git remote add origin https://github.com/<내계정>/interview-analyzer.git
git push -u origin main
```

### 2. Render에 배포하기

1. https://dashboard.render.com 접속 → **New → Web Service**
2. 방금 만든 GitHub 저장소 연결 (`render.yaml`이 있어서 설정이 자동으로 잡힙니다)
3. **Environment Variables**에 두 개의 키를 입력:
   - `GROQ_API_KEY` = `gsk_...`
   - `ANTHROPIC_API_KEY` = `sk-ant-...`
4. **Deploy** 클릭 → 몇 분 뒤 `https://interview-analyzer-xxxx.onrender.com` 주소가 발급됩니다.

이후에는 코드를 수정하고 `git push`만 하면 Render가 자동으로 재배포합니다.

### 3. 로컬에서 먼저 테스트하려면

```bash
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app:app --reload
# http://localhost:8000 접속
```

## 제한 사항

- 파일당 최대 **25MB** (Groq 무료 티어 제한). 긴 녹음은 잘라서 올려 주세요.
- Groq 무료 티어는 하루 약 2,000건의 전사 요청 제한이 있습니다 (개인 사용에는 충분).
- 전사 언어는 한국어(`ko`)로 고정되어 있습니다. 영어 인터뷰를 분석하려면 `app.py`에서 `"language": "ko"` 부분을 지우면 자동 감지로 동작합니다.
- 지원 형식: mp3, m4a, wav, webm, mp4, ogg, flac 등
- Render 무료 플랜은 유휴 시 서버가 잠들어 첫 요청이 느릴 수 있고, 요청 타임아웃이 있어 아주 긴 파일은 유료 플랜이 안정적입니다.

## 사용 시 유의사항

분석 결과는 발화 텍스트에 기반한 **확률적 추정**이며 틀릴 수 있습니다.
채용·평가 등 개인에게 실질적 영향을 주는 결정의 단독 근거로 사용하지 마시고,
녹음 대상자의 동의를 받은 파일만 사용하세요.
