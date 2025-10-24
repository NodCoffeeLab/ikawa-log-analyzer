import streamlit as st
import pandas as pd
import io

st.set_page_config(layout="wide")
st.title("🔥 Ikawa Roast Log Analyzer")
st.markdown("**(v.0.1 - Initial Setup)**")

uploaded_files = st.file_uploader(
    "CSV 로그 파일을 여기에 업로드하세요.aaa",
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
            
            # utf-8-sig 또는 utf-8으로 디코딩
            try:
                decoded_data = bytes_data.decode('utf-8-sig')
            except UnicodeDecodeError:
                decoded_data = bytes_data.decode('utf-8')
                
            stringio = io.StringIO(decoded_data)

            # --- 여기가 수정된 부분: 헤더 확인 후 재처리 ---
            # 1. 일단 기본으로 읽어본다
            df = pd.read_csv(stringio)
            
            # 2. 첫 열 이름이 'time'이 아닌지 확인 (헤더가 밀렸는지 검사)
            if df.columns[0] != 'time':
                st.warning(f"'{uploaded_file.name}' 파일 헤더 자동 감지 실패. 수동으로 재지정합니다.")
                # 3. 헤더 없이 다시 읽고, 올바른 헤더 목록 수동 지정
                stringio.seek(0) # 커서 처음으로
                df = pd.read_csv(stringio, header=None, skiprows=1) # 헤더 없이 읽고, 실제 헤더 줄은 건너뜀
                
                # 파일의 실제 열 개수에 맞춰 헤더 목록 준비
                num_cols = len(df.columns)
                current_headers = expected_headers[:num_cols]
                df.columns = current_headers # 헤더 수동 지정
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
