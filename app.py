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

            # utf-8-sig or utf-8 decoding
            try:
                decoded_data = bytes_data.decode('utf-8-sig')
            except UnicodeDecodeError:
                decoded_data = bytes_data.decode('utf-8')

            stringio = io.StringIO(decoded_data)

            # --- 여기가 수정된 부분: on_bad_lines='skip' 추가 ---
            # 1. 첫 줄 읽어서 헤더 추출
            stringio.seek(0)
            header_line = stringio.readline().strip()
            headers = [h.strip() for h in header_line.split(',')]

            # 2. 나머지 부분을 데이터로 읽되, 열 개수 안 맞는 줄은 건너뛰기
            stringio.seek(0)
            # skiprows=1 로 헤더 줄 건너뛰고, header=None 으로 자동 헤더 감지 방지
            # on_bad_lines='skip' 추가
            df = pd.read_csv(stringio, header=None, skiprows=1, skipinitialspace=True, on_bad_lines='skip')

            # 3. 추출한 헤더 목록 적용 (열 개수가 부족하면 헤더 잘라서 적용)
            if len(headers) >= len(df.columns):
                 df.columns = headers[:len(df.columns)]
            else:
                 # 데이터 열이 헤더보다 많은 경우 경고 후 임시 이름 부여
                 st.warning(f"'{uploaded_file.name}': 데이터 열({len(df.columns)})이 헤더({len(headers)})보다 많습니다. 추가 열은 임시 이름이 부여됩니다.")
                 df.columns = headers + [f'unknown_{i}' for i in range(len(df.columns) - len(headers))]

            # 첫 열 이름이 time인지 확인
            if df.columns[0] != 'time':
                st.error(f"'{uploaded_file.name}': 헤더 처리 후 첫 열이 'time'이 아닙니다 ('{df.columns[0]}'). 파일 구조를 확인해주세요.")
                continue
            # --- 수정 끝 ---

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
