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

            # --- 여기가 수정된 부분: 헤더와 데이터 분리 읽기 ---
            # 1. 첫 줄만 읽어서 헤더 추출
            stringio.seek(0) # 커서 처음으로
            header_line = stringio.readline().strip()
            headers = [h.strip() for h in header_line.split(',')] # 콤마로 분리하고 공백 제거

            # 2. 나머지 부분을 데이터로 읽기 (header=None 사용)
            stringio.seek(0) # 커서 다시 처음으로
            # skiprows=1 로 헤더 줄 건너뛰고, header=None 으로 자동 헤더 감지 방지
            df = pd.read_csv(stringio, header=None, skiprows=1, skipinitialspace=True)
            
            # 3. 추출한 헤더 목록 적용 (열 개수가 부족하면 헤더 잘라서 적용)
            if len(headers) >= len(df.columns):
                 df.columns = headers[:len(df.columns)]
            else:
                 # 데이터 열이 헤더보다 많으면 경고 (드문 경우)
                 st.warning(f"'{uploaded_file.name}': 데이터 열 개수({len(df.columns)})가 헤더 개수({len(headers)})보다 많습니다.")
                 df.columns = headers + [f'unknown_{i}' for i in range(len(df.columns) - len(headers))]

            # 첫 열 이름이 time인지 확인
            if df.columns[0] != 'time':
                st.error(f"'{uploaded_file.name}': 헤더 처리 후에도 첫 열이 'time'이 아닙니다. 파일 구조를 확인해주세요.")
                continue # 이 파일은 처리 중단
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
