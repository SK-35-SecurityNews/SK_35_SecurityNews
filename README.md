# CyberWatch - 사이버보안 통합 대시보드

Flask + MongoDB 기반의 보안 뉴스·사이버범죄 통계 검색 대시보드입니다.

## 실행 방법

```bash
# 1) 가상환경 활성화 (Windows)
venv\Scripts\activate

# 2) 패키지 설치 (최초 1회)
pip install -r requirements.txt

# 3) 데이터 수집 및 가공, MongoDB 저장
python rss_.py

# 4) 서버 실행
python app.py
```

브라우저에서 http://localhost:5000 접속. MongoDB는 `mongodb://localhost:27017` 에 실행 중이어야 합니다.
DB가 비어 있으면 첫 접속 시 자동으로 예시 데이터가 적재됩니다.

## 구조

| 파일 | 설명 |
| --- | --- |
| `app.py` | Flask 라우트 (홈/검색, 보안 뉴스, 통계, 추이, 데이터 원본, 정보, 검색 API) |
| `rss_.py` | 데이터 수집 및 가공 이후 MongoDB `cyberwatch` DB에 데이터 적재 |
| `templates/` | Jinja2 템플릿 (`base.html` 공통 레이아웃) |
| `static/style.css` | 스타일 |

## MongoDB 컬렉션 (`cyberwatch`)

| 컬렉션 | 내용 |
| --- | --- |
| `categories` | 범죄 유형 7종 (이름, 아이콘, 색상) |
| `stats` | 2020~2025년 유형별 발생건수, 전년 대비 증감률 |
| `news` | 보안 뉴스 24건 (유형, 제목, 출처, 날짜, 요약, 태그) |
| `sources` | 데이터 출처 정보 |
| `meta` | 마지막 업데이트 시각 |

## 주요 기능

- 홈: 키워드 검색 + 유형/출처/연도/태그 색인으로 news 컬렉션 탐색, 통계 컬렉션 동시 검색
- 상단 카드: 최신 연도 유형별 건수와 전년 대비 증감률 (클릭 시 해당 유형으로 검색)
- 데이터 새로고침 버튼: 예시 데이터 재적재
- `GET /api/search?q=...&category=...&source=...&year=...&tag=...` JSON 검색 API
