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
    # --- 여기가 수정된 부분: session_state 초기화 위치 변경 ---
    if 'log_data' not in st.session_state:
        st.session_state.log_data = {}

    st.subheader("📊 업로드된 로그 데이터 확인")

    # 기존 데이터를 지우고 새로 업로드된 파일만 처리
    st.session_state.log_data.clear() 

    for uploaded_file in uploaded_files:
        profile_name = uploaded_file.name.replace('.csv', '')
        
        try:
            bytes_data = uploaded_file.getvalue()
            stringio = io.StringIO(bytes_data.decode('utf-8'))
            
            # --- 여기가 수정된 부분: index_col=0 추가 ---
            df = pd.read_csv(stringio, index_col=0) 
            
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
            # 오류 발생 시 해당 프로파일 데이터 제거
            if profile_name in st.session_state.log_data:
                del st.session_state.log_data[profile_name]

# --- session_state에 데이터가 없을 경우 안내 메시지 표시 ---
if not uploaded_files and 'log_data' not in st.session_state or not st.session_state.get('log_data'):
     st.info("분석할 CSV 파일을 업로드해주세요.")
