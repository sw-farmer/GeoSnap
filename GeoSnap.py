import streamlit as st
import pandas as pd
import datetime
import folium
from streamlit_folium import st_folium
from folium.plugins import LocateControl
import json
import requests
from PIL import Image
from io import BytesIO
import base64
import streamlit.components.v1 as components

# 페이지 설정 - 모바일 최적화
st.set_page_config(
    page_title="도시재생 현장 데이터 기록",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS로 모바일 최적화
st.markdown("""
    <style>
        .stApp {
            max-width: 100%;
            padding: 0.5rem;
        }
        .st-emotion-cache-1y4p8pa {
            padding: 0;
        }
        .row-widget.stButton > button {
            width: 100%;
            margin: 0;
        }
        .main-content {
            display: flex;
            flex-direction: row;
            gap: 1rem;
        }
        @media (max-width: 768px) {
            .main-content {
                flex-direction: column;
            }
        }
        .data-input {
            flex: 1;
            min-width: 300px;
        }
        .data-display {
            flex: 1;
            min-width: 300px;
        }
        .st-emotion-cache-1788y8l {
            margin-bottom: 0.5rem;
        }
        .streamlit-expanderHeader {
            font-size: 1rem;
        }
        div[data-testid="column"] {
            padding: 0 0.5rem;
        }
    </style>
""", unsafe_allow_html=True)

# 데이터 저장용 세션 상태 초기화
if 'data' not in st.session_state:
    st.session_state.data = []

if 'edit_index' not in st.session_state:
    st.session_state.edit_index = None

if 'location_requested' not in st.session_state:
    st.session_state.location_requested = False

# API 키 설정
if 'kakao_api_key' not in st.session_state:
    st.session_state.kakao_api_key = ""

# 현재 위치 가져오기 함수
def get_current_location():
    js_code = """
    <script>
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                window.parent.postMessage({
                    type: 'location',
                    lat: position.coords.latitude,
                    lon: position.coords.longitude
                }, '*');
            },
            function(error) {
                console.error('Error:', error);
            },
            {
                enableHighAccuracy: true,
                timeout: 5000,
                maximumAge: 0
            }
        );
    }
    </script>
    """
    components.html(js_code, height=0)

# 위치 정보 수신을 위한 JavaScript
def handle_location_message():
    components.html("""
        <script>
        window.addEventListener('message', function(e) {
            if (e.data.type === 'location') {
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    data: {
                        latitude: e.data.lat,
                        longitude: e.data.lon
                    }
                }, '*');
            }
        });
        </script>
    """, height=0)

# Kakao API를 사용한 주소 변환 함수
def get_address_from_coordinates(lat, lon):
    if not st.session_state.kakao_api_key:
        return "API 키가 필요합니다"
    
    url = f"https://dapi.kakao.com/v2/local/geo/coord2address.json?x={lon}&y={lat}"
    headers = {"Authorization": f"KakaoAK {st.session_state.kakao_api_key}"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            result = response.json()
            if result["documents"]:
                address = result["documents"][0]["address"]
                return f"{address['address_name']}"
            return "주소를 찾을 수 없습니다"
    except Exception as e:
        return f"에러: {str(e)}"
    
    return "주소 변환 실패"

# 메인 타이틀
st.title("도시재생 현장 데이터 기록 시스템")

# 패스워드 인증 섹션
with st.sidebar:
    st.title("설정")
    password = st.text_input("비밀번호를 입력하세요", type="password")
    if password == "1":
        st.session_state.kakao_api_key = "161b32ed45c4c6e918f53270d663458b"
        st.success("인증되었습니다.")
        
        # 인증 성공 시 현재 위치 가져오기
        if 'location_initialized' not in st.session_state:
            get_current_location()
            st.session_state.location_initialized = True
    elif password:
        st.error("잘못된 비밀번호입니다.")

# 위치 정보 초기화
if 'latitude' not in st.session_state:
    st.session_state.latitude = 37.5665  # 기본값
if 'longitude' not in st.session_state:
    st.session_state.longitude = 126.9780  # 기본값

# 2단 레이아웃 구성
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("현장 데이터 입력")
    
    # 지도 타입 선택
    map_type = st.selectbox(
        "지도 타입 선택",
        ["일반지도", "위성지도", "하이브리드"]
    )

    # 선택된 지도 타입에 따른 타일 레이어 URL
    tile_dict = {
        "일반지도": "OpenStreetMap",
        "위성지도": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        "하이브리드": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
    }

    # 지도 생성
    m = folium.Map(
        location=[st.session_state.latitude, st.session_state.longitude],
        zoom_start=17,
    )

    # 선택된 지도 타입 적용
    if map_type == "일반지도":
        folium.TileLayer(tile_dict[map_type]).add_to(m)
    else:
        folium.TileLayer(
            tiles=tile_dict[map_type],
            attr='Google Maps',
            name=map_type,
        ).add_to(m)

    # 현재 위치 찾기 컨트롤 추가
    LocateControl(
        auto_start=False,
        position='bottomright',
        strings={'title': '현재 위치 찾기'},
        locateOptions={'enableHighAccuracy': True}
    ).add_to(m)

    # 현재 위치 마커 추가
    folium.Marker(
        [st.session_state.latitude, st.session_state.longitude],
        popup="현재 위치",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

    # 저장된 위치들에 마커 추가
    for idx, record in enumerate(st.session_state.data):
        try:
            coords = record["위치좌표"].split(",")
            folium.Marker(
                [float(coords[0]), float(coords[1])],
                popup=f"기록 {idx+1}",
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)
        except:
            pass

    # 지도 표시
    st_data = st_folium(m, width="100%", height=500)

    # 지도 클릭 위치로 좌표 업데이트
    if st_data['last_clicked']:
        st.session_state.latitude = st_data['last_clicked']['lat']
        st.session_state.longitude = st_data['last_clicked']['lng']

    # 수동으로 위치 새로고침
    if st.button("현재 위치 새로고침"):
        get_current_location()
        st.rerun()

    # 사용자 기록 항목 설정
    if "record_fields" not in st.session_state:
        st.session_state.record_fields = ["건물상태", "용도", "특이사항"]

    # 기록 항목 관리
    with st.expander("기록 항목 설정"):
        record_fields = st.text_input(
            "기록 항목 입력 (쉼표로 구분)",
            value=",".join(st.session_state.record_fields)
        )
        st.session_state.record_fields = [field.strip() for field in record_fields.split(",")]
        st.write("현재 기록 항목:", st.session_state.record_fields)

    # 데이터 입력 폼
    with st.form("data_form", clear_on_submit=True):
        user_id = st.text_input("사용자 ID")
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 위치 좌표 및 주소
        location_str = f"{st.session_state.latitude}, {st.session_state.longitude}"
        address = get_address_from_coordinates(st.session_state.latitude, st.session_state.longitude)
        st.write(f"현재 위치: {location_str}")
        st.write(f"주소: {address}")
        
        # 기록 항목 입력
        record_data = {
            "사용자ID": user_id,
            "시간": current_time,
            "위치좌표": location_str,
            "주소": address,
        }
        
        for field in st.session_state.record_fields:
            record_data[field] = st.text_input(field)
        
        # 카메라 입력
        img_file = st.camera_input("사진 촬영")
        if img_file:
            record_data["사진"] = img_file.getvalue()
            
        # 또는 파일 업로드
        uploaded_file = st.file_uploader("또는 사진 업로드", type=['png', 'jpg', 'jpeg'])
        if uploaded_file:
            record_data["사진"] = uploaded_file.getvalue()
        
        submitted = st.form_submit_button("기록 저장")
        if submitted:
            if user_id:
                if st.session_state.edit_index is not None:
                    st.session_state.data[st.session_state.edit_index] = record_data
                    st.session_state.edit_index = None
                    st.success("데이터가 수정되었습니다.")
                    st.rerun()
                else:
                    st.session_state.data.append(record_data)
                    st.success("데이터가 저장되었습니다.")
                    st.rerun()
            else:
                st.error("사용자 ID를 입력해주세요.")

with col2:
    st.subheader("저장된 데이터")
    
    if st.session_state.data:
        # 데이터프레임 생성 (사진 제외)
        df_display = []
        for record in st.session_state.data:
            record_display = record.copy()
            if "사진" in record_display:
                del record_display["사진"]
            df_display.append(record_display)
        
        df = pd.DataFrame(df_display)
        st.dataframe(df, use_container_width=True, height=300)
        
        # 각 기록 상세 보기
        for idx, record in enumerate(st.session_state.data):
            with st.expander(f"기록 {idx+1} 상세보기"):
                # 기본 정보 표시
                for key, value in record.items():
                    if key != "사진":
                        st.write(f"{key}: {value}")
                
                # 사진 표시
                if "사진" in record and record["사진"]:
                    try:
                        image = Image.open(BytesIO(record["사진"]))
                        st.image(image, caption="현장 사진", use_column_width=True)
                    except Exception as e:
                        st.error(f"사진을 표시할 수 없습니다. 오류: {str(e)}")
                
                # 수정/삭제 버튼
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("수정", key=f"edit_{idx}"):
                        st.session_state.edit_index = idx
                        st.rerun()
                with col2:
                    if st.button("삭제", key=f"del_{idx}"):
                        st.session_state.data.pop(idx)
                        st.rerun()

        # 데이터 내보내기
        st.subheader("데이터 내보내기")
        
        # CSV 다운로드 버튼
        csv = df.to_csv(index=False)
        st.download_button(
            label="CSV 다운로드",
            data=csv,
            file_name=f"urban_research_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

# 위치 정보 수신을 위한 JavaScript
handle_location_message()