import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 1. 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.write("한국 시간 기준으로 어제의 영화관입장권통합전산망(KOBIS) 박스오피스를 보여줍니다.")


# --------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# --------------------------------------------------

# 배포 서버의 시간이 한국 시간이 아닐 수 있기 때문에
# 반드시 한국 시간(KST)을 기준으로 날짜를 계산합니다.
KST = ZoneInfo("Asia/Seoul")

now_korea = datetime.now(KST)
yesterday = now_korea.date() - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여줄 날짜 형식
display_date = yesterday.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# 3. KOBIS API 주소
# --------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# --------------------------------------------------
# 4. API에서 박스오피스 데이터 가져오기
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    KOBIS API에서 특정 날짜의 일일 박스오피스 데이터를 가져옵니다.

    ttl=3600
    → 같은 날짜를 다시 조회해도 약 1시간 동안은
      API를 다시 호출하지 않고 저장된 결과를 사용합니다.
    """

    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 인증키를 코드에 직접 적지 않습니다.
    try:
        kobis_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 Settings → Secrets에서 "
                "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
            ),
            "data": None
        }

    # API에 전달할 요청값
    params = {
        "key": kobis_key,
        "targetDt": target_dt
    }

    try:
        # KOBIS API 호출
        response = requests.get(
            API_URL,
            params=params,
            timeout=10
        )

        # HTTP 오류가 있는 경우 확인
        response.raise_for_status()

        # JSON 데이터로 변환
        result = response.json()

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청 시간이 초과되었습니다.\n\n"
                "잠시 후 다시 실행해 보거나 인터넷 연결 및 "
                "KOBIS API 상태를 확인해 주세요."
            ),
            "data": None
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API에 요청하지 못했습니다.\n\n"
                f"오류 내용: {e}\n\n"
                "인터넷 연결과 KOBIS API 주소를 확인해 주세요."
            ),
            "data": None
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API에서 올바른 JSON 데이터를 받지 못했습니다.\n\n"
                "KOBIS API의 응답 상태를 확인해 주세요."
            ),
            "data": None
        }

    # --------------------------------------------------
    # 5. 인증키 오류 등 faultInfo 확인
    # --------------------------------------------------

    # 인증키가 잘못되어도 HTTP 상태코드는 200일 수 있습니다.
    # 따라서 반드시 faultInfo가 있는지 확인해야 합니다.
    if "faultInfo" in result:
        fault_info = result["faultInfo"]

        fault_code = fault_info.get("message", "알 수 없는 오류")
        fault_detail = fault_info.get("code", "")

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 내용: {fault_code}\n"
                f"오류 코드: {fault_detail}\n\n"
                "KOBIS_KEY가 올바른지, API 사용 권한과 "
                "호출 조건을 확인해 주세요."
            ),
            "data": None
        }

    # --------------------------------------------------
    # 6. boxOfficeResult 확인
    # --------------------------------------------------

    boxoffice_result = result.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "message": (
                "박스오피스 결과(boxOfficeResult)가 없습니다.\n\n"
                "조회 날짜와 KOBIS API 응답을 확인해 주세요."
            ),
            "data": None
        }

    # 영화 목록 가져오기
    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{target_dt} 날짜의 영화 목록이 없습니다.\n\n"
                "해당 날짜에 박스오피스 데이터가 집계되었는지 "
                "KOBIS에서 확인해 주세요."
            ),
            "data": None
        }

    return {
        "success": True,
        "message": "",
        "data": movie_list
    }


# --------------------------------------------------
# 7. API 호출
# --------------------------------------------------

result = get_boxoffice(target_date)


# --------------------------------------------------
# 8. API 요청 실패 시 안내
# --------------------------------------------------

if not result["success"]:
    st.error("⚠️ 박스오피스 데이터를 불러오지 못했습니다.")

    # 여러 줄의 안내문을 보기 쉽게 표시
    st.warning(result["message"])

    st.info(
        "확인할 항목\n"
        "① Streamlit Cloud Secrets에 KOBIS_KEY가 등록되어 있는지\n"
        "② KOBIS 인증키가 정확한지\n"
        "③ KOBIS API가 정상적으로 응답하는지\n"
        "④ 조회 날짜에 박스오피스 데이터가 존재하는지"
    )

    st.stop()


# --------------------------------------------------
# 9. 영화 데이터를 표 형태로 변환
# --------------------------------------------------

movie_list = result["data"]

df = pd.DataFrame(movie_list)


# --------------------------------------------------
# 10. 숫자 데이터를 실제 숫자로 변환
# --------------------------------------------------

# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 그래프와 정렬에 제대로 사용하기 위해 숫자로 변환합니다.

number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in number_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0).astype(int)


# --------------------------------------------------
# 11. 조회 날짜 표시
# --------------------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")

st.caption(
    "※ 한국 시간 기준으로 어제 데이터를 조회했습니다. "
    "같은 날짜의 결과는 약 1시간 동안 캐시됩니다."
)


# --------------------------------------------------
# 12. 1위 영화 정보
# --------------------------------------------------

# 순위를 기준으로 정렬
df = df.sort_values("rank").reset_index(drop=True)

first_movie = df.iloc[0]

movie_name = first_movie["movieNm"]
first_audience = first_movie["audiCnt"]
first_total = first_movie["audiAcc"]
first_screens = first_movie["scrnCnt"]


# --------------------------------------------------
# 13. 1위 영화 지표 카드 3개
# --------------------------------------------------

st.subheader(f"🥇 1위: {movie_name}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="오늘 관객수",
        value=f"{first_audience:,}명"
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{first_total:,}명"
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{first_screens:,}개"
    )


# --------------------------------------------------
# 14. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서대로 5편 선택
top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .copy()
)

# 그래프에서 영화 이름과 관객수를 사용합니다.
chart_data = top5.set_index("movieNm")[["audiCnt"]]

st.bar_chart(
    chart_data,
    x_label="영화",
    y_label="관객수"
)


# --------------------------------------------------
# 15. 전체 박스오피스 표
# --------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

# 사용자에게 보여줄 열만 선택
table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 표의 열 이름을 한국어로 변경
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# 숫자를 천 단위 쉼표로 표시
# 실제 데이터는 숫자 상태를 유지하면서 화면에서만 보기 좋게 표시합니다.
st.dataframe(
    table_df.style.format({
        "관객수": "{:,}",
        "누적관객": "{:,}",
        "스크린수": "{:,}"
    }),
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 16. 데이터 안내
# --------------------------------------------------

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) 일일 박스오피스 API"
)
