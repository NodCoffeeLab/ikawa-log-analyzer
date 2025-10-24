import streamlit as st
import pandas as pd
import io

st.set_page_config(layout="wide")
st.title("🔥 Ikawa Roast Log Analyzer")
st.markdown("**(v.0.2 - Data Cleaning)**") # 버전 업데이트

uploaded_files = st.file_uploader(
    "CSV 로그 파일을 여기에 업로드하세요.",
    type="csv",
    accept_multiple_files=True
)

# --- 예상되는 전체 헤더 목록 ---
expected_headers = [
    'time', 'fan set', 'setpoint', 'fan speed', 'temp above', 'state',
    'heater', 'p', 'i', 'd', 'temp below', 'temp board', 'j', 'ror_above',
    'abs_humidity', 'abs_humidity_roc', 'abs_humidity_roc_direction',
    'adfc_timestamp', 'end_timestamp', 'tdf_error', 'pressure',
    'total_moisture_loss', 'moisture_loss_rate'
]

# --- 핵심 데이터 열 이름 ---
# 사용자와 확인 후 확정 필요
TIME_COL = 'time'
EXHAUST_TEMP_COL = 'temp above'
INLET_TEMP_COL = 'temp below'
EXHAUST_ROR_COL = 'ror_above'
FAN_SPEED_COL = 'fan speed'
HUMIDITY_COL = 'abs_humidity'          # X 모델 전용
HUMIDITY_ROC_COL = 'abs_humidity_roc' # X 모델 전용
STATE_COL = 'state'

if uploaded_files:
    if 'log_data' not in st.session_state:
        st.session_state.log_data = {}
    if 'cleaned_data' not in st.session_state: # 정제된 데이터를 저장할 곳
        st.session_state.cleaned_data = {}

    st.subheader("🛠️ 데이터 정제 결과 확인")
    st.session_state.log_data.clear()
    st.session_state.cleaned_data.clear() # 새로 업로드 시 정제 데이터도 초기화

    all_files_valid = True
    for uploaded_file in uploaded_files:
        profile_name = uploaded_file.name.replace('.csv', '')
        
        try:
            bytes_data = uploaded_file.getvalue()
            try: decoded_data = bytes_data.decode('utf-8-sig')
            except UnicodeDecodeError: decoded_data = bytes_data.decode('utf-8')
            stringio = io.StringIO(decoded_data)

            # 1. 헤더 추출
            stringio.seek(0); header_line = stringio.readline().strip()
            headers = [h.strip() for h in header_line.split(',')]

            # 2. 데이터 읽기
            stringio.seek(0)
            df = pd.read_csv(stringio, header=None, skiprows=1, skipinitialspace=True)
            
            # 3. 헤더 적용
            if len(headers) >= len(df.columns): df.columns = headers[:len(df.columns)]
            else: raise ValueError("데이터 열 개수가 헤더 개수보다 많습니다.")
            
            # --- 여기가 추가/수정된 부분: 데이터 정제 ---
            
            # 4. 로스팅 구간 필터링 ('ROASTING' 상태만 선택)
            if STATE_COL in df.columns:
                roasting_df = df[df[STATE_COL] == 'ROASTING'].copy()
                if roasting_df.empty:
                    st.warning(f"'{uploaded_file.name}': 'ROASTING' 상태 데이터를 찾을 수 없습니다. 'state' 열을 확인해주세요.")
                    # READY_FOR_ROAST 부터 포함할지 등 예외처리 필요 시 추가
                    roasting_df = df # 임시로 전체 데이터 사용
            else:
                st.warning(f"'{uploaded_file.name}': 'state' 열을 찾을 수 없습니다. 전체 데이터를 사용합니다.")
                roasting_df = df.copy()

            # 5. 시간 초기화 (첫 로스팅 시간 기준으로 0초 시작)
            if TIME_COL in roasting_df.columns and not roasting_df.empty:
                start_time = roasting_df[TIME_COL].iloc[0]
                roasting_df[TIME_COL] = roasting_df[TIME_COL] - start_time
            
            # 6. 숫자형 변환 시도 (오류 발생 시 NaN 처리)
            cols_to_convert = [EXHAUST_TEMP_COL, INLET_TEMP_COL, EXHAUST_ROR_COL, FAN_SPEED_COL]
            if HUMIDITY_COL in roasting_df.columns: cols_to_convert.append(HUMIDITY_COL)
            if HUMIDITY_ROC_COL in roasting_df.columns: cols_to_convert.append(HUMIDITY_ROC_COL)
                
            for col in cols_to_convert:
                if col in roasting_df.columns:
                    roasting_df[col] = pd.to_numeric(roasting_df[col], errors='coerce')

            # --- 정제 끝 ---

            st.session_state.log_data[profile_name] = df # 원본 데이터 (참고용)
            st.session_state.cleaned_data[profile_name] = roasting_df # 정제된 데이터

            # 정제된 데이터 정보 출력
            st.write(f"---")
            st.write(f"**파일명:** {uploaded_file.name} (정제 후)")
            st.write(f"**데이터 첫 5줄:**")
            st.dataframe(roasting_df.head())
            
            buffer = io.StringIO()
            roasting_df.info(buf=buffer)
            s = buffer.getvalue()
            st.text(s)

        except Exception as e:
            st.error(f"'{uploaded_file.name}' 파일을 처리하는 중 오류 발생: {e}")
            all_files_valid = False
            # 오류 발생 시 해당 프로파일 데이터 제거
            if profile_name in st.session_state.log_data: del st.session_state.log_data[profile_name]
            if profile_name in st.session_state.cleaned_data: del st.session_state.cleaned_data[profile_name]

# 데이터가 성공적으로 처리되었을 경우 다음 단계 안내 (예시)
if uploaded_files and all_files_valid and st.session_state.cleaned_data:
     st.success("모든 파일 처리 완료! 이제 그래프를 그릴 준비가 되었습니다.")
elif not uploaded_files and ('log_data' not in st.session_state or not st.session_state.get('log_data')):
     st.info("분석할 CSV 파일을 업로드해주세요.")
