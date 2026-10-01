# -*- coding: utf-8 -*-
"""
CyberWatch - 사이버보안 통합 대시보드 (Flask + MongoDB)
실행: venv\Scripts\python.exe app.py
"""
import re
from math import ceil

from flask import Flask, render_template, request, redirect, url_for, jsonify
from pymongo import MongoClient, DESCENDING, ASCENDING

import seed as seeder

# flask 웹 애플리케이션 객체를 생성하고 app 변수에 저장
app = Flask(__name__)

# mongodb 연동
client = MongoClient(seeder.MONGO_URI)
db = client[seeder.DB_NAME]

NAV = [
    ("index", "홈", "🏠"),
    ("news", "보안 뉴스", "📰"),
    ("stats", "사이버범죄 통계", "📊"),
    ("trend", "연도별 추이", "📈"),
    ("data", "데이터 원본", "🗄️"),
    ("about", "정보", "ℹ️"),
]


# ---------- 공통 헬퍼 ----------
def ensure_seeded():
    """DB가 비어 있으면 예시 데이터를 자동 적재"""
    if db.categories.count_documents({}) == 0:
        seeder.seed(client)


def get_categories():
    return list(db.categories.find({}, {"_id": 0}).sort("order", ASCENDING))


def get_last_updated():
    doc = db.meta.find_one({"key": "last_updated"})
    return doc["value"] if doc else None


def latest_year():
    doc = db.stats.find_one(sort=[("year", DESCENDING)])
    return doc["year"] if doc else None


def summary_cards(year):
    """상단 카드: 해당 연도 유형별 건수와 전년 대비 증감률"""
    cards = []
    for cat in get_categories():
        s = db.stats.find_one({"year": year, "category_key": cat["key"]})
        cards.append({**cat, "count": s["count"] if s else 0,
                      "yoy": s.get("yoy_change") if s else None})
    return cards


@app.context_processor
def inject_globals():
    ensure_seeded()
    year = latest_year()
    return {
        "nav": NAV,
        "last_updated": get_last_updated(),
        "cards": summary_cards(year) if year else [],
        "card_year": year,
    }


@app.template_filter("comma")
def comma(n):
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return n


# ---------- 홈: 색인/검색 ----------
def build_news_query(q, category, source, year, tag):
    cond = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        cond["$or"] = [{"title": rx}, {"summary": rx}, {"tags": rx}, {"source": rx}, {"category": rx}]
    if category:
        cond["category"] = category
    if source:
        cond["source"] = source
    if tag:
        cond["tags"] = tag
    if year:
        try:
            y = int(year)
            cond["date"] = {"$gte": seeder.datetime(y, 1, 1), "$lt": seeder.datetime(y + 1, 1, 1)}
        except ValueError:
            pass
    return cond


def facet(field, cond=None):
    """필드별 건수 집계 (색인 패널용)"""
    pipeline = []
    if cond:
        pipeline.append({"$match": cond})
    if field == "tags":
        pipeline.append({"$unwind": "$tags"})
    if field == "year":
        pipeline.append({"$group": {"_id": {"$year": "$date"}, "n": {"$sum": 1}}})
    else:
        pipeline.append({"$group": {"_id": f"${field}", "n": {"$sum": 1}}})
    pipeline.append({"$sort": {"n": -1, "_id": 1}})
    return [{"value": d["_id"], "count": d["n"]} for d in db.news.aggregate(pipeline)]


@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    source = request.args.get("source", "")
    year = request.args.get("year", "")
    tag = request.args.get("tag", "")
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 10

    cond = build_news_query(q, category, source, year, tag)
    total = db.news.count_documents(cond)
    results = list(db.news.find(cond).sort("date", DESCENDING)
                   .skip((page - 1) * per_page).limit(per_page))

    # 통계 컬렉션도 함께 검색 (유형명 일치)
    stat_hits = []
    if q:
        stat_hits = list(db.stats.find({"category": {"$regex": re.escape(q), "$options": "i"}})
                         .sort([("year", DESCENDING), ("count", DESCENDING)]).limit(12))

    return render_template(
        "index.html",
        q=q, category=category, source=source, year=year, tag=tag,
        results=results, total=total, page=page, pages=ceil(total / per_page) if total else 1,
        stat_hits=stat_hits,
        facet_category=facet("category"),
        facet_source=facet("source"),
        facet_year=facet("year"),
        facet_tags=facet("tags")[:30],
        collection_counts={c: db[c].estimated_document_count() for c in ("news", "stats", "categories", "sources")},
    )


@app.route("/api/search")
def api_search():
    """검색 API (JSON)"""
    cond = build_news_query(request.args.get("q", "").strip(), request.args.get("category", ""),
                            request.args.get("source", ""), request.args.get("year", ""),
                            request.args.get("tag", ""))
    docs = []
    for d in db.news.find(cond).sort("date", DESCENDING).limit(50):
        d["_id"] = str(d["_id"])
        d["date"] = d["date"].strftime("%Y-%m-%d")
        docs.append(d)
    return jsonify({"total": len(docs), "results": docs})


# ---------- 보안 뉴스 ----------
@app.route("/news")
def news():
    category = request.args.get("category", "")
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 8
    cond = {"category": category} if category else {}
    total = db.news.count_documents(cond)
    items = list(db.news.find(cond).sort("date", DESCENDING)
                 .skip((page - 1) * per_page).limit(per_page))
    # 유형 이름 → 카드와 같은 아이콘/색 (base.html 카드와 동일한 categories 컬렉션)
    icons = {c["name"]: c for c in get_categories()}
    return render_template("news.html", items=items, category=category, total=total,
                           page=page, pages=ceil(total / per_page) if total else 1,
                           categories=facet("category"), icons=icons)


# ---------- 사이버범죄 통계 ----------
@app.route("/stats")
def stats():
    years = sorted(db.stats.distinct("year"), reverse=True)
    year = int(request.args.get("year", years[0]))
    rows = list(db.stats.find({"year": year}, {"_id": 0}))
    order = {c["key"]: c for c in get_categories()}
    rows.sort(key=lambda r: order[r["category_key"]]["order"])
    for r in rows:
        r["color"] = order[r["category_key"]]["color"]
    total = sum(r["count"] for r in rows)
    for r in rows:
        r["ratio"] = round(r["count"] / total * 100, 1) if total else 0
    return render_template("stats.html", rows=rows, year=year, years=years, total=total)


# ---------- 연도별 추이 ----------
@app.route("/trend")
def trend():
    years = sorted(db.stats.distinct("year"))
    cats = get_categories()
    table = {}
    for s in db.stats.find({}, {"_id": 0}):
        table.setdefault(s["category_key"], {})[s["year"]] = s["count"]
    series = [{"name": c["name"], "color": c["color"],
               "data": [table.get(c["key"], {}).get(y, 0) for y in years]} for c in cats]
    totals = [sum(table.get(c["key"], {}).get(y, 0) for c in cats) for y in years]
    return render_template("trend.html", years=years, series=series, totals=totals)


# ---------- 데이터 원본 ----------
@app.route("/data")
def data():
    collection = request.args.get("collection", "news")
    allowed = ["news", "stats", "categories", "sources", "meta"]
    if collection not in allowed:
        collection = "news"
    docs = []
    for d in db[collection].find().limit(100):
        d["_id"] = str(d["_id"])
        docs.append(d)
    columns = []
    for d in docs:
        for k in d:
            if k not in columns:
                columns.append(k)
    counts = {c: db[c].estimated_document_count() for c in allowed}
    sources = list(db.sources.find({}, {"_id": 0}))
    return render_template("data.html", collection=collection, docs=docs, columns=columns,
                           counts=counts, sources=sources, allowed=allowed)


# ---------- 정보 ----------
@app.route("/about")
def about():
    info = client.server_info()
    return render_template("about.html", mongo_version=info.get("version"),
                           db_name=seeder.DB_NAME, collections=db.list_collection_names())


# ---------- 데이터 새로고침 (예시 데이터 재적재) ----------
@app.route("/refresh", methods=["POST"])
def refresh():
    seeder.seed(client)
    return redirect(request.referrer or url_for("index"))


# 개발시 python 실행가능하도록
if __name__ == "__main__":
    app.run(debug=True)
