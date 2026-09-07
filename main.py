
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 1. 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일일 박스오피스")
st.write(
    "달력에서 날짜를 선택하면 해당 날짜의 영화관입장권통합전산망(KOBIS) "
    "박스오피스를 확인할 수 있습니다."
)


# --------------------------------------------------
# 2. 한국 시간 기준 날짜 계산
# --------------------------------------------------

# Streamlit Cloud 서버의 시간은 한국 시간이 아닐 수 있습니다.
# 따라서 한국 시간(KST)을 기준으로 날짜를 계산합니다.
KST = ZoneInfo("Asia/Seoul")

now_korea = datetime.now(KST)

# 오늘 날짜
today = now_korea.date()

# 오늘의 박스오피스는 아직 집계 전이므로
# 선택할 수 있는 가장 늦은 날짜를 어제로 설정합니다.
yesterday = today - timedelta(days=1)


# --------------------------------------------------
# 3. 날짜 선택
# --------------------------------------------------

st.subheader("📅 조회 날짜 선택")

selected_date = st.date_input(
    "박스오피스를 확인할 날짜를 선택하세요.",
    value=yesterday,
    max_value=yesterday
)

# KOBIS API가 사용하는 날짜 형식
# 예: 2026년 09월 06일 → 20260906
target_date = selected_date.strftime("%Y%m%d")

# 화면에 표시할 날짜
display_date = selected_date.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# 4. KOBIS API 주소
# --------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# --------------------------------------------------
# 5. KOBIS API 호출 함수
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    KOBIS API에서 선택한 날짜의 박스오피스 데이터를 가져옵니다.

    ttl=3600은 1시간입니다.
    같은 날짜를 1시간 안에 다시 조회하면
    API를 다시 호출하지 않고 저장된 결과를 사용합니다.
    """

    # Streamlit Cloud Secrets에서 인증키를 가져옵니다.
    # 인증키를 코드에 직접 적지 않습니다.
    try:
        kobis_key = st.secrets["KOBIS_KEY"]

    except Exception:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 Settings → Secrets에서 "
                "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
            ),
            "data": None
        }

    # KOBIS API에 전달할 값
    params = {
        "key": kobis_key,
        "targetDt": target_dt
    }

    try:
        # API 호출
        response = requests.get(
            API_URL,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        # JSON 데이터로 변환
        result = response.json()

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API 요청 시간이 초과되었습니다.\n\n"
                "잠시 후 다시 시도하거나 인터넷 연결 및 "
                "KOBIS API 상태를 확인해 주세요."
            ),
            "data": None
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "empty": False,
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
            "empty": False,
            "message": (
                "KOBIS API에서 올바른 데이터를 받지 못했습니다.\n\n"
                "KOBIS API의 응답 상태를 확인해 주세요."
            ),
            "data": None
        }

    # --------------------------------------------------
    # 6. faultInfo 확인
    # --------------------------------------------------

    # KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인합니다.
    if "faultInfo" in result:

        fault_info = result["faultInfo"]

        fault_message = fault_info.get(
            "message",
            "알 수 없는 오류"
        )

        fault_code = fault_info.get(
            "code",
            ""
        )

        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 내용: {fault_message}\n"
                f"오류 코드: {fault_code}\n\n"
                "KOBIS_KEY가 정확한지와 API 사용 조건을 확인해 주세요."
            ),
            "data": None
        }

    # --------------------------------------------------
    # 7. boxOfficeResult 확인
    # --------------------------------------------------

    boxoffice_result = result.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "empty": False,
            "message": (
                "박스오피스 결과를 찾을 수 없습니다.\n\n"
                "조회 날짜와 KOBIS API 응답을 확인해 주세요."
            ),
            "data": None
        }

    # 영화 목록 가져오기
    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )

    # --------------------------------------------------
    # 8. 영화 목록이 비어 있는 경우
    # --------------------------------------------------

    if not movie_list:
        return {
            "success": False,
            "empty": True,
            "message": "그날은 아직 집계 전입니다.",
            "data": None
        }

    # 정상적으로 데이터를 가져온 경우
    return {
        "success": True,
        "empty": False,
        "message": "",
        "data": movie_list
    }


# --------------------------------------------------
# 9. 선택한 날짜의 데이터 가져오기
# --------------------------------------------------

result = get_boxoffice(target_date)


# --------------------------------------------------
# 10. 데이터가 없는 경우
# --------------------------------------------------

if result["empty"]:
    st.warning(
        f"📭 {display_date} 박스오피스 데이터가 없습니다."
    )

    st.info(
        "그날은 아직 집계 전입니다.\n\n"
        "다른 날짜를 선택해 주세요."
    )

    st.stop()


# --------------------------------------------------
# 11. API 요청 자체가 실패한 경우
# --------------------------------------------------

if not result["success"]:

    st.error("⚠️ 박스오피스 데이터를 불러오지 못했습니다.")

    st.warning(result["message"])

    st.info(
        "확인할 항목\n"
        "① Streamlit Cloud Secrets에 KOBIS_KEY가 등록되어 있는지\n"
        "② KOBIS 인증키가 정확한지\n"
        "③ KOBIS API가 정상적으로 응답하는지\n"
        "④ 선택한 날짜에 박스오피스 데이터가 집계되었는지"
    )

    st.stop()


# --------------------------------------------------
# 12. 데이터를 DataFrame으로 변환
# --------------------------------------------------

movie_list = result["data"]

df = pd.DataFrame(movie_list)


# --------------------------------------------------
# 13. 숫자 데이터를 실제 숫자로 변환
# --------------------------------------------------

# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 정렬과 그래프에 사용할 수 있도록 숫자로 변환합니다.

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
# 14. 순위 기준으로 정렬
# --------------------------------------------------

df = df.sort_values(
    "rank",
    ascending=True
).reset_index(drop=True)


# --------------------------------------------------
# 15. 영화명 꾸미기
# --------------------------------------------------

def make_movie_name(row):
    """
    누적관객이 100만 명 이상이면
    영화명 뒤에 트로피 이모지를 붙입니다.
    """

    movie_name = row["movieNm"]

    if row["audiAcc"] >= 1_000_000:
        return f"{movie_name} 🏆"

    return movie_name


df["movieNmDisplay"] = df.apply(
    make_movie_name,
    axis=1
)


# --------------------------------------------------
# 16. 선택한 날짜 표시
# --------------------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")

st.caption(
    "※ 한국 시간 기준으로 선택한 날짜의 데이터입니다. "
    "같은 날짜의 결과는 약 1시간 동안 캐시됩니다."
)


# --------------------------------------------------
# 17. 1위 영화 정보
# --------------------------------------------------

first_movie = df.iloc[0]

first_movie_name = first_movie["movieNmDisplay"]
first_audience = first_movie["audiCnt"]
first_total = first_movie["audiAcc"]
first_screens = first_movie["scrnCnt"]


# --------------------------------------------------
# 18. 1위 영화 표시
# --------------------------------------------------

st.subheader(f"🥇 1위: {first_movie_name}")


# --------------------------------------------------
# 19. 지표 카드 3개
# --------------------------------------------------

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        label="당일 관객수",
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
# 20. 관객수 상위 5편
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# 그래프에 사용할 데이터
chart_data = top5[
    ["movieNmDisplay", "audiCnt"]
].set_index("movieNmDisplay")


st.bar_chart(
    chart_data,
    x_label="영화",
    y_label="관객수"
)


# --------------------------------------------------
# 21. 전체 박스오피스 표 만들기
# --------------------------------------------------

table_df = df[
    [
        "rank",
        "rankInten",
        "movieNmDisplay",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# --------------------------------------------------
# 22. 순위 증감 화살표 붙이기
# --------------------------------------------------

def make_rank_change(rank_inten):
    """
    전날보다 순위가 오른 경우:
    빨간색 위 화살표 ▲

    전날보다 순위가 내려간 경우:
    파란색 아래 화살표 ▼

    변동이 없는 경우:
    -
    """

    if rank_inten > 0:
        return f"🔴 ▲ {rank_inten}"

    elif rank_inten < 0:
        return f"🔵 ▼ {abs(rank_inten)}"

    else:
        return "-"


table_df["순위 변동"] = table_df[
    "rankInten"
].apply(make_rank_change)


# --------------------------------------------------
# 23. 표에서 사용할 열 이름 변경
# --------------------------------------------------

table_df = table_df[
    [
        "rank",
        "movieNmDisplay",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
        "순위 변동"
    ]
]

table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
    "순위 변동"
]


# --------------------------------------------------
# 24. 전체 박스오피스 표 표시
# --------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

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
# 25. 안내
# --------------------------------------------------

st.caption(
    "🔴 ▲ = 전날보다 순위 상승   "
    "🔵 ▼ = 전날보다 순위 하락   "
    "🏆 = 누적관객 100만 명 이상"
)

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) 일일 박스오피스 API"
)

