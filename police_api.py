import os

import requests
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

load_dotenv()

API_KEY = os.getenv("POLICE_API_KEY")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
API_URL = "https://api.odcloud.kr/api/15053887/v1/uddi:4a0b64ee-fee2-42c1-802b-99c651d5260a"

# app.py 와 반드시 같은 DB를 사용
DB_NAME = "cybercrime_db"
COLLECTION_NAME = "police_stats"

# 출력용 라벨 : API 필드명 dd
FIELDS = {
    "랜섬웨어": "악성프로그램_랜섬웨어",
    "피싱": "사이버금융범죄_피싱",
    "스미싱": "정보탈취연계형범죄_스미싱",
    "개인정보 유출": "해킹_자료유출",
    "DDoS": "서비스거부공격",
    "악성코드": "악성프로그램_기타",
    "계정 탈취": "해킹_계정도용",
}

if not API_KEY:
    raise ValueError(".env 파일에 POLICE_API_KEY가 없습니다.")


def fetch_data():
    """경찰청 API 데이터를 가져온다."""
    params = {"page": 1, "perPage": 100, "returnType": "JSON", "serviceKey": API_KEY}
    response = requests.get(API_URL, params=params, timeout=10)
    response.raise_for_status()
    return response, response.json()


def save_to_mongo(items):
    """(연도, 구분)이 같으면 덮어써서 중복을 막고, 한 번에 저장한다."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    collection = client[DB_NAME][COLLECTION_NAME]

    collection.bulk_write([
        UpdateOne({"연도": i.get("연도"), "구분": i.get("구분")}, {"$set": i}, upsert=True)
        for i in items
    ])
    return collection.count_documents({})


def print_occurrence(items):
    """'발생건수' 항목만 출력한다."""
    print("\n--- 사이버 범죄 발생건수 ---")
    for item in (i for i in items if i.get("구분") == "발생건수"):
        print(f"\n연도 : {item.get('연도')}년")
        print("\n".join(f"{label} : {item.get(key)}건" for label, key in FIELDS.items()))


def main():
    response, data = fetch_data()
    print(f"상태 코드 : {response.status_code}")
    print(f"전체 데이터 수 : {data.get('totalCount')}")
    print(f"현재 데이터 수 : {data.get('currentCount')}")

    items = data.get("data", [])
    if not items:
        print("가져온 데이터가 없습니다.")
        return

    try:
        total = save_to_mongo(items)
        print(f"\nMongoDB 저장 완료 : {DB_NAME}.{COLLECTION_NAME} (총 {total}건)")
    except PyMongoError as e:
        print(f"\nMongoDB 연결/저장 실패 : {e}")

    print_occurrence(items)


if __name__ == "__main__":
    main()