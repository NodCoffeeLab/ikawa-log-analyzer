import streamlit as st
import pandas as pd
import numpy as np
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# --- 백엔드 함수 ---
# (create_new_profile, create_new_fan_profile 등 이전 앱 함수는 삭제)

# --- UI 및 앱 실행 로직 ---
st.set_page_config(layout="wide")
st.title("🔥 Ikawa Roast Log Analyzer")
st.markdown("**(v.0.2 - Graphing)**") # 버전 업데이트

# --- Session State 초기화 ---
if 'processed_logs' not in st.session_state: st.session_state.processed_logs = {}
if 'selected_time' not in st.session_state: st.session_state.selected_time = 0
if 'axis_ranges' not in st.session_state:
    st.session_state.axis_ranges = {'x': [0, 600], 'y': [0, 250], 'y2': [-0.5, 1.5]} # 로그 데이터에 맞는 기본 범위

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
# (향후 추가될 열: FAN_SPEED_COL, HUMIDITY_COL, HUMIDITY_ROC_COL)

# --- 사이드바 UI ---
with st.sidebar:
    st.header("⚙️ 보기 옵션")
    # processed_logs가 채워진 후에 프로파일 목록 생성
    profile_names_sidebar = list(st.session_state.processed_logs.keys())
    # 처음 로드 시 또는 사용자가 선택한 값이 없을 경우 모든 프로파일 선택
    default_selected = st.session_state.get('selected_profiles', profile_names_sidebar)
    # 현재 로그 목록에 없는 프로파일은 제거 (파일 재업로드 시 동기화)
    default_selected = [p for p in default_selected if p in profile_names_sidebar]
    if not default_selected and profile_names_sidebar: # 만약 선택된 것이 없다면 다시 전체 선택
        default_selected = profile_names_sidebar

    st.session_state.selected_profiles = st.multiselect(
        "그래프에 표시할 로그 선택",
        options=profile_names_sidebar,
        default=default_selected
    )
    
    st.subheader("축 범위 조절")
    axis_ranges = st.session_state.axis_ranges # 현재 범위 불러오기
    col1, col2 = st.columns(2)
    with col1:
        x_min = st.number_input("X축 최소값(시간)", value=axis_ranges['x'][0])
        y_min = st.number_input("Y축(온도) 최소값", value=axis_ranges['y'][0])
        y2_min = st.number_input("보조Y축(ROR) 최소값", value=axis_ranges['y2'][0], format="%.2f")
    with col2:
        x_max = st.number_input("X축 최대값(시간)", value=axis_ranges['x'][1])
        y_max = st.number_input("Y축(온도) 최대값", value=axis_ranges['y'][1])
        y2_max = st.number_input("보조Y축(ROR) 최대값", value=axis_ranges['y2'][1], format="%.2f")
    st.session_state.axis_ranges = {'x': [x_min, x_max], 'y': [y_min, y_max], 'y2': [y2_min, y2_max]}

# --- 파일 업로드 UI ---
uploaded_files = st.file_uploader(
    "CSV 로그 파일을 여기에 업로드하세요.",
    type="csv",
    accept_multiple_files=True
)

# --- 데이터 로딩 및 정제 ---
if uploaded_files:
    st.session_state.processed_logs.clear() # 새 파일 업로드 시 기존 데이터 초기화
    st.session_state.selected_profiles = [] # 선택 목록도 초기화
    st.write("---")
    st.subheader("⏳ 파일 처리 중...")
    
    all_files_valid = True
    log_dfs_for_processing = {} # 임시 저장소

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

            # 2. 데이터 읽기 (오류 라인 무시)
            stringio.seek(0)
            df = pd.read_csv(stringio, header=None, skiprows=1, skipinitialspace=True, on_bad_lines='skip')
            
            # 3. 헤더 적용
            if len(headers) >= len(df.columns): df.columns = headers[:len(df.columns)]
            else: df.columns = headers + [f'unknown_{i}' for i in range(len(df.columns) - len(headers))]
            if df.columns[0] != 'time': raise ValueError("첫 열이 'time'이 아닙니다.")

            # 4. 로스팅 구간 필터링
            if STATE_COL in df.columns:
                roasting_df = df[df[STATE_COL] == 'ROASTING'].copy()
                if roasting_df.empty:
                    # READY_FOR_ROAST 부터 시작하는 경우 처리 (def 파일 등)
                    if not df[df[STATE_COL] == 'READY_FOR_ROAST'].empty:
                         start_index = df[df[STATE_COL] == 'READY_FOR_ROAST'].index[0]
                         roasting_df = df.iloc[start_index:].copy()
                    else:
                        st.warning(f"'{uploaded_file.name}': 'ROASTING' 상태 데이터를 찾을 수 없어 전체 데이터를 사용합니다.")
                        roasting_df = df.copy()
            else: roasting_df = df.copy()

            # 5. 시간 초기화
            if TIME_COL in roasting_df.columns and not roasting_df.empty:
                start_time = roasting_df[TIME_COL].iloc[0]
                roasting_df[TIME_COL] = roasting_df[TIME_COL] - start_time
            
            # 6. 숫자형 변환
            cols_to_convert = [EXHAUST_TEMP_COL, INLET_TEMP_COL, EXHAUST_ROR_COL] # 필수 열
            # (향후 추가될 열들 확인 후 추가)
            for col in cols_to_convert:
                if col in roasting_df.columns:
                    roasting_df[col] = pd.to_numeric(roasting_df[col], errors='coerce')
                else:
                    st.warning(f"'{uploaded_file.name}': 필수 열 '{col}'이 없습니다.")
                    roasting_df[col] = np.nan # 없는 열은 빈 값으로 추가

            log_dfs_for_processing[profile_name] = roasting_df

        except Exception as e:
            st.error(f"'{uploaded_file.name}' 파일을 처리하는 중 오류 발생: {e}")
            all_files_valid = False

    if all_files_valid and log_dfs_for_processing:
        st.session_state.processed_logs = log_dfs_for_processing
        # 데이터가 있는 프로파일만 selected_profiles의 기본값으로 설정
        st.session_state.selected_profiles = list(log_dfs_for_processing.keys())
        st.success("✅ 파일 처리 완료!")
        st.rerun() # 사이드바 업데이트 및 그래프 표시를 위해 재실행

# --- 그래프 및 분석 패널 UI ---
if st.session_state.processed_logs:
    st.header("📈 그래프 및 분석")
    graph_col, analysis_col = st.columns([0.7, 0.3])
    
    # 처리된 로그 중 최대 시간 계산
    max_time = 0
    for df in st.session_state.processed_logs.values():
        if TIME_COL in df.columns and not df[TIME_COL].dropna().empty:
            max_time = max(max_time, df[TIME_COL].max())
    max_time = max(max_time, 1) # 최소 1초 확보

    with graph_col:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        selected_profiles_data = st.session_state.get('selected_profiles', [])
        colors = px.colors.qualitative.Plotly
        color_map = {name: colors[i % len(colors)] for i, name in enumerate(st.session_state.processed_logs.keys())}
        
        for name in selected_profiles_data:
            df = st.session_state.processed_logs.get(name); color = color_map.get(name)
            if df is not None and color is not None:
                # 데이터 유효성 검사 (시간과 온도 데이터가 있는지)
                if TIME_COL in df.columns and EXHAUST_TEMP_COL in df.columns:
                    valid_df_exhaust = df.dropna(subset=[TIME_COL, EXHAUST_TEMP_COL])
                    if len(valid_df_exhaust) > 1:
                        fig.add_trace(go.Scatter(x=valid_df_exhaust[TIME_COL], y=valid_df_exhaust[EXHAUST_TEMP_COL], mode='lines', name=f'{name} 배기', line=dict(color=color, dash='solid'), legendgroup=name), secondary_y=False)
                
                if TIME_COL in df.columns and INLET_TEMP_COL in df.columns:
                     valid_df_inlet = df.dropna(subset=[TIME_COL, INLET_TEMP_COL])
                     if len(valid_df_inlet) > 1:
                         fig.add_trace(go.Scatter(x=valid_df_inlet[TIME_COL], y=valid_df_inlet[INLET_TEMP_COL], mode='lines', name=f'{name} 투입', line=dict(color=color, dash='dash'), legendgroup=name), secondary_y=False)
                
                if TIME_COL in df.columns and EXHAUST_ROR_COL in df.columns:
                    valid_df_ror = df.dropna(subset=[TIME_COL, EXHAUST_ROR_COL])
                    if len(valid_df_ror) > 1:
                        ror_df = valid_df_ror.iloc[1:] # 0초 제외
                        fig.add_trace(go.Scatter(x=ror_df[TIME_COL], y=ror_df[EXHAUST_ROR_COL], mode='lines', name=f'{name} ROR', line=dict(color=color, dash='dot'), legendgroup=name, showlegend=False), secondary_y=True)

        selected_time_int = int(st.session_state.get('selected_time', 0)); fig.add_vline(x=selected_time_int, line_width=1, line_dash="dash", line_color="grey")
        axis_ranges = st.session_state.axis_ranges
        fig.update_layout(height=700, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)) # 높이 조정
        fig.update_xaxes(range=axis_ranges['x'], title_text='시간 (초)', dtick=60)
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
        # 슬라이더 최대값을 실제 데이터 최대값으로 설정
        st.slider("시간 선택 (초)", 0, int(max_time), selected_time_val, 1, key="time_slider", on_change=update_slider_time)
        
        st.write(""); st.write("**선택된 시간 상세 정보**")
        selected_time = st.session_state.selected_time; st.markdown(f"#### {int(selected_time // 60)}분 {int(selected_time % 60):02d}초 ({selected_time}초)")
        
        for name in selected_profiles_data:
            st.markdown(f"<p style='margin-bottom: 0.2em;'><strong>{name}</strong></p>", unsafe_allow_html=True)
            exhaust_temp_str, inlet_temp_str, ror_str = "--", "--", "--"
            df = st.session_state.processed_logs.get(name)
            if df is not None:
                # 시간 열이 있는지 확인
                if TIME_COL not in df.columns: continue
                
                # 배기 온도 보간
                if EXHAUST_TEMP_COL in df.columns:
                    valid_exhaust = df.dropna(subset=[TIME_COL, EXHAUST_TEMP_COL])
                    if len(valid_exhaust) > 1 and selected_time <= valid_exhaust[TIME_COL].max():
                        hover_exhaust = np.interp(selected_time, valid_exhaust[TIME_COL], valid_exhaust[EXHAUST_TEMP_COL])
                        exhaust_temp_str = f"{hover_exhaust:.1f}℃"

                # 투입 온도 보간
                if INLET_TEMP_COL in df.columns:
                    valid_inlet = df.dropna(subset=[TIME_COL, INLET_TEMP_COL])
                    if len(valid_inlet) > 1 and selected_time <= valid_inlet[TIME_COL].max():
                        hover_inlet = np.interp(selected_time, valid_inlet[TIME_COL], valid_inlet[INLET_TEMP_COL])
                        inlet_temp_str = f"{hover_inlet:.1f}℃"

                # ROR 보간
                if EXHAUST_ROR_COL in df.columns:
                    valid_ror = df.dropna(subset=[TIME_COL, EXHAUST_ROR_COL])
                    if len(valid_ror) > 1 and selected_time <= valid_ror[TIME_COL].max():
                        # ROR은 일반적으로 이전 값 유지 또는 보간 (여기서는 보간 사용)
                        hover_ror = np.interp(selected_time, valid_ror[TIME_COL], valid_ror[EXHAUST_ROR_COL])
                        ror_str = f"{hover_ror:.3f}℃/sec"

            st.markdown(f"<p style='margin:0; font-size: 0.95em;'>&nbsp;&nbsp;• 배기 온도: {exhaust_temp_str}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin:0; font-size: 0.95em;'>&nbsp;&nbsp;• 투입 온도: {inlet_temp_str}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin-bottom:0.8em; font-size: 0.95em;'>&nbsp;&nbsp;• 배기 ROR: {ror_str}</p>", unsafe_allow_html=True)

# 파일이 업로드되지 않았거나 처리된 데이터가 없을 경우 안내 메시지
elif not uploaded_files:
    st.info("분석할 CSV 파일을 업로드해주세요.")
