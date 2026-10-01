import feedparser
from datetime import datetime


# RSS 주소
rss_sources = {
    "ASEC": "https://asec.ahnlab.com/ko/feed/",
    "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "DailySecu": "https://www.dailysecu.com/rss/clickTop.xml"
}


# 보안 / 사이버 범죄 관련 기사 필터링용 키워드
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


# 보안 기사여도 프로젝트에서 필요 없는 내용 제외
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


# 기사 내용을 기준으로 카테고리 분류
def get_category(text):

    text = text.lower()

    if "랜섬웨어" in text or "ransomware" in text:
        return "랜섬웨어"

    elif "피싱" in text or "phishing" in text or "스미싱" in text:
        return "피싱/스미싱"

    elif "악성코드" in text or "malware" in text or "infostealer" in text:
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


news_list = []


# RSS 사이트를 하나씩 확인
for source, url in rss_sources.items():

    feed = feedparser.parse(url)

    # 사이트별 기사 최대 30개 확인
    for news in feed.entries[:30]:

        title = news.get("title", "")
        summary = news.get("summary", "")

        # 제목과 요약을 합쳐서 키워드 검색
        check_text = f"{title} {summary}".lower()


        is_security_news = False

        for keyword in security_keywords:

            if keyword.lower() in check_text:
                is_security_news = True
                break


        is_excluded = False

        for keyword in exclude_keywords:

            if keyword.lower() in check_text:
                is_excluded = True
                break


        # 보안 관련 기사만 최종 저장
        if is_security_news and not is_excluded:

            # RSS 게시일을 날짜 형식으로 변환
            published_parsed = news.get("published_parsed")

            if published_parsed:
                published_dt = datetime(*published_parsed[:6])

                # 년 / 월 / 일 / 시 / 분 형식으로 변경
                published_text = published_dt.strftime(
                    "%Y년 %m월 %d일 %H시 %M분"
                )
            else:
                published_dt = None
                published_text = "게시일 정보 없음"


            news_data = {
                "source": source,
                "category": get_category(check_text),
                "title": title,
                "link": news.get("link", ""),
                "published": published_text,

                # 날짜 정렬을 위한 값
                "sort_date": published_dt
            }

            news_list.append(news_data)


# 같은 링크의 중복 기사 제거
unique_news = []
checked_links = set()

for news in news_list:

    link = news["link"]

    if link not in checked_links:
        checked_links.add(link)
        unique_news.append(news)


news_list = unique_news


# 게시일 기준 오름차순 정렬
# 날짜가 없는 기사는 마지막으로 이동
news_list.sort(
    key=lambda news: (
        news["sort_date"] is None,
        news["sort_date"] or datetime.max
    )
)


# 수집 결과 확인
for news in news_list:

    print(f"출처 : {news['source']}")
    print(f"분류 : {news['category']}")
    print(f"제목 : {news['title']}")
    print(f"게시일 : {news['published']}")
    print(f"링크 : {news['link']}")
    print("-" * 80)


print(f"\n보안 관련 기사 총 {len(news_list)}개")