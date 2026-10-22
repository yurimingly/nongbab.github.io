"""농밥 봇 — 식단표 메일을 찾아 PDF를 읽고, 앱이 보여줄 JSON을 만듭니다.

흐름:  Gmail(IMAP) 검색 → 새 메일의 PDF 첨부 → Claude가 표를 JSON으로 변환
      → 형식 검증·정리 → docs/data/weeks/<월요일>.json 저장 → index.json 갱신

사용법:
  python nongbab_bot.py                 메일함 확인 후 새 식단표 반영 (GitHub Actions가 이걸 실행)
  python nongbab_bot.py --pdf 식단.pdf   메일 없이 로컬 PDF 하나로 테스트
  python nongbab_bot.py --reprocess     이미 처리한 메일도 다시 읽기 (파싱 방식 바꿨을 때)
"""
import argparse
import base64
import datetime as dt
import email
import imaplib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

import config

WEEKDAYS = "월화수목금토일"
IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def report(level, msg):
    """콘솔에 찍고, GitHub Actions에서는 실행 화면 상단 알림 + 요약에도 남깁니다 (로그를 안 열어도 원인이 보이게)."""
    print(msg)
    if IN_ACTIONS:
        print(f"::{level}::" + msg.replace("%", "%25").replace("\r", "").replace("\n", "%0A"))
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write(("❌ " if level == "error" else "ℹ️ ") + msg.replace("\n", "  \n") + "\n\n")


class Fatal(Exception):
    """설정·로그인처럼 더 진행할 수 없는 문제"""

PROMPT = """첨부한 PDF는 회사 구내식당의 주간 식단표입니다. 표 전체를 빠짐없이 아래 JSON 형식으로 옮겨 주세요.
JSON만 출력하고 설명은 붙이지 마세요.

{
  "title": "표 제목 그대로",
  "week_start": "YYYY-MM-DD (표의 첫 날짜)",
  "week_end": "YYYY-MM-DD (표의 마지막 날짜)",
  "days": [
    {
      "date": "YYYY-MM-DD",
      "holiday": false,
      "holiday_name": "",
      "meals": [
        {
          "meal": "아침 | 점심 | 저녁 중 하나 (표의 구분 이름이 '활기찬 아침'처럼 꾸며져 있어도 끼니 이름으로)",
          "label": "표에 적힌 구분 이름 그대로 (예: 활기찬 아침), 없으면 빈 문자열",
          "time": "운영 시간 (예: 7:30~8:40), 없으면 빈 문자열",
          "corners": [
            {"name": "코너 이름 (예: CORNER1, 컵밥, PLUS, 국)", "items": ["메뉴 한 줄씩"], "kcal": 759}
          ]
        }
      ]
    }
  ],
  "shared": [
    {"meal": "끼니", "name": "여러 요일에 걸쳐 합쳐진 칸의 이름 (예: 셀프라면)", "time": "운영 시간", "lines": ["한 줄씩"]}
  ]
}

규칙:
- 표에 있는 날짜는 모두 days에 넣으세요. 비어 있거나 회색으로 막힌 날은 holiday=true, meals=[] 로 두고, 사유가 적혀 있으면 holiday_name에 쓰세요.
- 원산지 표기는 해당 메뉴 줄 끝에 괄호로 붙이세요. 예: "돈육고추장찌개 (돈전지:미국산)"
- 칼로리 칸은 바로 위 코너의 kcal 숫자로 넣고, 없으면 null.
- 국/찌개처럼 코너 이름 없이 맨 위에 따로 있는 칸은 corners 맨 앞에 name "국"으로 넣으세요.
- 글자를 지어내지 말고, 흐려서 읽을 수 없는 글자는 그대로 [?]로 표시하세요.
"""


# ─────────────────────────── Gmail ───────────────────────────
def _decode(value):
    return str(make_header(decode_header(value))) if value else ""


def fetch_menu_mails(processed_ids, reprocess=False):
    """검색 조건에 맞는 메일 중 아직 처리하지 않은 것의 PDF들을 오래된 순서로 돌려줍니다."""
    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not user or not pw:
        raise Fatal("GMAIL_USER / GMAIL_APP_PASSWORD 환경변수가 없습니다. README의 '1. Gmail 앱 비밀번호'를 보세요.")

    conn = imaplib.IMAP4_SSL(config.IMAP_HOST)
    try:
        conn.login(user, pw)
    except imaplib.IMAP4.error as e:
        raise Fatal(f"Gmail 로그인 실패: {e}\n→ 일반 비밀번호가 아니라 '앱 비밀번호'를 넣었는지 확인하세요.")

    # 받은편지함 밖(라벨·보관함)에 있어도 찾도록 전체보관함에서 검색.
    # 한국어 Gmail은 폴더 이름이 '[Gmail]/전체보관함'이라, 이름 대신 \All 표시로 찾습니다.
    all_mail = None
    for line in conn.list()[1] or []:
        text = line.decode(errors="ignore") if isinstance(line, bytes) else str(line)
        if "\\All" in text:
            all_mail = text.rsplit(' "/" ', 1)[-1].strip()
            break
    if not all_mail or conn.select(all_mail, readonly=True)[0] != "OK":
        conn.select("INBOX", readonly=True)

    # 한글 검색어는 literal로 넘겨야 Gmail 검색(X-GM-RAW)이 제대로 받습니다
    conn.literal = config.GMAIL_QUERY.encode("utf-8")
    status, data = conn.uid("SEARCH", "CHARSET", "UTF-8", "X-GM-RAW")
    if status != "OK":
        conn.logout()
        raise Fatal(f"메일 검색 실패: {data}")

    uids = data[0].split()[-config.MAX_MAILS_PER_RUN:]
    found = []
    for uid in uids:
        status, msg_data = conn.uid("FETCH", uid, "(RFC822)")
        if status != "OK" or not msg_data or msg_data[0] is None:
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        msg_id = (msg.get("Message-ID") or f"uid-{uid.decode()}").strip()
        if msg_id in processed_ids and not reprocess:
            continue
        subject = _decode(msg.get("Subject"))
        try:
            received = parsedate_to_datetime(msg.get("Date")).isoformat()
        except Exception:
            received = ""
        pdfs = []
        for part in msg.walk():
            filename = _decode(part.get_filename())
            is_pdf = filename.lower().endswith(".pdf") or part.get_content_type() == "application/pdf"
            if is_pdf and part.get_payload(decode=True):
                pdfs.append((filename or "menu.pdf", part.get_payload(decode=True)))
        found.append({"id": msg_id, "subject": subject, "received": received, "pdfs": pdfs})
    conn.logout()
    found.sort(key=lambda m: m["received"])  # 오래된 것부터 → 같은 주 정정본이면 최신이 덮어씀
    return found


# ─────────────────────────── PDF → JSON ───────────────────────────
def ask_claude(pdf_bytes):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise Fatal("ANTHROPIC_API_KEY 환경변수가 없습니다. 저장소 Settings → Secrets에 넣어 주세요.")
    body = {
        "model": config.CLAUDE_MODEL,
        "max_tokens": config.CLAUDE_MAX_TOKENS,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                 "data": base64.b64encode(pdf_bytes).decode()}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")[:300]
        if e.code in (401, 403):
            raise Fatal(f"Claude API 키가 거절됐습니다 ({e.code}). 키를 다시 확인하세요: {detail}")
        if e.code == 400 and "credit" in detail.lower():
            raise Fatal(f"Claude API 잔액이 부족합니다. console.anthropic.com에서 충전하세요: {detail}")
        raise RuntimeError(f"Claude API 오류 {e.code}: {detail}")
    return "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text")


def extract_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("응답에 JSON이 없습니다")
    return json.loads(text[start:end + 1])


def _date(s):
    return dt.date.fromisoformat(str(s).strip()[:10])


def _kcal(v):
    if v in (None, ""):
        return None
    m = re.search(r"\d+", str(v).replace(",", ""))
    return int(m.group()) if m else None


def _lines(v):
    if isinstance(v, str):
        v = v.split("\n")
    return [re.sub(r"\s+", " ", str(x)).strip() for x in (v or []) if str(x).strip()]


MEAL_ORDER = {"아침": 0, "점심": 1, "저녁": 2}


def _meal_name(m, label=""):
    for name in MEAL_ORDER:
        if name in (m or "") or name in (label or ""):
            return name
    return (m or label or "식사").strip()


def normalize(raw, source):
    """Claude가 돌려준 값을 앱이 믿고 쓸 수 있는 형태로 정리·검증합니다. 문제가 있으면 ValueError."""
    days = []
    for d in raw.get("days") or []:
        date = _date(d["date"])
        meals = []
        for m in d.get("meals") or []:
            corners = []
            for c in m.get("corners") or []:
                items = _lines(c.get("items"))
                if items:
                    corners.append({"name": str(c.get("name") or "").strip(), "items": items, "kcal": _kcal(c.get("kcal"))})
            if corners:
                meals.append({"meal": _meal_name(m.get("meal"), m.get("label")),
                              "label": str(m.get("label") or "").strip(),
                              "time": str(m.get("time") or "").strip(), "corners": corners})
        meals.sort(key=lambda m: MEAL_ORDER.get(m["meal"], 9))
        days.append({"date": date.isoformat(), "weekday": WEEKDAYS[date.weekday()],
                     "holiday": bool(d.get("holiday")) or not meals,
                     "holiday_name": str(d.get("holiday_name") or "").strip(), "meals": meals})
    if not days:
        raise ValueError("요일 데이터가 비어 있습니다")
    days.sort(key=lambda d: d["date"])
    if all(d["holiday"] for d in days):
        raise ValueError("모든 날이 비어 있습니다 — 표를 읽지 못한 것 같습니다")

    first = _date(days[0]["date"])
    week_start = (first - dt.timedelta(days=first.weekday())).isoformat()  # 항상 그 주 월요일 기준
    shared = [{"meal": _meal_name(s.get("meal")), "name": str(s.get("name") or "").strip(),
               "time": str(s.get("time") or "").strip(), "lines": _lines(s.get("lines"))}
              for s in raw.get("shared") or [] if _lines(s.get("lines"))]
    return {"title": str(raw.get("title") or "주간식단표").strip(),
            "week_start": week_start, "week_end": days[-1]["date"],
            "days": days, "shared": shared, "source": source,
            "updated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds")}


def parse_pdf(pdf_bytes, source):
    last_err = None
    for attempt in range(1 + config.PARSE_RETRIES):
        try:
            return normalize(extract_json(ask_claude(pdf_bytes)), source)
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            last_err = e
            print(f"  ↻ 해석 재시도 {attempt + 1}: {e}")
    raise RuntimeError(f"PDF 해석 실패: {last_err}")


# ─────────────────────────── 저장 ───────────────────────────
def _load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)  # 앱이 반쯤 쓰인 파일을 읽지 않도록 한 번에 교체


def save_week(week):
    _save(config.WEEKS_DIR / f"{week['week_start']}.json", week)
    rebuild_index()
    print(f"  ✓ {week['week_start']} ~ {week['week_end']} 저장")


def rebuild_index():
    """weeks/ 폴더를 기준으로 목록을 다시 만듭니다 (파일과 목록이 어긋날 일이 없게)."""
    files = sorted(config.WEEKS_DIR.glob("*.json"), reverse=True)
    for old in files[config.KEEP_WEEKS:]:
        old.unlink()
    weeks = []
    for f in files[:config.KEEP_WEEKS]:
        w = _load(f, None)
        if w:
            weeks.append({"start": w["week_start"], "end": w["week_end"], "file": f"weeks/{f.name}"})
    index = {"app": config.APP_NAME, "latest": weeks[0]["start"] if weeks else None, "weeks": weeks,
             "updated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds")}
    _save(config.INDEX_FILE, index)

    # 같은 데이터를 스크립트 한 개로도 저장 → 인터넷이 없거나 앱 안(file://)에서 열어도 식단이 보이게
    bundle = {"index.json": index}
    for w in weeks:
        bundle[w["file"]] = _load(config.DATA_DIR / w["file"], None)
    tmp = config.BUNDLE_FILE.with_suffix(".tmp")
    tmp.write_text("window.NONGBAB_BUNDLE=" + json.dumps(bundle, ensure_ascii=False, separators=(",", ":")) + ";\n",
                   encoding="utf-8")
    tmp.replace(config.BUNDLE_FILE)


# ─────────────────────────── 실행 ───────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", help="메일 대신 로컬 PDF 파일로 테스트")
    ap.add_argument("--reprocess", action="store_true", help="이미 처리한 메일도 다시 해석")
    args = ap.parse_args()

    if args.pdf:
        with open(args.pdf, "rb") as f:
            save_week(parse_pdf(f.read(), {"filename": os.path.basename(args.pdf)}))
        return

    state = _load(config.PROCESSED_FILE, {"ids": []})
    mails = fetch_menu_mails(set(state["ids"]), args.reprocess)
    if not mails:
        report("notice", f"새 식단표 메일 없음 (검색어: {config.GMAIL_QUERY})")
        return

    failed = 0
    for m in mails:
        print(f"● {m['received'][:16]}  {m['subject']}")
        if not m["pdfs"]:
            print("  - PDF 첨부 없음, 건너뜀")
        for filename, data in m["pdfs"]:
            try:
                save_week(parse_pdf(data, {"subject": m["subject"], "received": m["received"], "filename": filename}))
            except Exception as e:  # 한 파일 실패가 다른 주차 반영을 막지 않게
                failed += 1
                if isinstance(e, Fatal):
                    raise
                report("error", f"{m['subject']} / {filename} 해석 실패: {e}")
                break
        else:
            if m["id"] not in state["ids"]:
                state["ids"].append(m["id"])  # 성공한 메일만 '처리됨' → 실패한 건 다음 실행에 재시도
    state["ids"] = state["ids"][-200:]
    _save(config.PROCESSED_FILE, state)
    if failed:
        sys.exit(1)
    report("notice", f"식단표 메일 {len(mails)}통 처리 완료")  # Actions에서 빨간 표시로 실패를 알 수 있게


if __name__ == "__main__":
    try:
        main()
    except Fatal as e:
        report("error", str(e))
        sys.exit(1)
    except Exception as e:  # 예상 못 한 오류도 원인이 화면에 남게
        report("error", f"예상 못 한 오류: {type(e).__name__}: {e}")
        raise
