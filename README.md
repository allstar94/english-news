# Daily English News

매일 아침 8시(KST), Gemini 2.5 Flash로 영어 뉴스를 요약해 이메일로 발송하는 자동화 시스템입니다.

- **카테고리**: IT/Tech · Economy · World (각 2~3개 기사)
- **내용**: 영어 제목 · 영어 요약(3~4문장) · 핵심 어휘 3개(뜻 + 예문)
- **전송**: Gmail SMTP → `alsltar94@gmail.com`
- **자동화**: GitHub Actions (매일 23:00 UTC = 08:00 KST)

---

## 설정 방법

### 1. Gemini API 키 발급

1. [Google AI Studio](https://aistudio.google.com/app/apikey) 접속
2. **Create API key** 클릭 → 키 복사

### 2. Gmail 앱 비밀번호 생성

Google 계정의 일반 비밀번호가 아닌 **앱 비밀번호**가 필요합니다.

1. [Google 계정 보안](https://myaccount.google.com/security) → **2단계 인증** 활성화 (없으면 먼저 켜기)
2. 같은 페이지 → **앱 비밀번호** 검색 → 새 앱 비밀번호 생성
3. 앱 이름: `DailyEnglishNews` → 생성된 16자리 비밀번호 복사

### 3. GitHub 저장소 생성 및 코드 업로드

```bash
cd ~/vibecoding/english-news
git init
git add .
git commit -m "Initial commit"
# GitHub에서 새 저장소(public/private 무관) 생성 후:
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

### 4. GitHub Secrets 등록

저장소 페이지 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 이름          | 값                                         |
| -------------------- | ------------------------------------------ |
| `GEMINI_API_KEY`     | Google AI Studio에서 발급한 API 키         |
| `GMAIL_USER`         | 발신 Gmail 주소 (예: `yourname@gmail.com`) |
| `GMAIL_APP_PASSWORD` | 위에서 생성한 16자리 앱 비밀번호           |

### 5. 동작 확인 (수동 실행)

저장소 → **Actions** 탭 → **Daily English News** → **Run workflow** → **Run workflow** 클릭

정상 실행 시 `alsltar94@gmail.com`으로 이메일이 발송됩니다.

---

## 로컬 테스트

```bash
cd ~/vibecoding/english-news
pip install -r requirements.txt

export GEMINI_API_KEY="your_gemini_api_key"
export GMAIL_USER="your@gmail.com"
export GMAIL_APP_PASSWORD="your_app_password"

python main.py
```

---

## 파일 구조

```
english-news/
├── main.py                          # 메인 스크립트
├── requirements.txt                 # Python 패키지
├── .github/
│   └── workflows/
│       └── daily_news.yml           # GitHub Actions 워크플로
└── README.md
```

---

## 자주 묻는 문제

**Q. Gemini 모델을 찾을 수 없다는 오류가 나요.**
`main.py`의 `"gemini-2.5-flash"` 부분을 [사용 가능한 최신 모델 ID](https://ai.google.dev/gemini-api/docs/models)로 교체하세요.

**Q. Gmail 인증 오류가 납니다.**
일반 비밀번호가 아닌 **앱 비밀번호** 16자리를 사용했는지 확인하세요. 2단계 인증이 켜져 있어야 앱 비밀번호를 만들 수 있습니다.

**Q. RSS를 못 가져와도 이메일이 오나요?**
네. RSS 수집 실패 시 Gemini가 자체 지식으로 대체 요약을 생성합니다.
