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
#   sheets 엑셀일 때 읽을 시트 (None이면 전부)
#   hint   이 식당 표만의 특징 (읽을 때 참고)
# 중앙회 본관·신관 메뉴는 진하윤 주임이 보내는 메일 한 통(엑셀 하나, 시트 두 개)에 같이 옵니다.
CENTRAL_QUERY = 'from:진하윤 has:attachment filename:xlsx newer_than:60d'

CAFETERIAS = [
    {
        "id": "sonbo",
        "name": "손보밥",
        "place": "NH농협손해보험 · KT&G 서대문타워 왕구네식당",
        "query": 'subject:("주간식단표" "왕구네식당") has:attachment newer_than:60d',
        "sheets": None,      # 엑셀일 때 읽을 시트 이름 목록 (None = 전부)
        "hint": "",
    },
    {
        "id": "center",
        "name": "중앙회밥",
        "place": "농협중앙회 본관 구내식당",
        "query": CENTRAL_QUERY,
        "sheets": ["본관"],   # 같은 엑셀에 신관 시트도 있어 본관만 읽음 (신관은 아래 '신관밥')
        "hint": """\
- 아침: 굵은 글씨 첫 메뉴가 대표 메뉴(main), 그 아래가 반찬(items). 코너 이름은 "", 시간 07:30~08:40.
  맨 위 '천원으로 즐기는 구내식당 아침밥…' 같은 캠페인 문구는 메뉴가 아니니 넣지 마세요.
- 점심 코너는 표 왼쪽 이름을 이렇게 바꿔 쓰세요: '두레 A' → "A코너", '두레 B' → "B코너", '신토불이' → "신토불이", '샐러드바' → "샐러드바".
  코너별 시간(time)은 아래 '운영 시간 안내'에서 가져오세요 (예: A코너 11:30~13:00, B코너 11:50~소진 시까지). 끼니 time은 비워 두세요.
- 한 코너에 굵은 메뉴가 두 개면(예: 소고기마라탕, 수제유린기) 첫째가 main, 둘째는 items 맨 앞에 넣으세요.
- 코너 위 주황 칸의 'A코너 자율배식', 금요일 '금요행복밥상' 같은 짧은 안내는 그 코너의 note에 넣으세요.
  금요행복밥상처럼 한 열 전체가 하나로 합쳐진 날은 코너 하나(name "금요행복밥상", 굵은 메뉴들 중 첫째가 main)로 넣으세요.
- '<행 사> 양곡부 …'처럼 행사로 코너 칸이 막힌 날은 그 코너들을 넣지 말고, 그 끼니의 note에 '행사: 양곡부 2026년 제3차 …'처럼 적으세요.
- 샐러드바: 첫 줄이 main, 그 아래(음료·디저트)는 items.
- 맨 아래 원산지 표는 메뉴가 아닙니다.""",
    },
    {
        "id": "singwan",
        "name": "신관밥",
        "place": "농협은행 신관 구내식당",
        "query": CENTRAL_QUERY,
        "sheets": ["신관"],
        "hint": """\
- 셀 하나에 메뉴 여러 줄이 ' / '로 이어져 있습니다. 그 칸의 첫 메뉴가 대표 메뉴(main), 나머지가 items입니다.
- 아침: 코너 이름 "", 끼니 time 07:30~08:40. 맨 위 '천원으로 셀프 계란후라이…' 같은 캠페인 문구는 메뉴가 아닙니다.
- 점심: 표 왼쪽 'A 코너' → "A코너", 'B 코너' → "B코너", '샐러드바' → "샐러드바". 끼니 time은 11:30~13:00.
  (운영 시간 안내의 A조·B조는 층별 식사 시간이지 코너가 아닙니다.)
- 칸 위에 굵게 따로 적힌 '균형미먹는날♪', '중식DAY' 같은 짧은 문구는 그 아래 코너의 note에 넣으세요.
- 금요일처럼 A·B 칸이 하나로 합쳐지고 '금요행복밥상'이 적힌 날은 코너 하나(name "금요행복밥상")로 넣으세요.
  '*애플소보로토스토*'처럼 별표로 감싼 디저트는 별표를 빼고 items 맨 끝에 넣으세요.
- '[행 사] 종합기획부 오찬'처럼 행사로 막힌 칸은 그 코너를 넣지 말고 그 끼니의 note에 '행사: 종합기획부 오찬'처럼 적으세요.
- 샐러드바 '야채샐러드 / 드레싱'은 main "야채샐러드", items ["드레싱"].
- 아래쪽 '행 사' 칸, 운영 시간 안내, 원산지 표는 메뉴가 아닙니다.""",
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
PROCESSED_FILE = ROOT / "state" / "processed.json"  # 이미 처리한 메일 ("식당id|Message-ID", 한 메일이 여러 식당에 쓰일 수 있어 식당별)
KEEP_WEEKS = 12                 # 앱에서 넘겨볼 수 있는 과거 주차 수

# ── 표시 이름 ────────────────────────────────────────────
APP_NAME = "농밥"
