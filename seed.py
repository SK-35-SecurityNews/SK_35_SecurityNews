# -*- coding: utf-8 -*-
"""
MongoDB 예시 데이터 적재 스크립트
실행: venv\Scripts\python.exe seed.py
"""
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "cyberwatch"

# 범죄 유형 (카드 색/아이콘 포함)
CATEGORIES = [
    {"key": "ransomware", "name": "랜섬웨어", "icon": "🔒", "color": "#ef4444", "bg": "#fef2f2"},
    {"key": "phishing", "name": "피싱", "icon": "✉️", "color": "#3b82f6", "bg": "#eff6ff"},
    {"key": "smishing", "name": "스미싱", "icon": "📱", "color": "#22c55e", "bg": "#f0fdf4"},
    {"key": "leak", "name": "개인정보 유출", "icon": "👤", "color": "#eab308", "bg": "#fefce8"},
    {"key": "ddos", "name": "DDoS", "icon": "🖧", "color": "#a855f7", "bg": "#faf5ff"},
    {"key": "malware", "name": "악성코드", "icon": "🐞", "color": "#f43f5e", "bg": "#fff1f2"},
    {"key": "account", "name": "계정 탈취", "icon": "🔑", "color": "#06b6d4", "bg": "#ecfeff"},
]

# 연도별 발생건수 (경찰청 통계 예시)
YEARLY = {
    2020: {"ransomware": 10, "phishing": 780, "smishing": 1150, "leak": 120, "ddos": 95, "malware": 180, "account": 45},
    2021: {"ransomware": 14, "phishing": 880, "smishing": 1440, "leak": 180, "ddos": 110, "malware": 205, "account": 52},
    2022: {"ransomware": 19, "phishing": 1020, "smishing": 1810, "leak": 230, "ddos": 128, "malware": 240, "account": 68},
    2023: {"ransomware": 22, "phishing": 1180, "smishing": 2050, "leak": 260, "ddos": 142, "malware": 262, "account": 80},
    2024: {"ransomware": 27, "phishing": 1392, "smishing": 2550, "leak": 324, "ddos": 170, "malware": 279, "account": 92},
    2025: {"ransomware": 32, "phishing": 1223, "smishing": 2685, "leak": 412, "ddos": 156, "malware": 320, "account": 98},
}

# 보안 뉴스 예시
NEWS = [
    ("랜섬웨어", "국내 기업 대상 랜섬웨어 공격 증가…보안 강화 시급", "데일리시큐", "2025-10-01",
     "최근 제조·유통 분야 중견기업을 겨냥한 랜섬웨어 공격이 급증하고 있다. 백업 체계 점검과 계정 다중인증 적용이 권고된다.", ["랜섬웨어", "기업", "백업", "MFA"]),
    ("개인정보 유출", "대형 쇼핑몰 개인정보 유출 가능성…이용자 주의", "데일리시큐", "2025-09-30",
     "대형 온라인 쇼핑몰의 외부 협력사 시스템에서 이름·연락처 등 개인정보가 유출됐을 가능성이 제기됐다. 비밀번호 변경이 권장된다.", ["개인정보", "쇼핑몰", "협력사"]),
    ("스미싱", "추석 명절 스미싱 문자 주의보 발령", "데일리시큐", "2025-09-30",
     "명절 택배 배송, 안부 인사를 가장한 스미싱 문자가 급증하고 있다. 출처 불명 URL 클릭을 자제해야 한다.", ["스미싱", "명절", "택배", "URL"]),
    ("취약점", "주요 솔루션 취약점 발견…보안 업데이트 권고", "데일리시큐", "2025-09-29",
     "국내에서 널리 쓰이는 문서 보안 솔루션에서 원격 코드 실행 취약점이 발견돼 긴급 패치가 배포됐다.", ["취약점", "패치", "RCE"]),
    ("DDoS", "해외발 DDoS 공격 증가…대응 체계 강화 필요", "데일리시큐", "2025-09-29",
     "금융·공공 분야를 겨냥한 해외발 DDoS 공격이 늘고 있어 트래픽 분산 및 차단 체계 강화가 필요하다.", ["DDoS", "금융", "공공"]),
    ("피싱", "가상자산 거래소 사칭 피싱 메일 유포", "보안뉴스", "2025-09-28",
     "거래소 계정 보안 점검을 가장한 피싱 메일이 유포되고 있다. 로그인 정보 입력을 유도하는 가짜 페이지에 주의해야 한다.", ["피싱", "가상자산", "메일"]),
    ("악성코드", "업무 문서 위장 악성코드 유포 정황 포착", "보안뉴스", "2025-09-27",
     "견적서·이력서로 위장한 문서 파일에 매크로 기반 악성코드가 삽입된 사례가 다수 확인됐다.", ["악성코드", "매크로", "문서"]),
    ("계정 탈취", "SNS 계정 탈취 후 지인 사칭 금전 요구 급증", "전자신문", "2025-09-26",
     "탈취된 SNS 계정으로 지인에게 급전을 요구하는 수법이 늘고 있다. 2단계 인증 설정이 권고된다.", ["계정탈취", "SNS", "사칭", "2단계인증"]),
    ("랜섬웨어", "병원 전산망 랜섬웨어 감염…진료 차질", "전자신문", "2025-09-25",
     "지방 종합병원 전산망이 랜섬웨어에 감염돼 일부 진료가 지연됐다. 의료기관 보안 투자 필요성이 제기된다.", ["랜섬웨어", "병원", "의료"]),
    ("피싱", "정부기관 사칭 '과태료 납부' 피싱 사이트 주의", "보안뉴스", "2025-09-24",
     "교통 과태료 납부를 안내하는 정부기관 사칭 피싱 사이트가 발견됐다. 공식 도메인 확인이 필요하다.", ["피싱", "정부기관", "과태료"]),
    ("스미싱", "청첩장·부고 스미싱, 악성 앱 설치 유도", "전자신문", "2025-09-22",
     "모바일 청첩장과 부고 문자를 가장해 악성 앱 설치를 유도하는 스미싱이 확산되고 있다.", ["스미싱", "청첩장", "부고", "악성앱"]),
    ("DDoS", "게임 서버 대상 DDoS 공격으로 접속 장애", "데일리시큐", "2025-09-20",
     "국내 온라인 게임 서버가 DDoS 공격을 받아 수 시간 동안 접속 장애가 발생했다.", ["DDoS", "게임", "장애"]),
    ("개인정보 유출", "학원 관리 프로그램 해킹…수강생 정보 유출", "보안뉴스", "2025-09-18",
     "학원 관리 프로그램 서버가 해킹돼 수강생과 학부모 개인정보가 유출된 것으로 확인됐다.", ["개인정보", "학원", "해킹"]),
    ("악성코드", "크랙 프로그램에 숨은 정보탈취 악성코드 확산", "전자신문", "2025-09-15",
     "불법 크랙 프로그램에 브라우저 저장 비밀번호를 탈취하는 인포스틸러가 포함된 사례가 늘고 있다.", ["악성코드", "인포스틸러", "크랙"]),
    ("계정 탈취", "크리덴셜 스터핑으로 쇼핑몰 계정 대량 탈취", "데일리시큐", "2025-09-12",
     "타 사이트에서 유출된 계정 정보를 이용한 크리덴셜 스터핑 공격으로 쇼핑몰 계정이 대량 탈취됐다.", ["계정탈취", "크리덴셜스터핑", "쇼핑몰"]),
    ("취약점", "공유기 펌웨어 취약점 악용 봇넷 구성 경고", "보안뉴스", "2025-09-10",
     "오래된 가정용 공유기의 펌웨어 취약점을 악용해 봇넷을 구성하는 공격이 포착됐다. 펌웨어 업데이트가 필요하다.", ["취약점", "공유기", "봇넷", "IoT"]),
    ("랜섬웨어", "이중 갈취 랜섬웨어 조직, 국내 기업 데이터 공개 협박", "전자신문", "2025-09-05",
     "데이터 암호화와 유출 협박을 병행하는 이중 갈취 랜섬웨어 조직이 국내 기업을 다크웹에 게시했다.", ["랜섬웨어", "이중갈취", "다크웹"]),
    ("피싱", "QR코드 피싱 '큐싱' 주차장·공공장소 확산", "데일리시큐", "2025-08-28",
     "주차 요금 결제 QR코드를 위조해 피싱 사이트로 유도하는 큐싱 사례가 보고됐다.", ["피싱", "큐싱", "QR코드"]),
    ("스미싱", "건강검진 결과 안내 가장 스미싱 급증", "보안뉴스", "2025-08-20",
     "국민건강보험공단을 사칭한 건강검진 결과 안내 스미싱이 급증해 주의가 요구된다.", ["스미싱", "건강검진", "공공기관사칭"]),
    ("DDoS", "DDoS 대응 모의훈련 실시…공공기관 대응력 점검", "전자신문", "2025-08-12",
     "정부가 주요 공공기관을 대상으로 DDoS 대응 모의훈련을 실시해 대응 체계를 점검했다.", ["DDoS", "모의훈련", "공공기관"]),
    ("개인정보 유출", "통신사 협력업체 개인정보 유출 사고 과징금 부과", "보안뉴스", "2025-07-30",
     "개인정보보호위원회가 통신사 협력업체의 개인정보 유출 사고에 대해 과징금을 부과했다.", ["개인정보", "통신사", "과징금"]),
    ("악성코드", "북한 연계 해킹조직, 국방 분야 표적 악성코드 유포", "전자신문", "2025-07-15",
     "북한 연계 해킹조직이 국방 관련 종사자를 대상으로 스피어피싱 메일로 악성코드를 유포했다.", ["악성코드", "APT", "스피어피싱", "국방"]),
    ("계정 탈취", "클라우드 관리자 계정 탈취로 기업 데이터 삭제", "데일리시큐", "2025-06-25",
     "클라우드 관리자 계정이 탈취돼 기업 데이터가 삭제된 사건이 발생했다. 권한 최소화가 권고된다.", ["계정탈취", "클라우드", "관리자"]),
    ("취약점", "오픈소스 라이브러리 공급망 취약점 긴급 패치", "보안뉴스", "2025-06-10",
     "널리 사용되는 오픈소스 라이브러리에서 공급망 공격에 악용 가능한 취약점이 발견돼 패치가 배포됐다.", ["취약점", "오픈소스", "공급망"]),
]

# 데이터 원본(출처) 정보
SOURCES = [
    {"name": "경찰청 사이버범죄 통계", "type": "통계", "url": "https://www.police.go.kr", "update_cycle": "연 1회",
     "description": "사이버범죄 유형별·연도별 발생 건수 통계 (예시 데이터)"},
    {"name": "데일리시큐", "type": "뉴스", "url": "https://www.dailysecu.com", "update_cycle": "실시간",
     "description": "정보보안 전문 매체 뉴스 (예시 데이터)"},
    {"name": "보안뉴스", "type": "뉴스", "url": "https://www.boannews.com", "update_cycle": "실시간",
     "description": "정보보안 전문 매체 뉴스 (예시 데이터)"},
    {"name": "전자신문", "type": "뉴스", "url": "https://www.etnews.com", "update_cycle": "실시간",
     "description": "IT 전문 일간지 보안 섹션 (예시 데이터)"},
]


# 출처별 기사 원본 URL 패턴 (예시 데이터이므로 실제 기사와 일치하지 않음)
ARTICLE_URL = {
    "데일리시큐": "https://www.dailysecu.com/news/articleView.html?idxno={n}",
    "보안뉴스": "https://www.boannews.com/media/view.asp?idx={n}",
    "전자신문": "https://www.etnews.com/{ymd}{n}",
}


def article_url(source, date, n):
    pattern = ARTICLE_URL.get(source, "https://example.com/news/{n}")
    return pattern.format(n=165000 + n, ymd=date.replace("-", ""))


def seed(client=None):
    client = client or MongoClient(MONGO_URI)
    db = client[DB_NAME]

    # 기존 데이터 초기화
    for col in ("categories", "stats", "news", "sources", "meta"):
        db[col].drop()

    db.categories.insert_many([dict(c, order=i) for i, c in enumerate(CATEGORIES)])

    stats_docs = []
    for year, counts in YEARLY.items():
        for cat in CATEGORIES:
            prev = YEARLY.get(year - 1, {}).get(cat["key"])
            cur = counts[cat["key"]]
            yoy = round((cur - prev) / prev * 100, 1) if prev else None
            stats_docs.append({
                "year": year,
                "category_key": cat["key"],
                "category": cat["name"],
                "count": cur,
                "yoy_change": yoy,
                "source": "경찰청 사이버범죄 통계",
            })
    db.stats.insert_many(stats_docs)
    db.stats.create_index([("year", ASCENDING), ("category_key", ASCENDING)], unique=True)

    news_docs = []
    for i, (category, title, source, date, summary, tags) in enumerate(NEWS, start=1):
        news_docs.append({
            "category": category,
            "title": title,
            "source": source,
            "date": datetime.strptime(date, "%Y-%m-%d"),
            "summary": summary,
            "tags": tags,
            "url": article_url(source, date, i),
        })
    db.news.insert_many(news_docs)
    db.news.create_index([("date", DESCENDING)])
    db.news.create_index([("category", ASCENDING)])
    db.news.create_index([("tags", ASCENDING)])

    db.sources.insert_many(SOURCES)

    db.meta.insert_one({"key": "last_updated", "value": datetime.now()})

    return {
        "categories": db.categories.count_documents({}),
        "stats": db.stats.count_documents({}),
        "news": db.news.count_documents({}),
        "sources": db.sources.count_documents({}),
    }


if __name__ == "__main__":
    result = seed()
    print("예시 데이터 적재 완료:", result)
