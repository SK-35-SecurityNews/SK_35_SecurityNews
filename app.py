# -*- coding: utf-8 -*-
"""
CyberWatch - 사이버보안 통합 대시보드 (Flask + MongoDB)

데이터는 rss_.py 가 수집해 MongoDB 에 저장한 cybercrime_db.news 컬렉션을 그대로 사용한다.
문서 구조:
  {
    source:    'ASEC' | 'BleepingComputer' | 'DailySecu',
    category:  '랜섬웨어' | '피싱/스미싱' | '악성코드' | '정보유출' | '취약점' | '해킹' | '기타 보안',
    title:     기사 제목,
    link:      기사 원본 URL (unique index),
    published: '2026년 09월 13일 15시 00분'  (표시용 문자열),
    sort_date: ISODate (정렬·기간 필터용, 없을 수 있음)
  }

실행: venv\Scripts\python.exe app.py
"""
import contextlib
import io
import os
import re
from datetime import datetime, timedelta
from math import ceil

from flask import Flask, render_template, request, redirect, url_for, jsonify
from pymongo import MongoClient, DESCENDING, ASCENDING

# ---------- 설정 ----------
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "cybercrime_db"          # rss_.py 의 DB_NAME
COLLECTION_NAME = "news"           # rss_.py 의 COLLECTION_NAME

# 데이터 새로고침 버튼이 호출할 수집 스크립트 (rss_.py). 없으면 버튼은 안내만 표시한다.
RSS_SCRIPT = os.environ.get(
    "RSS_SCRIPT", r"C:\Users\taehyi\OneDrive\문서\github\SK_35_SecurityNews\rss_.py")

# flask 웹 애플리케이션 객체를 생성하고 app 변수에 저장
app = Flask(__name__)

# mongodb 연동
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
news_col = db[COLLECTION_NAME]

# rss_.py 의 get_category() 가 반환하는 유형 목록 (상단 카드 순서·아이콘·색)
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

NAV = [
    ("index", "홈", "🏠"),
    ("news", "보안 뉴스", "📰"),
    ("stats", "사이버범죄 통계", "📊"),
    ("trend", "기간별 추이", "📈"),
    ("data", "데이터 원본", "🗄️"),
    ("about", "정보", "ℹ️"),
]


# ---------- 공통 헬퍼 ----------
def category_info(name):
    """유형 이름 → 아이콘/색. 목록에 없는 유형은 기본값."""
    return CATEGORY_BY_NAME.get(name, {"name": name, "icon": "📰", "color": "#64748b", "bg": "#f1f5f9"})


def latest_collected():
    """가장 최근 기사의 게시 시각 (= 마지막 수집 기준)"""
    doc = news_col.find_one({"sort_date": {"$ne": None}}, sort=[("sort_date", DESCENDING)])
    return doc["sort_date"] if doc else None


def summary_cards():
    """상단 카드: 유형별 전체 기사 수와 최근 7일 / 이전 7일 비교"""
    now = datetime.now()
    week = now - timedelta(days=7)
    two_weeks = now - timedelta(days=14)
    cards = []
    for cat in CATEGORIES:
        total = news_col.count_documents({"category": cat["name"]})
        recent = news_col.count_documents({"category": cat["name"], "sort_date": {"$gte": week}})
        prev = news_col.count_documents({"category": cat["name"],
                                         "sort_date": {"$gte": two_weeks, "$lt": week}})
        change = None if prev == 0 else round((recent - prev) / prev * 100, 1)
        cards.append({**cat, "count": total, "recent": recent, "prev": prev, "change": change})
    return cards


@app.context_processor
def inject_globals():
    return {
        "nav": NAV,
        "last_updated": latest_collected(),
        "cards": summary_cards(),
        "total_news": news_col.estimated_document_count(),
        "db_name": DB_NAME,
    }


@app.template_filter("comma")
def comma(n):
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return n


@app.template_filter("datefmt")
def datefmt(doc, fmt="%Y.%m.%d %H:%M"):
    """sort_date 가 있으면 포맷, 없으면 published 문자열 그대로"""
    d = doc.get("sort_date")
    return d.strftime(fmt) if d else doc.get("published", "-")


@app.template_filter("cat")
def cat_filter(name):
    return category_info(name)


# ---------- 검색 조건 / 색인 집계 ----------
def month_range(ym):
    """'2026-09' → (9월 1일, 10월 1일)"""
    y, m = (int(x) for x in ym.split("-"))
    start = datetime(y, m, 1)
    end = datetime(y + (m // 12), (m % 12) + 1, 1)
    return start, end


def build_query(q, category, source, month):
    cond = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        cond["$or"] = [{"title": rx}, {"source": rx}, {"category": rx}, {"link": rx}]
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


SORT = [("sort_date", DESCENDING), ("_id", DESCENDING)]


# ---------- 홈: 색인/검색 ----------
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    source = request.args.get("source", "")
    month = request.args.get("month", "")
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 10

    cond = build_query(q, category, source, month)
    total = news_col.count_documents(cond)
    results = list(news_col.find(cond).sort(SORT).skip((page - 1) * per_page).limit(per_page))

    return render_template(
        "index.html",
        q=q, category=category, source=source, month=month,
        results=results, total=total, page=page, pages=ceil(total / per_page) if total else 1,
        facet_category=facet("category"),
        facet_source=facet("source"),
        facet_month=facet("month"),
    )


@app.route("/api/search")
def api_search():
    """검색 API (JSON)"""
    cond = build_query(request.args.get("q", "").strip(), request.args.get("category", ""),
                       request.args.get("source", ""), request.args.get("month", ""))
    docs = []
    for d in news_col.find(cond).sort(SORT).limit(50):
        d["_id"] = str(d["_id"])
        d["sort_date"] = d["sort_date"].isoformat() if d.get("sort_date") else None
        docs.append(d)
    return jsonify({"total": len(docs), "results": docs})


# ---------- 보안 뉴스 ----------
@app.route("/news")
def news():
    category = request.args.get("category", "")
    source = request.args.get("source", "")
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 10
    cond = {}
    if category:
        cond["category"] = category
    if source:
        cond["source"] = source
    total = news_col.count_documents(cond)
    items = list(news_col.find(cond).sort(SORT).skip((page - 1) * per_page).limit(per_page))
    return render_template("news.html", items=items, category=category, source=source, total=total,
                           page=page, pages=ceil(total / per_page) if total else 1,
                           categories=facet("category"), sources=facet("source"))


# ---------- 사이버범죄 통계 (유형별 · 출처별) ----------
@app.route("/stats")
def stats():
    total = news_col.estimated_document_count()
    rows = []
    for f in facet("category"):
        info = category_info(f["value"])
        rows.append({"name": f["value"], "count": f["count"], "color": info["color"], "icon": info["icon"],
                     "ratio": round(f["count"] / total * 100, 1) if total else 0})

    # 출처 × 유형 교차표
    pivot = {}
    for d in news_col.aggregate([{"$group": {"_id": {"s": "$source", "c": "$category"}, "n": {"$sum": 1}}}]):
        pivot.setdefault(d["_id"]["s"], {})[d["_id"]["c"]] = d["n"]
    cat_names = [r["name"] for r in rows]
    source_rows = [{"source": s, "counts": [pivot[s].get(c, 0) for c in cat_names],
                    "total": sum(pivot[s].values())} for s in sorted(pivot)]
    return render_template("stats.html", rows=rows, total=total, cat_names=cat_names, source_rows=source_rows)


# ---------- 기간별 추이 ----------
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

    series = []
    for cat in CATEGORIES:
        data = [counts.get(cat["name"], {}).get(day, 0) for day in labels]
        if any(data):
            series.append({"name": cat["name"], "color": cat["color"], "data": data, "total": sum(data)})
    totals = [sum(s["data"][i] for s in series) for i in range(days)]

    # 월별 × 유형 표
    monthly = {}
    for d in news_col.aggregate([
        {"$match": {"sort_date": {"$ne": None}}},
        {"$group": {"_id": {"m": {"$dateToString": {"format": "%Y-%m", "date": "$sort_date"}},
                            "cat": "$category"}, "n": {"$sum": 1}}},
    ]):
        monthly.setdefault(d["_id"]["m"], {})[d["_id"]["cat"]] = d["n"]
    months = sorted(monthly)
    month_rows = [{"name": c["name"], "color": c["color"],
                   "data": [monthly[m].get(c["name"], 0) for m in months]} for c in CATEGORIES]
    month_rows = [r for r in month_rows if any(r["data"])]
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
    docs = []
    for d in db[collection].find().sort("_id", DESCENDING).limit(100):
        d["_id"] = str(d["_id"])
        docs.append(d)
    columns = []
    for d in docs:
        for k in d:
            if k not in columns:
                columns.append(k)
    counts = {c: db[c].estimated_document_count() for c in allowed}
    indexes = [{"name": k, "keys": v["key"], "unique": v.get("unique", False)}
               for k, v in db[collection].index_information().items()]
    return render_template("data.html", collection=collection, docs=docs, columns=columns,
                           counts=counts, allowed=allowed, indexes=indexes,
                           rss_script=RSS_SCRIPT, rss_exists=os.path.exists(RSS_SCRIPT))


# ---------- 정보 ----------
@app.route("/about")
def about():
    info = client.server_info()
    return render_template("about.html", mongo_version=info.get("version"),
                           collections=db.list_collection_names(),
                           rss_script=RSS_SCRIPT, rss_exists=os.path.exists(RSS_SCRIPT))


# ---------- 데이터 새로고침: rss_.py 의 collect_and_save() 를 한 번 실행 ----------
def run_rss_collect():
    """rss_.py 를 불러와 수집 함수만 실행한다. (스케줄 대기 루프 부분은 제외)"""
    src = io.open(RSS_SCRIPT, encoding="utf-8").read()
    src = src.split("# 7. 자동 실행 일정 설정")[0]
    ns = {"__name__": "rss_collect"}
    before = news_col.estimated_document_count()
    # rss_.py 의 print() 출력은 콘솔(cp949)로 보내지 않고 버퍼에 담는다 (인코딩 오류 방지)
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(src, RSS_SCRIPT, "exec"), ns)
        ns["collect_and_save"]()
    return news_col.estimated_document_count() - before


@app.route("/refresh", methods=["POST"])
def refresh():
    if not os.path.exists(RSS_SCRIPT):
        msg = "rss_.py 를 찾을 수 없습니다. 환경변수 RSS_SCRIPT 로 경로를 지정하세요."
    else:
        try:
            added = run_rss_collect()
            msg = f"RSS 수집 완료: 새 기사 {added}건 추가"
        except Exception as e:  # 수집 실패해도 화면은 계속 동작
            msg = f"RSS 수집 실패: {e}"
    target = request.referrer or url_for("index")
    sep = "&" if "?" in target else "?"
    return redirect(f"{target}{sep}msg={msg}")


# 개발시 python 실행가능하도록
if __name__ == "__main__":
    app.run(debug=True)
