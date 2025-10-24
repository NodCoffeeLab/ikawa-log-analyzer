import streamlit as st
import pandas as pd
import io # 파일 처리(특히 업로드된 파일)를 위해 필요

st.set_page_config(layout="wide")
st.title("🔥 Ikawa Roast Log Analyzer")
st.markdown("**(v.0.1 - Initial Setup)**")

# --- 1. 파일 업로드 ---
uploaded_files = st.file_uploader(
    "CSV 로그 파일을 여기에 업로드하세요.",
    type="csv",
    accept_multiple_files=True # 여러 파일 업로드 허용
)

# --- 2. 데이터 로딩 및 구조 확인 ---
if uploaded_files:
    st.session_state.log_data = {} # 데이터를 저장할 딕셔너리 초기화
    st.subheader("📊 업로드된 로그 데이터 확인")

    for uploaded_file in uploaded_files:
        # 파일명을 프로파일 이름으로 사용
        profile_name = uploaded_file.name.replace('.csv', '') # 확장자 제거
        
        try:
            # 업로드된 파일을 BytesIO로 읽어서 Pandas로 전달
            bytes_data = uploaded_file.getvalue()
            stringio = io.StringIO(bytes_data.decode('utf-8')) # 바이트 -> 문자열 변환
            df = pd.read_csv(stringio)
            
            st.session_state.log_data[profile_name] = df # 세션 상태에 DataFrame 저장

            # 각 파일의 기본 정보 출력 (개발 확인용)
            st.write(f"---")
            st.write(f"**파일명:** {uploaded_file.name}")
            st.write(f"**데이터 첫 5줄:**")
            st.dataframe(df.head())
            
            # .info()는 직접 출력되지 않으므로, 버퍼를 사용해 출력 내용을 가져옴
            buffer = io.StringIO()
            df.info(buf=buffer)
            s = buffer.getvalue()
            st.text(s)

        except Exception as e:
            st.error(f"'{uploaded_file.name}' 파일을 읽는 중 오류 발생: {e}")
else:
    st.info("분석할 CSV 파일을 업로드해주세요.")
