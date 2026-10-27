"""농밥 설정 파일 — 로직(nongbab_bot.py)과 분리된 값만 둡니다.

비밀번호·API 키는 여기 적지 말고 환경변수(GitHub Secrets)로 넣으세요.
  GMAIL_USER          식단표 메일을 받는 Gmail 주소
  GMAIL_APP_PASSWORD  Google 계정 > 보안 > 앱 비밀번호 (16자리, 일반 비밀번호 X)
  ANTHROPIC_API_KEY   식단표(PDF·엑셀)를 읽어 JSON으로 바꿀 때 사용
"""
from pathlib import Path

# ── 식당 목록 ─────────────────────────────────────────────
# 식당을 늘리려면 여기에 한 줄(블록)만 추가하면 됩니다. 앱 상단 탭은 이 순서대로 나옵니다.
#   id     저장 폴더 이름 (영문, 바꾸지 마세요)
#   name   앱 탭에 보이는 이름
#   place  앱 아래쪽에 작게 보이는 식당 설명
#   query  Gmail 검색어 (Gmail 검색창에 그대로 넣어 결과가 맞는지 확인해 보세요)
#   hint   이 식당 표만의 특징 (읽을 때 참고)
CAFETERIAS = [
    {
        "id": "sonbo",
        "name": "손보밥",
        "place": "NH농협손해보험 · KT&G 서대문타워 왕구네식당",
        "query": 'subject:("주간식단표" "왕구네식당") has:attachment newer_than:60d',
        "hint": "",
    },
    {
        "id": "center",
        "name": "중앙회밥",
        "place": "농협중앙회 본관 구내식당",
        "query": 'subject:("본관 구내식당" "주간메뉴표") has:attachment newer_than:60d',
        "hint": "",
    },
]
ATTACHMENT_TYPES = (".pdf", ".xlsx")  # 읽을 수 있는 첨부 형식
IMAP_HOST = "imap.gmail.com"
MAX_MAILS_PER_RUN = 10          # 식당마다 한 번 실행에 확인할 최근 메일 수

# ── 식단표 해석 ────────────────────────────────────────────
CLAUDE_MODEL = "claude-opus-5-5"   # 주 1회라 비용보다 정확도 우선
CLAUDE_MAX_TOKENS = 16000
PARSE_RETRIES = 2               # JSON 형식이 틀리면 다시 시도할 횟수
RENDER_DPI = 200                # PDF 작은 글씨 확인용으로 함께 보내는 확대 이미지 해상도

# ── 저장 위치 (GitHub Pages가 docs/ 를 그대로 서비스) ─────────────
ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "docs"
DATA_DIR = WEB_DIR / "data"                   # 식당별로 data/<id>/index.json, data/<id>/weeks/<월요일>.json
CAFETERIAS_FILE = DATA_DIR / "cafeterias.json"  # 앱이 탭을 그릴 때 읽는 식당 목록
STATUS_FILE = DATA_DIR / "status.json"        # 마지막 실행 시각·결과 (앱의 새로고침 버튼이 사용)
BUNDLE_FILE = DATA_DIR / "bundle.js"          # 위 데이터를 한 파일로 묶은 오프라인·앱 내장용 사본
ORIGINALS_DIR = ROOT / "originals"           # 원본 식단표 (originals/<id>/<월요일>.pdf|xlsx, 대조용)
PROCESSED_FILE = ROOT / "state" / "processed.json"  # 이미 처리한 메일 Message-ID
KEEP_WEEKS = 12                 # 앱에서 넘겨볼 수 있는 과거 주차 수

# ── 표시 이름 ────────────────────────────────────────────
APP_NAME = "농밥"
