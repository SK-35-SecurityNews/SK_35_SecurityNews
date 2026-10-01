import os
import requests
from dotenv import load_dotenv

# .env 파일의 환경변수 불러오기
load_dotenv()

# 경찰청 API 인증키
API_KEY = os.getenv("POLICE_API_KEY")

# 경찰청 연도별 사이버 범죄 통계 API
API_URL = (
    "https://api.odcloud.kr/api/15053887/v1/"
    "uddi:4a0b64ee-fee2-42c1-802b-99c651d5260a"
)

# API 키가 없으면 실행 중단
if not API_KEY:
    raise ValueError(".env 파일에 POLICE_API_KEY가 없습니다.")

# API 요청 조건 설정
params = {
    "page": 1,
    "perPage": 10,
    "returnType": "JSON",
    "serviceKey": API_KEY
}

# 경찰청 API 데이터 요청
response = requests.get(
    API_URL,
    params=params,
    timeout=10
)

# 요청 실패 시 오류 발생
response.raise_for_status()

# 응답 데이터를 JSON 형태로 변환
data = response.json()


# API 요청 결과 확인
print(f"상태 코드 : {response.status_code}")
print(f"전체 데이터 수 : {data.get('totalCount')}")
print(f"현재 데이터 수 : {data.get('currentCount')}")

print("\n--- 사이버 범죄 발생건수 ---")


# 전체 데이터 중 '발생건수' 항목만 출력
for item in data.get("data", []):

    if item.get("구분") == "발생건수":

        print(f"\n연도 : {item.get('연도')}년")
        print(f"랜섬웨어 : {item.get('악성프로그램_랜섬웨어')}건")
        print(f"피싱 : {item.get('사이버금융범죄_피싱')}건")
        print(f"스미싱 : {item.get('정보탈취연계형범죄_스미싱')}건")
        print(f"개인정보 유출 : {item.get('해킹_자료유출')}건")
        print(f"DDoS : {item.get('서비스거부공격')}건")
        print(f"악성코드 : {item.get('악성프로그램_기타')}건")
        print(f"계정 탈취 : {item.get('해킹_계정도용')}건")