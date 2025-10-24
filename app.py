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

            # --- 여기가 수정된 부분: 파일 내용 직접 출력 ---
            st.write(f"---")
            st.write(f"**파일명:** {uploaded_file.name}")
            st.write("**파일 내용 앞부분 (텍스트):**")
            # StringIO로 변환 후 첫 5줄 읽기
            stringio_for_preview = io.StringIO(decoded_data)
            preview_lines = [stringio_for_preview.readline().strip() for _ in range(5)]
            st.code('\n'.join(preview_lines), language='csv')
            # --- 수정 끝 ---

            # StringIO 커서를 다시 처음으로 이동하여 pandas에서 사용
            stringio = io.StringIO(decoded_data)
            # 가장 기본적인 읽기 시도 (pandas 자동 감지)
            df = pd.read_csv(stringio, skipinitialspace=True)

            st.session_state.log_data[profile_name] = df

            st.write(f"**Pandas 데이터 첫 5줄:**")
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
