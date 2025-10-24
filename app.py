import streamlit as st
import pandas as pd
import io

st.set_page_config(layout="wide")
st.title("🔥 Ikawa Roast Log Analyzer")
st.markdown("**(v.0.1 - Initial Setup)**")

uploaded_files = st.file_uploader(
    "CSV 로그 파일을 여기에 업로드하세요.",
    type="csv",
    accept_multiple_files=True
)

# --- 예상되는 전체 헤더 목록 ---
# (일반 모델과 X 모델에 공통적으로 존재하는 헤더 + X 모델에만 있는 헤더 순서대로)
expected_headers = [
    'time', 'fan set', 'setpoint', 'fan speed', 'temp above', 'state',
    'heater', 'p', 'i', 'd', 'temp below', 'temp board', 'j', 'ror_above',
    'abs_humidity', 'abs_humidity_roc', 'abs_humidity_roc_direction', # X 모델 추가 시작
    'adfc_timestamp', 'end_timestamp', 'tdf_error', 'pressure',
    'total_moisture_loss', 'moisture_loss_rate' # X 모델 추가 끝
]

if uploaded_files:
    if 'log_data' not in st.session_state:
        st.session_state.log_data = {}

    st.subheader("📊 업로드된 로그 데이터 확인")
    st.session_state.log_data.clear()

    for uploaded_file in uploaded_files:
        profile_name = uploaded_file.name.replace('.csv', '')
        
        try:
            bytes_data = uploaded_file.getvalue()
            
            # utf-8-sig 또는 utf-8으로 디코딩
            try:
                decoded_data = bytes_data.decode('utf-8-sig')
            except UnicodeDecodeError:
                decoded_data = bytes_data.decode('utf-8')
                
            stringio = io.StringIO(decoded_data)

            # --- 여기가 수정된 부분: header=0과 names 옵션 사용 ---
            # 먼저 파일에 몇 개의 열이 있는지 확인
            temp_df_for_col_count = pd.read_csv(io.StringIO(decoded_data), nrows=1)
            num_cols = len(temp_df_for_col_count.columns)

            # 파일의 열 개수에 맞는 헤더 목록 생성
            current_headers = expected_headers[:num_cols]

            # header=0 (첫 줄을 헤더로 인식), names로 강제 지정, skiprows=1로 헤더 줄 건너뛰기
            stringio.seek(0) # StringIO 커서를 다시 처음으로 이동
            df = pd.read_csv(stringio, header=0, names=current_headers, skiprows=1)
            # --- 수정 끝 ---

            # 첫 열 이름이 time인지 다시 확인 (검증용)
            if df.columns[0] != 'time':
                 st.warning(f"'{uploaded_file.name}': 첫 열 이름이 'time'이 아닙니다 ('{df.columns[0]}'). 데이터 로딩에 문제가 있을 수 있습니다.")


            st.session_state.log_data[profile_name] = df

            st.write(f"---")
            st.write(f"**파일명:** {uploaded_file.name}")
            st.write(f"**데이터 첫 5줄:**")
            st.dataframe(df.head())
            
            buffer = io.StringIO()
            df.info(buf=buffer)
            s = buffer.getvalue()
            st.text(s)

        except Exception as e:
            st.error(f"'{uploaded_file.name}' 파일을 읽는 중 오류 발생: {e}")
            if profile_name in st.session_state.log_data:
                del st.session_state.log_data[profile_name]

if not uploaded_files and ('log_data' not in st.session_state or not st.session_state.get('log_data')):
     st.info("분석할 CSV 파일을 업로드해주세요.")
