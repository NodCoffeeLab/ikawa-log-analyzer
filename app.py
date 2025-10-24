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
            
            # --- 여기가 수정된 부분: 인코딩 처리 및 기본 read_csv ---
            # utf-8-sig를 먼저 시도 (BOM 처리), 실패 시 utf-8 사용
            try:
                decoded_data = bytes_data.decode('utf-8-sig')
            except UnicodeDecodeError:
                decoded_data = bytes_data.decode('utf-8')
                
            stringio = io.StringIO(decoded_data)
            
            # index_col 옵션 없이 기본값으로 읽기
            df = pd.read_csv(stringio)
            # --- 수정 끝 ---

            # 읽은 후 첫 열 이름 확인 (디버깅용 - 문제가 계속되면 이 정보가 필요합니다)
            first_col_name = df.columns[0]
            if first_col_name.startswith('Unnamed:'):
                 st.warning(f"'{uploaded_file.name}' 파일에서 첫 열 이름이 '{first_col_name}'으로 인식되었습니다. 데이터 정렬을 확인해주세요.")

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

if not uploaded_files and 'log_data' not in st.session_state or not st.session_state.get('log_data'):
     st.info("분석할 CSV 파일을 업로드해주세요.")
