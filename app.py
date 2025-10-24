import streamlit as st
import pandas as pd
import numpy as np
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# --- 백엔드 함수 (변경 없음) ---
def calculate_ror(df):
    # This function seems unused currently, but keep for potential future use or remove if sure.
    # Placeholder implementation:
    if 'temp above' not in df.columns or 'time' not in df.columns:
        df['ror_calc'] = np.nan
        return df
    if df['temp above'].isnull().all():
        df['ror_calc'] = np.nan
        return df
    last_valid_index = df['temp above'].last_valid_index()
    if last_valid_index is None:
        df['ror_calc'] = np.nan
        return df
    calc_df = df.loc[0:last_valid_index].copy()
    delta_temp = calc_df['temp above'].diff()
    delta_time = calc_df['time'].diff()
    ror = (delta_temp / delta_time).replace([np.inf, -np.inf], 0).fillna(0)
    calc_df['ror_calc'] = ror
    df.update(calc_df)
    return df


# --- UI 및 앱 실행 로직 ---
st.set_page_config(layout="wide")
st.title("🔥 Ikawa Roast Log Analyzer")
st.markdown("**(v.0.4 - Fan/Humidity Graphs)**") # 버전 업데이트

# --- Session State 초기화 (축 범위 추가 및 수정) ---
if 'processed_logs' not in st.session_state: st.session_state.processed_logs = {}
if 'selected_time' not in st.session_state: st.session_state.selected_time = 0
if 'axis_ranges' not in st.session_state:
    st.session_state.axis_ranges = {
        'x': [0, 600],
        'y_temp': [60, 300], # 온도 Y축
        'y_ror': [0.0, 5.0],  # ROR 보조 Y축 (범위 조정)
        'y_fan': [0, 100],  # 팬 속도 Y축
        'y_hum': [0, 20]    # 습도 보조 Y축
    }

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
FAN_SPEED_COL = 'fan speed'           # 팬 속도 추가
HUMIDITY_COL = 'abs_humidity'          # X 모델 전용
HUMIDITY_ROC_COL = 'abs_humidity_roc' # X 모델 전용

# --- 사이드바 UI ---
with st.sidebar:
    st.header("⚙️ 보기 옵션")

    # processed_logs가 채워진 후에만 프로파일 목록 표시
    profile_names_sidebar = list(st.session_state.processed_logs.keys())
    if profile_names_sidebar: # 목록이 있을 때만 multiselect 표시
        default_selected = st.session_state.get('selected_profiles', profile_names_sidebar)
        default_selected = [p for p in default_selected if p in profile_names_sidebar]
        if not default_selected: default_selected = profile_names_sidebar # 선택된게 없으면 다시 전체 선택
        st.session_state.selected_profiles = st.multiselect(
            "그래프에 표시할 로그 선택",
            options=profile_names_sidebar,
            default=default_selected
        )
    else:
        st.info("CSV 파일을 업로드하면 로그 목록이 나타납니다.")
        st.session_state.selected_profiles = [] # 로그 없으면 선택 목록 비움

    st.subheader("축 범위 조절")
    axis_ranges = st.session_state.axis_ranges
    col1, col2 = st.columns(2)
    with col1:
        x_min = st.number_input("X축 최소값(시간)", value=axis_ranges['x'][0])
        y_min = st.number_input("Y축(온도) 최소값", value=axis_ranges['y_temp'][0])
        y2_min = st.number_input("보조Y축(ROR) 최소값", value=float(axis_ranges['y_ror'][0]), format="%.2f") # float 명시, 포맷 수정
        y3_min = st.number_input("Y축(팬) 최소값", value=axis_ranges['y_fan'][0])
        y4_min = st.number_input("보조Y축(습도) 최소값", value=axis_ranges['y_hum'][0])
    with col2:
        x_max = st.number_input("X축 최대값(시간)", value=axis_ranges['x'][1])
        y_max = st.number_input("Y축(온도) 최대값", value=axis_ranges['y_temp'][1])
        y2_max = st.number_input("보조Y축(ROR) 최대값", value=float(axis_ranges['y_ror'][1]), format="%.2f") # float 명시, 포맷 수정
        y3_max = st.number_input("Y축(팬) 최대값", value=axis_ranges['y_fan'][1])
        y4_max = st.number_input("보조Y축(습도) 최대값", value=axis_ranges['y_hum'][1])

    # axis_ranges 업데이트
    st.session_state.axis_ranges = {
        'x': [x_min, x_max],
        'y_temp': [y_min, y_max],
        'y_ror': [y2_min, y2_max],
        'y_fan': [y3_min, y3_max],
        'y_hum': [y4_min, y4_max]
    }


# --- 파일 업로드 UI ---
uploaded_files = st.file_uploader("CSV 로그 파일을 여기에 업로드하세요.", type="csv", accept_multiple_files=True)

# --- 데이터 로딩 및 정제 ---
if uploaded_files:
    # 파일을 새로 올렸는지 확인하고 처리
    current_file_names = sorted([f.name for f in uploaded_files])
    previous_file_names = st.session_state.get('uploaded_file_names', [])
    if current_file_names != previous_file_names:
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
                df = pd.read_csv(stringio, header=None, skiprows=1, skipinitialspace=True, on_bad_lines='warn')
                if len(headers) >= len(df.columns): df.columns = headers[:len(df.columns)]
                else: df.columns = headers + [f'unknown_{i}' for i in range(len(df.columns) - len(headers))]
                if df.columns[0] != 'time': raise ValueError("첫 열이 'time'이 아닙니다.")

                roasting_df = pd.DataFrame()
                if STATE_COL in df.columns:
                    df[STATE_COL] = df[STATE_COL].astype(str).str.strip().str.lower()
                    start_mask = df[STATE_COL].str.contains('roasting|ready_for_roast', case=False, na=False)
                    end_mask = df[STATE_COL].str.contains('cooling|cooldown', case=False, na=False)
                    start_index = -1
                    if start_mask.any(): start_index = df[start_mask].index[0]
                    end_index = len(df)
                    if end_mask.any(): end_index = df[end_mask].index[0]
                    if start_index != -1: roasting_df = df.iloc[start_index:end_index].copy()
                    else:
                        st.warning(f"'{uploaded_file.name}': 로스팅 시작 상태를 찾을 수 없어 전체 데이터를 사용합니다 (쿨링 제외 시도).")
                        cooling_mask = df[STATE_COL].str.contains('cooling|cooldown', case=False, na=False)
                        roasting_df = df[~cooling_mask].copy()
                else:
                     st.warning(f"'{uploaded_file.name}': 'state' 열이 없어 전체 데이터를 사용합니다.")
                     roasting_df = df.copy()

                if TIME_COL in roasting_df.columns and not roasting_df.empty:
                    start_time = roasting_df[TIME_COL].iloc[0]
                    roasting_df[TIME_COL] = roasting_df[TIME_COL] - start_time

                # 변환할 열 목록에 팬/습도 추가
                cols_to_convert = [EXHAUST_TEMP_COL, INLET_TEMP_COL, EXHAUST_ROR_COL, FAN_SPEED_COL]
                if HUMIDITY_COL in roasting_df.columns: cols_to_convert.append(HUMIDITY_COL)
                if HUMIDITY_ROC_COL in roasting_df.columns: cols_to_convert.append(HUMIDITY_ROC_COL)

                for col in cols_to_convert:
                    if col in roasting_df.columns:
                        roasting_df[col] = pd.to_numeric(roasting_df[col], errors='coerce')
                    else:
                        # 습도 관련 열은 없을 수 있으므로 경고 없이 넘어감
                        if col not in [HUMIDITY_COL, HUMIDITY_ROC_COL]:
                             st.warning(f"'{uploaded_file.name}': 필수 열 '{col}'이 없습니다.")
                        roasting_df[col] = np.nan # 없으면 빈 열 추가

                log_dfs_for_processing[profile_name] = roasting_df

            except Exception as e:
                st.error(f"'{uploaded_file.name}' 파일을 처리하는 중 오류 발생: {e}")
                all_files_valid = False

        if all_files_valid and log_dfs_for_processing:
            st.session_state.processed_logs = log_dfs_for_processing
            st.session_state.selected_profiles = list(log_dfs_for_processing.keys())
            st.session_state.uploaded_file_names = current_file_names # 현재 처리된 파일 이름 저장
            st.success("✅ 파일 처리 완료!")
            st.rerun() # 사이드바와 메인 화면 업데이트 위해 재실행

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
        # 팬/습도 그래프 추가 위해 서브플롯 사양 변경
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4], # 높이 비율 조정
                            vertical_spacing=0.03, specs=[[{"secondary_y": True}], [{"secondary_y": True}]]) # 아래쪽도 보조 Y축 추가

        selected_profiles_data = st.session_state.get('selected_profiles', [])
        colors = px.colors.qualitative.Plotly
        color_map = {name: colors[i % len(colors)] for i, name in enumerate(st.session_state.processed_logs.keys())}

        for name in selected_profiles_data:
            df = st.session_state.processed_logs.get(name); color = color_map.get(name)
            if df is not None and color is not None:
                # --- 온도/ROR 그래프 (row=1) ---
                if TIME_COL in df.columns and EXHAUST_TEMP_COL in df.columns:
                    valid_df_exhaust = df.dropna(subset=[TIME_COL, EXHAUST_TEMP_COL])
                    if len(valid_df_exhaust) > 1: fig.add_trace(go.Scatter(x=valid_df_exhaust[TIME_COL], y=valid_df_exhaust[EXHAUST_TEMP_COL], mode='lines', name=f'{name} Exhaust Temp', line=dict(color=color, dash='solid'), legendgroup=name), row=1, col=1, secondary_y=False)
                if TIME_COL in df.columns and INLET_TEMP_COL in df.columns:
                     valid_df_inlet = df.dropna(subset=[TIME_COL, INLET_TEMP_COL])
                     if len(valid_df_inlet) > 1: fig.add_trace(go.Scatter(x=valid_df_inlet[TIME_COL], y=valid_df_inlet[INLET_TEMP_COL], mode='lines', name=f'{name} Inlet Temp', line=dict(color=color, dash='dash'), legendgroup=name), row=1, col=1, secondary_y=False)
                if TIME_COL in df.columns and EXHAUST_ROR_COL in df.columns:
                    valid_df_ror = df.dropna(subset=[TIME_COL, EXHAUST_ROR_COL])
                    if len(valid_df_ror) > 1:
                        ror_df = valid_df_ror.iloc[1:];
                        if not ror_df.empty: fig.add_trace(go.Scatter(x=ror_df[TIME_COL], y=ror_df[EXHAUST_ROR_COL], mode='lines', name=f'{name} ROR', line=dict(color=color, dash='dot'), legendgroup=name, showlegend=False), row=1, col=1, secondary_y=True)

                # --- 팬/습도 그래프 (row=2) ---
                if TIME_COL in df.columns and FAN_SPEED_COL in df.columns:
                    valid_df_fan = df.dropna(subset=[TIME_COL, FAN_SPEED_COL])
                    if len(valid_df_fan) > 1: fig.add_trace(go.Scatter(x=valid_df_fan[TIME_COL], y=valid_df_fan[FAN_SPEED_COL], mode='lines', name=f'{name} Fan Speed', line=dict(color=color, dash='solid'), legendgroup=name, showlegend=False), row=2, col=1, secondary_y=False)
                if TIME_COL in df.columns and HUMIDITY_COL in df.columns: # 습도 데이터 있을 때만 추가
                     valid_df_hum = df.dropna(subset=[TIME_COL, HUMIDITY_COL])
                     if len(valid_df_hum) > 1: fig.add_trace(go.Scatter(x=valid_df_hum[TIME_COL], y=valid_df_hum[HUMIDITY_COL], mode='lines', name=f'{name} Humidity', line=dict(color=color, dash='dashdot'), legendgroup=name, showlegend=False), row=2, col=1, secondary_y=True) # 보조 Y축 사용
                if TIME_COL in df.columns and HUMIDITY_ROC_COL in df.columns: # 습도 변화율 데이터 있을 때만 추가
                     valid_df_hum_roc = df.dropna(subset=[TIME_COL, HUMIDITY_ROC_COL])
                     if len(valid_df_hum_roc) > 1: fig.add_trace(go.Scatter(x=valid_df_hum_roc[TIME_COL], y=valid_df_hum_roc[HUMIDITY_ROC_COL], mode='lines', name=f'{name} Humidity RoC', line=dict(color=color, dash='longdash'), legendgroup=name, showlegend=False), row=2, col=1, secondary_y=True) # 보조 Y축 사용

        selected_time_int = int(st.session_state.get('selected_time', 0)); fig.add_vline(x=selected_time_int, line_width=1, line_dash="dash", line_color="grey")
        axis_ranges = st.session_state.axis_ranges
        fig.update_layout(height=900, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)) # 높이 복원
        
        # X축 업데이트
        fig.update_xaxes(range=axis_ranges['x'], showticklabels=False, dtick=60, row=1, col=1) # 위쪽 X축 눈금 숨김
        fig.update_xaxes(range=axis_ranges['x'], title_text='시간 (초)', dtick=60, row=2, col=1) # 아래쪽 X축만 표시
        
        # Y축 업데이트 (row=1)
        fig.update_yaxes(title_text="온도 (°C)", range=axis_ranges['y_temp'], dtick=10, row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="ROR (℃/sec)", range=axis_ranges['y_ror'], showgrid=False, row=1, col=1, secondary_y=True)
        
        # Y축 업데이트 (row=2) - 팬/습도
        fig.update_yaxes(title_text="Fan Speed (%)", range=axis_ranges['y_fan'], row=2, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Humidity / RoC", range=axis_ranges['y_hum'], showgrid=False, row=2, col=1, secondary_y=True)

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
            fan_speed_str, humidity_str, humidity_roc_str = "--", "--", "--" # 팬/습도 추가
            
            df = st.session_state.processed_logs.get(name)
            if df is not None:
                if TIME_COL not in df.columns: continue
                # 온도/ROR 보간 (이전과 동일)
                if EXHAUST_TEMP_COL in df.columns:
                    valid_exhaust = df.dropna(subset=[TIME_COL, EXHAUST_TEMP_COL])
                    if len(valid_exhaust) > 1 and selected_time <= valid_exhaust[TIME_COL].max(): hover_exhaust = np.interp(selected_time, valid_exhaust[TIME_COL], valid_exhaust[EXHAUST_TEMP_COL]); exhaust_temp_str = f"{hover_exhaust:.1f}℃"
                if INLET_TEMP_COL in df.columns:
                    valid_inlet = df.dropna(subset=[TIME_COL, INLET_TEMP_COL])
                    if len(valid_inlet) > 1 and selected_time <= valid_inlet[TIME_COL].max(): hover_inlet = np.interp(selected_time, valid_inlet[TIME_COL], valid_inlet[INLET_TEMP_COL]); inlet_temp_str = f"{hover_inlet:.1f}℃"
                if EXHAUST_ROR_COL in df.columns:
                    valid_ror = df.dropna(subset=[TIME_COL, EXHAUST_ROR_COL])
                    if len(valid_ror) > 1 and selected_time <= valid_ror[TIME_COL].max(): hover_ror = np.interp(selected_time, valid_ror[TIME_COL], valid_ror[EXHAUST_ROR_COL]); ror_str = f"{hover_ror:.3f}℃/sec"
                
                # 팬/습도 보간 추가
                if FAN_SPEED_COL in df.columns:
                    valid_fan = df.dropna(subset=[TIME_COL, FAN_SPEED_COL])
                    if len(valid_fan) > 1 and selected_time <= valid_fan[TIME_COL].max(): hover_fan = np.interp(selected_time, valid_fan[TIME_COL], valid_fan[FAN_SPEED_COL]); fan_speed_str = f"{hover_fan:.1f}%"
                if HUMIDITY_COL in df.columns:
                    valid_hum = df.dropna(subset=[TIME_COL, HUMIDITY_COL])
                    if len(valid_hum) > 1 and selected_time <= valid_hum[TIME_COL].max(): hover_hum = np.interp(selected_time, valid_hum[TIME_COL], valid_hum[HUMIDITY_COL]); humidity_str = f"{hover_hum:.2f}"
                if HUMIDITY_ROC_COL in df.columns:
                     valid_hum_roc = df.dropna(subset=[TIME_COL, HUMIDITY_ROC_COL])
                     if len(valid_hum_roc) > 1 and selected_time <= valid_hum_roc[TIME_COL].max(): hover_hum_roc = np.interp(selected_time, valid_hum_roc[TIME_COL], valid_hum_roc[HUMIDITY_ROC_COL]); humidity_roc_str = f"{hover_hum_roc:.4f}"

            st.markdown(f"<p style='margin:0; font-size: 0.95em;'>&nbsp;&nbsp;• Exhaust Temp: {exhaust_temp_str}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin:0; font-size: 0.95em;'>&nbsp;&nbsp;• Inlet Temp: {inlet_temp_str}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin:0; font-size: 0.95em;'>&nbsp;&nbsp;• Exhaust ROR: {ror_str}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin:0; font-size: 0.95em;'>&nbsp;&nbsp;• Fan Speed: {fan_speed_str}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin:0; font-size: 0.95em;'>&nbsp;&nbsp;• Abs Humidity: {humidity_str}</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='margin-bottom:0.8em; font-size: 0.95em;'>&nbsp;&nbsp;• Humidity RoC: {humidity_roc_str}</p>", unsafe_allow_html=True)

# 파일 업로드 안내
elif not uploaded_files:
    st.info("분석할 CSV 파일을 업로드해주세요.")
