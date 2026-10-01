import feedparser
from datetime import datetime

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

import schedule
import time


# ============================================================
# 1. MongoDB 연결
# ============================================================

MONGO_URL = "mongodb://localhost:27017/"
DB_NAME = "cybercrime_db"
COLLECTION_NAME = "news"

client = MongoClient(MONGO_URL)

db = client[DB_NAME]
collection = db[COLLECTION_NAME]

# 기사 링크를 기준으로 중복 저장 방지
collection.create_index("link", unique=True)

print("MongoDB 연결 완료")


# ============================================================
# 2. RSS 주소
# ============================================================

rss_sources = {
    "ASEC": "https://asec.ahnlab.com/ko/feed/",
    "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "DailySecu": "https://www.dailysecu.com/rss/clickTop.xml"
}


# ============================================================
# 3. 보안 / 사이버 범죄 관련 기사 필터링용 키워드
# ============================================================

security_keywords = [
    "해킹", "해커",
    "랜섬웨어",
    "피싱", "스미싱",
    "악성코드", "악성 프로그램",
    "개인정보 유출", "정보 유출", "데이터 유출",
    "계정 탈취", "정보 탈취",
    "사이버 공격", "사이버 범죄",
    "침해 사고", "보안 사고",
    "취약점", "제로데이",
    "디도스", "DDoS",
    "APT", "CVE", "익스플로잇",

    "hacking", "hacker",
    "cyberattack", "cyber attack", "cybercrime",
    "ransomware",
    "phishing",
    "malware",
    "breach", "data breach",
    "vulnerability",
    "exploit",
    "zero-day", "zero day",
    "infostealer",
    "botnet",
    "ddos",
    "credential theft"
]


# ============================================================
# 4. 프로젝트에서 제외할 기사
# ============================================================

exclude_keywords = [
    "교육생 모집",
    "채용",
    "인사",
    "수상",
    "업무협약",
    "MOU",
    "이벤트",
    "장학생",
    "공모전"
]


# ============================================================
# 5. 기사 카테고리 분류
# ============================================================

def get_category(text):

    text = text.lower()

    if "랜섬웨어" in text or "ransomware" in text:
        return "랜섬웨어"

    elif (
        "피싱" in text
        or "phishing" in text
        or "스미싱" in text
    ):
        return "피싱/스미싱"

    elif (
        "악성코드" in text
        or "malware" in text
        or "infostealer" in text
    ):
        return "악성코드"

    elif (
        "개인정보 유출" in text
        or "데이터 유출" in text
        or "data breach" in text
        or "breach" in text
    ):
        return "정보유출"

    elif (
        "취약점" in text
        or "vulnerability" in text
        or "cve" in text
        or "zero-day" in text
    ):
        return "취약점"

    elif (
        "해킹" in text
        or "해커" in text
        or "hacking" in text
        or "hacker" in text
        or "cyberattack" in text
    ):
        return "해킹"

    else:
        return "기타 보안"


# ============================================================
# 6. RSS 수집 및 MongoDB 저장
# ============================================================

def collect_and_save():

    print("\n" + "=" * 80)
    print(f"RSS 데이터 수집 시작 : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    news_list = []

    # --------------------------------------------------------
    # RSS 기사 수집
    # --------------------------------------------------------

    for source, url in rss_sources.items():

        print(f"\n[{source}] RSS 수집 중...")

        feed = feedparser.parse(url)

        # 사이트별 기사 최대 30개 확인
        for news in feed.entries[:30]:

            title = news.get("title", "")
            summary = news.get("summary", "")

            # 제목 + 요약을 합쳐서 키워드 검색
            check_text = f"{title} {summary}".lower()


            # ------------------------------------------------
            # 보안 관련 기사인지 확인
            # ------------------------------------------------

            is_security_news = False

            for keyword in security_keywords:

                if keyword.lower() in check_text:
                    is_security_news = True
                    break


            # ------------------------------------------------
            # 프로젝트에서 제외할 기사인지 확인
            # ------------------------------------------------

            is_excluded = False

            for keyword in exclude_keywords:

                if keyword.lower() in check_text:
                    is_excluded = True
                    break


            # ------------------------------------------------
            # 보안 관련 기사만 저장
            # ------------------------------------------------

            if is_security_news and not is_excluded:

                # RSS 게시일
                published_parsed = news.get("published_parsed")

                if published_parsed:

                    published_dt = datetime(*published_parsed[:6])

                    published_text = published_dt.strftime(
                        "%Y년 %m월 %d일 %H시 %M분"
                    )

                else:

                    published_dt = None
                    published_text = "게시일 정보 없음"


                # MongoDB에 저장할 데이터
                news_data = {
                    "source": source,
                    "category": get_category(check_text),
                    "title": title,
                    "link": news.get("link", ""),
                    "published": published_text,
                    "sort_date": published_dt
                }

                news_list.append(news_data)


    # ========================================================
    # RSS 수집 과정에서 1차 중복 제거
    # ========================================================

    unique_news = []
    checked_links = set()

    for news in news_list:

        link = news["link"]

        if link and link not in checked_links:

            checked_links.add(link)
            unique_news.append(news)

    news_list = unique_news


    # ========================================================
    # 게시일 기준 정렬
    # ========================================================

    news_list.sort(
        key=lambda news: (
            news["sort_date"] is None,
            news["sort_date"] or datetime.max
        )
    )


    # ========================================================
    # MongoDB 저장
    # ========================================================

    insert_count = 0
    duplicate_count = 0

    print("\n--- MongoDB 저장 시작 ---")

    for news in news_list:

        try:

            collection.insert_one(news)

            insert_count += 1

            print(f"저장 완료 : {news['title']}")

        except DuplicateKeyError:

            duplicate_count += 1

            print(f"중복 기사 : {news['title']}")


    # ========================================================
    # 수집 결과
    # ========================================================

    print("\n" + "=" * 80)
    print("수집 및 MongoDB 저장 결과")
    print("=" * 80)

    print(f"수집된 보안 기사 : {len(news_list)}개")
    print(f"새로 저장된 기사 : {insert_count}개")
    print(f"중복으로 제외된 기사 : {duplicate_count}개")

    print("=" * 80)


# ============================================================
# 7. 자동 실행 일정 설정
# ============================================================

# 하루 2번 실행
# 오전 09:00
schedule.every().day.at("09:00").do(collect_and_save)

# 오후 21:00
schedule.every().day.at("21:00").do(collect_and_save)


# ============================================================
# 8. 프로그램 시작 시 한 번 즉시 실행
# ============================================================

print("\n자동 RSS 수집 프로그램 시작")
print("실행 일정 : 매일 09:00 / 21:00")
print("프로그램을 종료하려면 Ctrl + C를 누르세요.")

# 프로그램 실행 직후 한 번 수집
collect_and_save()


# ============================================================
# 9. 스케줄 대기
# ============================================================

try:

    while True:

        schedule.run_pending()

        time.sleep(60)

except KeyboardInterrupt:

    print("\n프로그램 종료")


# ============================================================
# 10. MongoDB 연결 종료
# ============================================================

client.close()

print("MongoDB 연결 종료")