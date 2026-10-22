# 농밥

예은 님이 보내주는 `[주간식단표]` 메일을 자동으로 읽어서, 월~금 메뉴를 한 화면에 보여주는 앱입니다.

```
Gmail ──(30분마다)──▶ GitHub Actions: nongbab_bot.py ──▶ docs/data/*.json ──▶ GitHub Pages ──▶ 농밥 앱(플레이스토어)
          PDF 첨부        Claude가 표를 JSON으로 변환         저장소에 커밋          웹 주소로 서비스      웹앱을 감싼 안드로이드 앱
```

서버를 따로 빌리지 않습니다. 메일 확인은 GitHub Actions(무료), 앱 화면은 GitHub Pages(무료)가 맡습니다.
메일이 들어오면 늦어도 30분 안에 앱에 반영되고, 앱 자체를 다시 올릴 필요는 없습니다.

| 파일 | 하는 일 |
|---|---|
| `config.py` | 메일 검색 조건, 모델, 저장 위치 같은 설정값 |
| `nongbab_bot.py` | 메일 찾기 → PDF 해석 → 검증 → 저장 |
| `docs/index.html` | 앱 화면 (이 한 파일에 화면·디자인·동작이 다 들어 있음) |
| `docs/sw.js`, `docs/manifest.webmanifest`, 아이콘 | 설치형 앱(PWA)용 파일 |
| `docs/privacy.html` | 플레이스토어 등록에 필요한 개인정보처리방침 |
| `.github/workflows/nongbab.yml` | 평일 08~20시, 30분마다 봇 실행 |

---

## 1. Gmail 앱 비밀번호 만들기

봇은 **일반 비밀번호로는 로그인할 수 없습니다** (구글이 막아둠). 대신 앱 전용 비밀번호를 씁니다.

1. 식단표를 받는 Gmail 계정의 비밀번호를 먼저 새로 바꿉니다 (채팅에 노출됐던 비밀번호는 쓰지 마세요).
2. https://myaccount.google.com/security 에서 **2단계 인증**을 켭니다.
3. https://myaccount.google.com/apppasswords 에서 이름을 `농밥`으로 앱 비밀번호를 만듭니다 → 16자리가 나옵니다.

이 비밀번호로는 메일 읽기만 할 수 있고, 언제든 같은 화면에서 삭제하면 바로 끊깁니다.

## 2. Claude API 키 만들기

https://console.anthropic.com → API Keys → Create Key. PDF 한 장 읽는 데 몇십 원 수준이라 주 1회면 한 달에 수백 원 정도입니다.

## 3. GitHub에 올리기

1. GitHub에서 저장소를 만듭니다. 이름을 **`<내 GitHub 아이디>.github.io`** 로 하세요.
   (플레이스토어 앱에서 주소창 없이 열리려면 사이트가 도메인 맨 앞에 있어야 해서 이 이름이 필요합니다.)
2. 이 폴더 전체를 그 저장소에 올립니다.
3. 저장소 **Settings → Secrets and variables → Actions → New repository secret** 에 세 개를 넣습니다.
   - `GMAIL_USER` : 식단표를 받는 Gmail 주소
   - `GMAIL_APP_PASSWORD` : 1번의 16자리
   - `ANTHROPIC_API_KEY` : 2번의 키
4. **Settings → Pages** → Source: `Deploy from a branch`, Branch: `main`, 폴더: `/docs` → Save.
5. **Actions 탭 → 농밥 식단표 수집 → Run workflow** 로 한 번 실행합니다. 초록불이 뜨면 `https://<아이디>.github.io` 에서 실제 식단이 보입니다.

> 메일을 못 찾으면 `config.py`의 `GMAIL_QUERY`를 Gmail 검색창에 그대로 붙여 넣어 보세요. 거기서 식단표 메일이 나오도록 고치면 봇도 똑같이 찾습니다.
> 보낸 사람이 바뀌면 `from:` 부분만 바꾸면 됩니다.

내 PC에서 PDF 하나로 먼저 시험해 보려면:

```
$env:ANTHROPIC_API_KEY="sk-ant-..."
py -3.14 nongbab_bot.py --pdf 20260818_식단표.pdf
```
(추가 설치 패키지 없음, 파이썬 기본 라이브러리만 사용)

## 3-1. 내 폰에서 바로 테스트 (APK)

저장소에 올리면 `농밥 테스트 APK` 워크플로가 자동으로 APK를 만들어 **Releases → test-apk**에 올립니다.

1. 폰 브라우저로 `https://github.com/<아이디>/<저장소>/releases/tag/test-apk` 열기 → `nongbab.apk` 받기
2. 설치할 때 "출처를 알 수 없는 앱" 허용 (크롬 또는 내 파일 앱에 허용)
3. 홈 화면의 '농밥' 아이콘으로 실행

- 앱 화면을 고쳐서 올리면 새 APK가 같은 링크에 다시 올라가고, 기존 앱 위에 덮어 설치됩니다.
- 앱은 GitHub Pages의 최신 식단을 먼저 읽고, 연결이 안 되면 APK 안에 든 식단을 보여줍니다.
- `android/debug.keystore`는 테스트 전용 서명키입니다. 플레이스토어 출시는 아래 4번의 별도 키로 합니다.

## 4. 플레이스토어 앱 만들기 (Bubblewrap)

웹앱을 안드로이드 앱으로 감싸는 구글 공식 도구입니다. 메뉴가 바뀌어도 앱을 다시 올릴 필요가 없습니다.

```
npm i -g @bubblewrap/cli
mkdir android && cd android
bubblewrap init --manifest https://<아이디>.github.io/manifest.webmanifest
```
질문이 나오면:
- Application ID: `io.github.<아이디>.nongbab`
- 키스토어는 새로 만들기 → **비밀번호와 `android.keystore` 파일은 꼭 따로 백업** (잃어버리면 업데이트 불가)

```
bubblewrap build
```
→ `app-release-bundle.aab`(플레이스토어 업로드용)가 만들어집니다.

**주소창 없애기 (중요)**: 앱이 내 사이트 소유라는 증명이 필요합니다.
1. `bubblewrap fingerprint generateAssetLinks` → 나온 내용을 `docs/.well-known/assetlinks.json`에 덮어씁니다.
2. 플레이 콘솔 → 앱 → **설정 → 앱 무결성 → 앱 서명**에 있는 *앱 서명 키 SHA-256* 도
   `bubblewrap fingerprint add <SHA-256>` 후 다시 생성해서 함께 넣습니다 (구글이 앱을 다시 서명하기 때문).
3. 커밋 → 몇 분 뒤 앱을 열면 주소창 없이 전체 화면으로 뜹니다.

## 5. 플레이 콘솔 등록

1. https://play.google.com/console 개발자 계정 (1회 25달러, 본인 인증)
2. 앱 만들기 → 이름 `농밥`, 무료
3. 스토어 등록정보: 아이콘은 `docs/icon-maskable-512.png`, 스크린샷은 폰에서 앱 화면 캡처 2장 이상
4. 개인정보처리방침 URL: `https://<아이디>.github.io/privacy.html`
5. 앱 콘텐츠 설문: 광고 없음 / 데이터 수집 없음 / 대상 연령 18세 이상
6. **테스트 → 비공개 테스트**에 `.aab` 업로드, 테스터 이메일 등록
   - 2023년 11월 이후 만든 개인 계정은 **테스터 12명 이상이 14일간** 써야 프로덕션(공개) 출시 신청이 열립니다.
   - 회사 동료끼리만 쓸 거라면 비공개 테스트 상태로 계속 써도 됩니다. 메뉴는 똑같이 자동 갱신됩니다.

## 운영 메모

- **식단 공개 범위**: 메일 하단에 외부 배포 금지 문구가 있습니다. Pages 사이트와 공개 출시 앱은 누구나 볼 수 있으니, 공개 출시 전에 예은 님 쪽에 확인해 두세요.
- **잘못 읽힌 메뉴**: `docs/data/weeks/<월요일날짜>.json`을 GitHub에서 바로 고쳐 저장하면 앱에 반영됩니다.
- **같은 주 정정본 메일**: 나중에 온 메일이 그 주 식단을 덮어씁니다.
- **해석 실패**: Actions가 빨간불이 되고, 실패한 메일은 다음 실행 때 다시 시도합니다. 다른 주차는 정상 반영됩니다.
- 앱은 최근 12주까지 넘겨볼 수 있습니다 (`config.KEEP_WEEKS`).
- 지금 들어 있는 8/17~8/21 데이터는 메일 미리보기에서 옮긴 **예시**입니다. 첫 실행 후 새 주차가 생기면 그대로 두거나 지워도 됩니다.
