# -*- coding: utf-8 -*-
"""
CyberWatch - 사이버보안 통합 대시보드 (Flask + MongoDB)

cybercrime_db.news         : rss_.py 가 수집한 보안 뉴스
cybercrime_db.police_stats : police_api.py 가 저장한 경찰청 연도별 통계
"""
import contextlib
import io
import os
import re
from datetime import datetime, timedelta
from math import ceil

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from pymongo import ASCENDING, DESCENDING, MongoClient

load_dotenv()

# ---------- 설정 ----------
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "cybercrime_db"
COLLECTION_NAME = "news"
POLICE_COLLECTION = "police_stats"

RSS_SCRIPT = os.environ.get(
    "RSS_SCRIPT", r"C:\Users\taehyi\OneDrive\문서\github\SK_35_SecurityNews\rss_.py")

app = Flask(__name__)

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
news_col = db[COLLECTION_NAME]
police_col = db[POLICE_COLLECTION]

CATEGORIES = [
    {"key": "ransomware", "name": "랜섬웨어",   "icon": "🔒", "color": "#ef4444", "bg": "#fef2f2"},
    {"key": "phishing",   "name": "피싱/스미싱", "icon": "✉️", "color": "#3b82f6", "bg": "#eff6ff"},
    {"key": "malware",    "name": "악성코드",   "icon": "🐞", "color": "#f97316", "bg": "#fff7ed"},
    {"key": "leak",       "name": "정보유출",   "icon": "👤", "color": "#eab308", "bg": "#fefce8"},
    {"key": "vuln",       "name": "취약점",     "icon": "🛡️", "color": "#22c55e", "bg": "#f0fdf4"},
    {"key": "hacking",    "name": "해킹",       "icon": "💻", "color": "#a855f7", "bg": "#faf5ff"},
    {"key": "etc",        "name": "기타 보안",  "icon": "📌", "color": "#06b6d4", "bg": "#ecfeff"},
]
CATEGORY_BY_NAME = {c["name"]: c for c in CATEGORIES}

# 경찰청 통계 : (표시 이름, API 필드명)
POLICE_FIELDS = [
    ("랜섬웨어", "악성프로그램_랜섬웨어"),
    ("피싱", "사이버금융범죄_피싱"),
    ("스미싱", "정보탈취연계형범죄_스미싱"),
    ("개인정보 유출", "해킹_자료유출"),
    ("DDoS", "서비스거부공격"),
    ("악성코드", "악성프로그램_기타"),
    ("계정 탈취", "해킹_계정도용"),
]

POLICE_STYLE = {
    "랜섬웨어": ("🔒", "#ef4444", "#fef2f2"),
    "피싱": ("✉️", "#3b82f6", "#eff6ff"),
    "스미싱": ("📱", "#06b6d4", "#ecfeff"),
    "개인정보 유출": ("👤", "#eab308", "#fefce8"),
    "DDoS": ("🌐", "#22c55e", "#f0fdf4"),
    "악성코드": ("🐞", "#f97316", "#fff7ed"),
    "계정 탈취": ("🔑", "#a855f7", "#faf5ff"),
}

NAV = [
    ("index", "홈", "🏠"),
    ("news", "보안 뉴스", "📰"),
    ("stats", "사이버범죄 통계", "📊"),
    ("trend", "기간별 추이", "📈"),
    ("data", "데이터 원본", "🗄️"),
    ("about", "정보", "ℹ️"),
]

SORT = [("sort_date", DESCENDING), ("_id", DESCENDING)]
PER_PAGE = 10


# ---------- 공통 헬퍼 ----------
def category_info(name):
    return CATEGORY_BY_NAME.get(name, {"name": name, "icon": "📰", "color": "#64748b", "bg": "#f1f5f9"})


def to_int(value):
    """'1,234' 같은 문자열도 정수로 변환, 실패하면 0"""
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0


def get_page():
    try:
        return max(int(request.args.get("page", 1)), 1)
    except ValueError:
        return 1


def total_pages(total):
    return ceil(total / PER_PAGE) if total else 1


def latest_collected():
    doc = news_col.find_one({"sort_date": {"$ne": None}}, sort=[("sort_date", DESCENDING)])
    return doc["sort_date"] if doc else None


def summary_cards():
    """상단 카드: 경찰청 최신 연도 발생건수와 전년 대비 증감률"""
    docs = list(police_col.find({"구분": "발생건수"}, {"_id": 0}).sort("연도", DESCENDING).limit(2))
    if not docs:
        return []
    latest, prev = docs[0], (docs[1] if len(docs) > 1 else None)

    cards = []
    for label, key in POLICE_FIELDS:
        icon, color, bg = POLICE_STYLE[label]
        count = to_int(latest.get(key))
        before = to_int(prev.get(key)) if prev else 0
        change = round((count - before) / before * 100, 1) if before else None
        cards.append({"name": label, "icon": icon, "color": color, "bg": bg,
                      "count": count, "year": latest.get("연도"),
                      "prev_year": prev.get("연도") if prev else None, "change": change})
    return cards

def police_latest():
    """가장 최근 연도의 경찰청 발생건수 (유형명 → 건수)"""
    doc = police_col.find_one({"구분": "발생건수"}, {"_id": 0}, sort=[("연도", DESCENDING)])
    if not doc:
        return None
    return {
        "year": doc.get("연도"),
        "items": [{"name": label, "count": to_int(doc.get(key))} for label, key in POLICE_FIELDS],
    }

@app.context_processor
def inject_globals():
    return {
        "nav": NAV,
        "last_updated": latest_collected(),
        "cards": summary_cards(),
        "total_news": news_col.estimated_document_count(),
        "db_name": DB_NAME,
        "POLICE_STYLE": POLICE_STYLE,
        "police_total": police_col.estimated_document_count(),
    }

@app.template_filter("comma")
def comma(n):
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return n


@app.template_filter("datefmt")
def datefmt(doc, fmt="%Y.%m.%d %H:%M"):
    d = doc.get("sort_date")
    return d.strftime(fmt) if d else doc.get("published", "-")


@app.template_filter("cat")
def cat_filter(name):
    return category_info(name)


# ---------- 검색 조건 / 집계 ----------
def month_range(ym):
    """'2026-09' → (9월 1일, 10월 1일)"""
    y, m = map(int, ym.split("-"))
    return datetime(y, m, 1), datetime(y + m // 12, m % 12 + 1, 1)


def build_query(q, category, source, month):
    cond = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        cond["$or"] = [{f: rx} for f in ("title", "source", "category", "link")]
    if category:
        cond["category"] = category
    if source:
        cond["source"] = source
    if month:
        try:
            start, end = month_range(month)
            cond["sort_date"] = {"$gte": start, "$lt": end}
        except ValueError:
            pass
    return cond

def facet(field):
    """필드별 건수 집계. field = 'category' | 'source' | 'month'"""
    if field == "month":
        pipeline = [
            {"$match": {"sort_date": {"$ne": None}}},
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$sort_date"}},
                        "n": {"$sum": 1}}},
            {"$sort": {"_id": -1}},
        ]
    else:
        pipeline = [
            {"$group": {"_id": f"${field}", "n": {"$sum": 1}}},
            {"$sort": {"n": -1, "_id": 1}},
        ]
    return [{"value": d["_id"], "count": d["n"]} for d in news_col.aggregate(pipeline) if d["_id"]]


# ---------- 홈 ----------
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    source = request.args.get("source", "")
    month = request.args.get("month", "")
    page = get_page()

    cond = build_query(q, category, source, month)
    total = news_col.count_documents(cond)
    results = list(news_col.find(cond).sort(SORT).skip((page - 1) * PER_PAGE).limit(PER_PAGE))

    # 색인 · 유형: 대시보드 카드(경찰청 분류)의 값
    latest = police_col.find_one({"구분": "발생건수"}, {"_id": 0}, sort=[("연도", DESCENDING)]) or {}
    facet_police = [{"value": label, "count": to_int(latest.get(key)), "year": latest.get("연도")}
                    for label, key in POLICE_FIELDS]

    return render_template(
        "index.html", q=q, category=category, source=source, month=month,
        results=results, total=total, page=page, pages=total_pages(total),
        facet_category=facet("category"), facet_source=facet("source"), facet_month=facet("month"),
        facet_police=facet_police,
    )

@app.route("/api/search")
def api_search():
    cond = build_query(request.args.get("q", "").strip(), request.args.get("category", ""),
                       request.args.get("source", ""), request.args.get("month", ""))
    docs = [
        {**d, "_id": str(d["_id"]),
         "sort_date": d["sort_date"].isoformat() if d.get("sort_date") else None}
        for d in news_col.find(cond).sort(SORT).limit(50)
    ]
    return jsonify({"total": len(docs), "results": docs})


# ---------- 보안 뉴스 ----------
@app.route("/news")
def news():
    category = request.args.get("category", "")
    source = request.args.get("source", "")
    page = get_page()

    cond = {k: v for k, v in (("category", category), ("source", source)) if v}
    total = news_col.count_documents(cond)
    items = list(news_col.find(cond).sort(SORT).skip((page - 1) * PER_PAGE).limit(PER_PAGE))
    return render_template("news.html", items=items, category=category, source=source, total=total,
                           page=page, pages=total_pages(total),
                           categories=facet("category"), sources=facet("source"))


# ---------- 사이버범죄 통계 (뉴스 집계 + 경찰청 통계) ----------
@app.route("/stats")
def stats():
    total = news_col.estimated_document_count()

    # 뉴스 유형별 집계
    rows = [
        {"name": f["value"], "count": f["count"],
         "color": category_info(f["value"])["color"], "icon": category_info(f["value"])["icon"],
         "ratio": round(f["count"] / total * 100, 1) if total else 0}
        for f in facet("category")
    ]

    # 출처 × 유형 교차표
    pivot = {}
    for d in news_col.aggregate([{"$group": {"_id": {"s": "$source", "c": "$category"}, "n": {"$sum": 1}}}]):
        pivot.setdefault(d["_id"]["s"], {})[d["_id"]["c"]] = d["n"]
    cat_names = [r["name"] for r in rows]
    source_rows = [{"source": s, "counts": [pivot[s].get(c, 0) for c in cat_names],
                    "total": sum(pivot[s].values())} for s in sorted(pivot)]

    # 경찰청 연도별 발생건수
    police_docs = list(police_col.find({"구분": "발생건수"}, {"_id": 0}).sort("연도", ASCENDING))
    police_years = [d.get("연도") for d in police_docs]
    police_rows = [
        {"name": label, "data": [to_int(d.get(key)) for d in police_docs]}
        for label, key in POLICE_FIELDS
    ]

    return render_template("stats.html", rows=rows, total=total, cat_names=cat_names,
                           source_rows=source_rows, police_years=police_years,
                           police_rows=police_rows)


# ---------- 기간별 추이 ----------dd
@app.route("/trend")
def trend():
    days = int(request.args.get("days", 30))
    start = datetime.combine((datetime.now() - timedelta(days=days - 1)).date(), datetime.min.time())
    labels = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

    counts = {}
    for d in news_col.aggregate([
        {"$match": {"sort_date": {"$gte": start}}},
        {"$group": {"_id": {"day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$sort_date"}},
                            "cat": "$category"}, "n": {"$sum": 1}}},
    ]):
        counts.setdefault(d["_id"]["cat"], {})[d["_id"]["day"]] = d["n"]

    series = [
        {"name": c["name"], "color": c["color"], "data": data, "total": sum(data)}
        for c in CATEGORIES
        if any(data := [counts.get(c["name"], {}).get(day, 0) for day in labels])
    ]
    totals = [sum(s["data"][i] for s in series) for i in range(days)]

    monthly = {}
    for d in news_col.aggregate([
        {"$match": {"sort_date": {"$ne": None}}},
        {"$group": {"_id": {"m": {"$dateToString": {"format": "%Y-%m", "date": "$sort_date"}},
                            "cat": "$category"}, "n": {"$sum": 1}}},
    ]):
        monthly.setdefault(d["_id"]["m"], {})[d["_id"]["cat"]] = d["n"]
    months = sorted(monthly)
    month_rows = [
        {"name": c["name"], "color": c["color"], "data": data}
        for c in CATEGORIES
        if any(data := [monthly[m].get(c["name"], 0) for m in months])
    ]
    month_totals = [sum(monthly[m].values()) for m in months]

    return render_template("trend.html", days=days, labels=labels, series=series, totals=totals,
                           months=months, month_rows=month_rows, month_totals=month_totals)


# ---------- 데이터 원본 ----------
@app.route("/data")
def data():
    allowed = db.list_collection_names() or [COLLECTION_NAME]
    collection = request.args.get("collection", COLLECTION_NAME)
    if collection not in allowed:
        collection = allowed[0]

    docs = [{**d, "_id": str(d["_id"])} for d in db[collection].find().sort("_id", DESCENDING).limit(100)]
    columns = list(dict.fromkeys(k for d in docs for k in d))  # 순서 유지 + 중복 제거
    counts = {c: db[c].estimated_document_count() for c in allowed}
    indexes = [{"name": k, "keys": v["key"], "unique": v.get("unique", False)}
               for k, v in db[collection].index_information().items()]
    return render_template("data.html", collection=collection, docs=docs, columns=columns,
                           counts=counts, allowed=allowed, indexes=indexes,
                           rss_script=RSS_SCRIPT, rss_exists=os.path.exists(RSS_SCRIPT))


# ---------- 정보 ----------
@app.route("/about")
def about():
    return render_template("about.html", mongo_version=client.server_info().get("version"),
                           collections=db.list_collection_names(),
                           rss_script=RSS_SCRIPT, rss_exists=os.path.exists(RSS_SCRIPT))


# ---------- 데이터 새로고침 ----------
def run_rss_collect():
    """rss_.py 의 수집 함수만 한 번 실행한다. (스케줄 대기 루프는 제외)"""
    with open(RSS_SCRIPT, encoding="utf-8") as f:
        src = f.read().split("# 7. 자동 실행 일정 설정")[0]

    ns = {"__name__": "rss_collect"}
    before = news_col.estimated_document_count()
    with contextlib.redirect_stdout(io.StringIO()):  # cp949 콘솔 인코딩 오류 방지
        exec(compile(src, RSS_SCRIPT, "exec"), ns)
        ns["collect_and_save"]()
    return news_col.estimated_document_count() - before


@app.route("/refresh", methods=["POST"])
def refresh():
    if not os.path.exists(RSS_SCRIPT):
        msg = "rss_.py 를 찾을 수 없습니다. 환경변수 RSS_SCRIPT 로 경로를 지정하세요."
    else:
        try:
            msg = f"RSS 수집 완료: 새 기사 {run_rss_collect()}건 추가"
        except Exception as e:
            msg = f"RSS 수집 실패: {e}"
    target = request.referrer or url_for("index")
    return redirect(f"{target}{'&' if '?' in target else '?'}msg={msg}")

@app.route("/debug/police")
def debug_police():
    sample = police_col.find_one({"구분": "발생건수"}, {"_id": 0})
    return jsonify({
        "db": DB_NAME,
        "collection": POLICE_COLLECTION,
        "total_docs": police_col.count_documents({}),
        "발생건수_docs": police_col.count_documents({"구분": "발생건수"}),
        "구분_values": police_col.distinct("구분"),
        "sample_연도": sample.get("연도") if sample else None,
        "stats_template_file": app.jinja_env.get_or_select_template("stats.html").filename,
        "app_folder": app.root_path,
    })

if __name__ == "__main__":
    app.run(debug=True)