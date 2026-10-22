"""농밥 설정 파일 — 로직(nongbab_bot.py)과 분리된 값만 둡니다.

비밀번호·API 키는 여기 적지 말고 환경변수(GitHub Secrets)로 넣으세요.
  GMAIL_USER          식단표 메일을 받는 Gmail 주소
  GMAIL_APP_PASSWORD  Google 계정 > 보안 > 앱 비밀번호 (16자리, 일반 비밀번호 X)
  ANTHROPIC_API_KEY   PDF 식단표를 읽어 JSON으로 바꿀 때 사용
"""
from pathlib import Path

# ── 메일 찾기 ──────────────────────────────────────────────
# Gmail 검색 문법 그대로 씁니다 (Gmail 검색창에 넣어 결과가 맞는지 먼저 확인해 보세요).
# 메일 제목 "[주간식단표] KT&G 서대문타워 왕구네식당" 으로 찾습니다 (보내는 사람이 바뀌어도 계속 동작).
GMAIL_QUERY = 'subject:("주간식단표" "왕구네식당") has:attachment filename:pdf newer_than:60d'
IMAP_HOST = "imap.gmail.com"
MAX_MAILS_PER_RUN = 10          # 한 번 실행에 확인할 최근 메일 수

# ── PDF 해석 ──────────────────────────────────────────────
CLAUDE_MODEL = "claude-opus-5-5"   # 주 1회라 비용보다 정확도 우선
CLAUDE_MAX_TOKENS = 16000
PARSE_RETRIES = 2               # JSON 형식이 틀리면 다시 시도할 횟수
RENDER_DPI = 200                # 작은 글씨 확인용으로 함께 보내는 확대 이미지 해상도

# ── 저장 위치 (GitHub Pages가 docs/ 를 그대로 서비스) ─────────────
ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "docs"
DATA_DIR = WEB_DIR / "data"
WEEKS_DIR = DATA_DIR / "weeks"
INDEX_FILE = DATA_DIR / "index.json"          # 주차 목록 + 최신 주차
STATUS_FILE = DATA_DIR / "status.json"        # 마지막 실행 시각·결과 (앱의 새로고침 버튼이 사용)
BUNDLE_FILE = DATA_DIR / "bundle.js"          # 위 데이터를 한 파일로 묶은 오프라인·앱 내장용 사본
ORIGINALS_DIR = ROOT / "originals"           # 원본 식단표 PDF (주 월요일 날짜로 저장, 대조용)
PROCESSED_FILE = ROOT / "state" / "processed.json"  # 이미 처리한 메일 Message-ID
KEEP_WEEKS = 12                 # 앱에서 넘겨볼 수 있는 과거 주차 수

# ── 표시 이름 ────────────────────────────────────────────
APP_NAME = "농밥"
