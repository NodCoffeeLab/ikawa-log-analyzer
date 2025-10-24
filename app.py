import streamlit as st
import pandas as pd
import numpy as np
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# --- 백엔드 함수 (변경 없음) ---
def calculate_ror(df):
    if df['온도'].isnull().all(): return df # Assuming '온도' is the relevant column, adjust if needed
    last_valid_index = df['온도'].last_valid_index()
    if last_valid_index is None: return df
    calc_df = df.loc[0:last_valid_index].copy()
    delta_temp = calc_df['온도'].diff(); delta_time = calc_df['누적 시간 (초)'].diff()
    ror = (delta_temp / delta_time).replace([np.inf, -np.inf], 0).fillna(0)
    calc_df['ROR (℃/sec)'] = ror; df.update(calc_df)
    return df


# --- UI 및 앱 실행 로직 ---
st.set_page_config(layout="wide")
st.title("🔥 Ikawa Roast Log Analyzer")
st.markdown("**(v.0.3 - Adjustments)**") # 버전 업데이트

# --- Session State 초기화 (기본 축 범위 수정) ---
if 'processed_logs' not in st.session_state: st.session_state.processed_logs = {}
if 'selected_time' not in st.session_state: st.session_state.selected_time = 0
if 'axis_ranges' not in st.session_state:
    st.session_state.axis_ranges = {'x': [0, 600], 'y': [60, 300], 'y2': [0, 50]} # 기본 범위 수정

# --- 예상되는 전체 헤더 목록 ---
expected_headers = [
    'time', 'fan set', 'setpoint', 'fan speed', 'temp above', 'state',
    'heater', 'p', 'i', 'd', 'temp below', 'temp board', 'j', 'ror_above',
    'abs_humidity', 'abs_humidity_roc', 'abs_humidity_roc_direction',
    'adfc_timestamp', 'end_timestamp', 'tdf_error', 'pressure',
    'total_moisture_loss', 'moisture_loss_rate'
]
# --- 핵심 데이터 열 이름 ---
TIME_COL = 'time'
EXHAUST_TEMP_COL = 'temp above'
INLET_TEMP_COL = 'temp below'
EXHAUST_ROR_COL = 'ror_above'
STATE_COL = 'state'

# --- 사이드바 UI (기본값 수정) ---
with st.sidebar:
    st.header("⚙️ 보기 옵션")
    profile_names_sidebar = list(st.session_state.processed_logs.keys())
    default_selected = st.session_state.get('selected_profiles', profile_names_sidebar)
    default_selected = [p for p in default_selected if p in profile_names_sidebar]
    if not default_selected and profile_names_sidebar:
        default_selected = profile_names_sidebar
    st.session_state.selected_profiles = st.multiselect("그래프에 표시할 로그 선택", options=profile_names_sidebar, default=default_selected)

    st.subheader("축 범위 조절")
    axis_ranges = st.session_state.axis_ranges
    col1, col2 = st.columns(2)
    with col1:
        # value 수정
        x_min = st.number_input("X축 최소값(시간)", value=axis_ranges['x'][0])
        y_min = st.number_input("Y축(온도) 최소값", value=axis_ranges['y'][0])
        y2_min = st.number_input("보조Y축(ROR) 최소값", value=axis_ranges['y2'][0], format="%.1f") # ROR 포맷 변경 고려
    with col2:
        # value 수정
        x_max = st.number_input("X축 최대값(시간)", value=axis_ranges['x'][1])
        y_max = st.number_input("Y축(온도) 최대값", value=axis_ranges['y'][1])
        y2_max = st.number_input("보조Y축(ROR) 최대값", value=axis_ranges['y2'][1], format="%.1f") # ROR 포맷 변경 고려
    st.session_state.axis_ranges = {'x': [x_min, x_max], 'y': [y_min, y_max], 'y2': [y2_min, y2_max]}

# --- 파일 업로드 UI ---
uploaded_files = st.file_uploader("CSV 로그 파일을 여기에 업로드하세요.", type="csv", accept_multiple_files=True)

# --- 데이터 로딩 및 정제 ---
if uploaded_files:
    if 'files_processed' not in st.session_state or st.session_state.uploaded_file_names != [f.name for f in uploaded_files]:
        st.session_state.processed_logs.clear()
        st.session_state.selected_profiles = []
        st.write("---")
        st.subheader("⏳ 파일 처리 중...")

        all_files_valid = True
        log_dfs_for_processing = {}

        for uploaded_file in uploaded_files:
            profile_name = uploaded_file.name.replace('.csv', '')
            try:
                bytes_data = uploaded_file.getvalue()
                try: decoded_data = bytes_data.decode('utf-8-sig')
                except UnicodeDecodeError: decoded_data = bytes_data.decode('utf-8')
                stringio = io.StringIO(decoded_data)
                stringio.seek(0); header_line = stringio.readline().strip()
                headers = [h.strip() for h in header_line.split(',')]
                stringio.seek(0)
                # 데이터 읽을 때 에러 라인 무시하도록 수정
                df = pd.read_csv(stringio, header=None, skiprows=1, skipinitialspace=True, on_bad_lines='warn') # 'skip' 대신 'warn' 사용 고려
                if len(headers) >= len(df.columns): df.columns = headers[:len(df.columns)]
                else: df.columns = headers + [f'unknown_{i}' for i in range(len(df.columns) - len(headers))]
                if df.columns[0] != 'time': raise ValueError("첫 열이 'time'이 아닙니다.")

                # --- 여기가 수정된 부분: 상태 필터링 강화 + 쿨링 제외 ---
                roasting_df = pd.DataFrame()
                if STATE_COL in df.columns:
                    df[STATE_COL] = df[STATE_COL].astype(str).str.strip().str.lower()
                    # 로스팅 시작 지점 찾기
                    start_mask = df[STATE_COL].str.contains('roasting|ready_for_roast', case=False, na=False)
                    # 로스팅 종료 지점 찾기 (cooling, cooldown 시작 전까지)
                    end_mask = df[STATE_COL].str.contains('cooling|cooldown', case=False, na=False)

                    start_index = -1
                    if start_mask.any():
                        start_index = df[start_mask].index[0]

                    end_index = len(df) # 기본값은 끝까지
                    if end_mask.any():
                        end_index = df[end_mask].index[0]

                    if start_index != -1:
                        roasting_df = df.iloc[start_index:end_index].copy()
                    else:
                        st.warning(f"'{uploaded_file.name}': 로스팅 시작 상태를 찾을 수 없어 전체 데이터를 사용합니다 (쿨링 제외 시도).")
                        # 쿨링 상태만 제외하고 사용
                        cooling_mask = df[STATE_COL].str.contains('cooling|cooldown', case=False, na=False)
                        roasting_df = df[~cooling_mask].copy() # 쿨링 아닌 것만 선택
                else:
                     st.warning(f"'{uploaded_file.name}': 'state' 열이 없어 전체 데이터를 사용합니다.")
                     roasting_df = df.copy()
                # --- 수정 끝 ---


                if TIME_COL in roasting_df.columns and not roasting_df.empty:
                    start_time = roasting_df[TIME_COL].iloc[0]
                    roasting_df[TIME_COL] = roasting_df[TIME_COL] - start_time

                cols_to_convert = [EXHAUST_TEMP_COL, INLET_TEMP_COL, EXHAUST_ROR_COL]
                for col in cols_to_convert:
                    if col in roasting_df.columns:
                        roasting_df[col] = pd.to_numeric(roasting_df[col], errors='coerce')
                    else:
                        st.warning(f"'{uploaded_file.name}': 필수 열 '{col}'이 없습니다.")
                        roasting_df[col] = np.nan

                log_dfs_for_processing[profile_name] = roasting_df

            except Exception as e:
                st.error(f"'{uploaded_file.name}' 파일을 처리하는 중 오류 발생: {e}")
                all_files_valid = False

        if all_files_valid and log_dfs_for_processing:
            st.session_state.processed_logs = log_dfs_for_processing
            st.session_state.selected_profiles = list(log_dfs_for_processing.keys())
            st.session_state.uploaded_file_names = [f.name for f in uploaded_files]
            st.session_state.files_processed = True
            st.success("✅ 파일 처리 완료!")
            # st.rerun() # 제거됨

# --- 그래프 및 분석 패널 UI ---
if st.session_state.processed_logs:
    st.header("📈 그래프 및 분석")
    graph_col, analysis_col = st.columns([0.7, 0.3])
    max_time = 0
    for df in st.session_state.processed_logs.values():
        if TIME_COL in df.columns and not df[TIME_COL].dropna().empty:
            max_time = max(max_time, df[TIME_COL].max())
    max_time = max(max_time, 1)

    with graph_col:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        selected_profiles_data = st.session_state.get('selected_profiles', [])
        colors = px.colors.qualitative.Plotly
        color_map = {name: colors[i % len(colors)] for i, name in enumerate(st.session_state.processed_logs.keys())}

        for name in selected_profiles_data:
            df = st.session_state.processed_logs.get(name); color = color_map.get(name)
            if df is not None and color is not None:
                if TIME_COL in df.columns and EXHAUST_TEMP_COL in df.columns:
                    valid_df_exhaust = df.dropna(subset=[TIME_COL, EXHAUST_TEMP_COL])
                    if len(valid_df_exhaust) > 1:
                        # 이름 변경
                        fig.add_trace(go.Scatter(x=valid_df_exhaust[TIME_COL], y=valid_df_exhaust[EXHAUST_TEMP_COL], mode='lines', name=f'{name} Exhaust Temp', line=dict(color=color, dash='solid'), legendgroup=name), secondary_y=False)
                if TIME_COL in df.columns and INLET_TEMP_COL in df.columns:
                     valid_df_inlet = df.dropna(subset=[TIME_COL, INLET_TEMP_COL])
                     if len(valid_df_inlet) > 1:
                         # 이름 변경
                         fig.add_trace(go.Scatter(x=valid_df_inlet[TIME_COL], y=valid_df_inlet[INLET_TEMP_COL], mode='lines', name=f'{name} Inlet Temp', line=dict(color=color, dash='dash'), legendgroup=name), secondary_y=False)
                if TIME_COL in df.columns and EXHAUST_ROR_COL in df.columns:
                    valid_df_ror = df.dropna(subset=[TIME_COL, EXHAUST_ROR_COL])
                    # Ensure at least 2 points for ROR plotting after removing the first one
                    if len(valid_df_ror) > 1:
                        ror_df = valid_df_ror.iloc[1:]
                        # Check again if ror_df is not empty after slicing
                        if not ror_df.empty:
                            fig.add_trace(go.Scatter(x=ror_df[TIME_COL], y=ror_df[EXHAUST_ROR_COL], mode='lines', name=f'{name} ROR', line=dict(color=color, dash='dot'), legendgroup=name, showlegend=False), secondary_y=True)


        selected_time_int = int(st.session_state.get('selected_time', 0)); fig.add_vline(x=selected_time_int, line_width=1, line_dash="dash", line_color="grey")
        axis_ranges = st.session_state.axis_ranges
        fig.update_layout(height=700, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        fig.update_xaxes(range=axis_ranges['x'], title_text='시간 (초)', dtick=60)
        # 축 범위 수정 반영
        fig.update_yaxes(title_text="온도 (°C)", range=axis_ranges['y'], dtick=10, secondary_y=False)
        fig.update_yaxes(title_text="ROR (℃/sec)", range=axis_ranges['y2'], showgrid=False, secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

    with analysis_col:
        st.subheader("🔍 분석 정보"); st.markdown("---")
        st.write("**총 로스팅 시간**")
        for name in selected_profiles_data:
            df = st.session_state.processed_logs.get(name)
            if df is not None and TIME_COL in df.columns:
                valid_df = df.dropna(subset=[TIME_COL])
                if not valid_df.empty:
                    total_time = valid_df[TIME_COL].max(); time_str = f"{int(total_time // 60)}분 {int(total_time % 60)}초"
                    st.markdown(f"**{name}**: <span style='font-size: 1.1em;'>{time_str}</span>", unsafe_allow_html=True)
        st.markdown("---")
        def update_slider_time():
            st.session_state.selected_time = st.session_state.time_slider
        selected_time_val = st.session_state.get('selected_time', 0)
        slider_max_time = max(1, int(max_time))
        if selected_time_val > slider_max_time:
            selected_time_val = slider_max_time
            st.session_state.selected_time = selected_time_val
        st.slider("시간 선택 (초)", 0, slider_max_time, selected_time_val, 1, key="time_slider", on_change=update_slider_time)

        st.write(""); st.write("**선택된 시간 상세 정보**")
        selected_time = st.session_state.selected_time; st.markdown(f"#### {int(selected_time // 60)}분 {int(selected_time % 60):02d}초 ({selected_time}초)")
        for name in selected_profiles_data:
            st.markdown(f"<p style='margin-bottom: 0.2em;'><strong>{name}</strong></p>", unsafe_allow_html=True)
            exhaust_temp_str, inlet_temp_str, ror_str = "--", "--", "--"
            df = st.session_state.processed_logs.get(name)
            if df is not None:
                if TIME_COL not in df.columns: continue
                # 이름 변경 반영
                if EXHAUST_TEMP_COL in df.columns:
                    valid_exhaust = df.dropna(subset=[TIME_COL, EXHAUST_TEMP_COL])
                    if len(valid_exhaust) > 1 and selected_time <= valid_exhaust[TIME_COL].max():
                        hover_exhaust = np.interp(selected_time, valid_exhaust[TIME_COL], valid_exhaust[EXHAUST_TEMP_COL]); exhaust_temp_str = f"{hover_exhaust:.1f}℃"
                if INLET_TEMP_COL in df.columns:
                    valid_inlet = df.dropna(subset=[TIME_COL, INLET_TEMP_COL])
                    if len(valid_inlet) > 1 and selected_time <= valid_inlet[TIME_COL].max():
                        hover_inlet = np.interp(selected_time, valid_inlet[TIME_COL], valid_inlet[INLET_TEMP_COL]); inlet_temp_str = f"{hover_inlet:.1f}℃"
                if EXHAUST_ROR_COL in df.columns:
                    valid_ror = df.dropna(subset=[TIME_COL, EXHAUST_ROR_COL])
                    if len(valid_ror) > 1 and selected_time <= valid_ror[TIME_COL].max():
                        hover_ror = np.interp(selected_time, valid_ror[TIME_COL], valid_ror[EXHAUST_ROR_COL]); ror_str = f"{hover_ror:.3f}℃/sec"
            # 이름 변경 반영
            st.markdown(f"<p style='margin:0; font-size: 0.95em;'>&nbsp;&nbsp;• Exhaust Temp: {exhaust_temp_str}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin:0; font-size: 0.95em;'>&nbsp;&nbsp;• Inlet Temp: {inlet_temp_str}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin-bottom:0.8em; font-size: 0.95em;'>&nbsp;&nbsp;• Exhaust ROR: {ror_str}</p>", unsafe_allow_html=True)

elif not uploaded_files:
    st.info("분석할 CSV 파일을 업로드해주세요.")
