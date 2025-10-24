import streamlit as st
import pandas as pd
import numpy as np
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# --- 백엔드 함수 (변경 없음) ---
def calculate_ror(df):
    if 'temp above' not in df.columns or 'time' not in df.columns: df['ror_calc'] = np.nan; return df
    if df['temp above'].isnull().all(): df['ror_calc'] = np.nan; return df
    last_valid_index = df['temp above'].last_valid_index()
    if last_valid_index is None: df['ror_calc'] = np.nan; return df
    calc_df = df.loc[0:last_valid_index].copy()
    delta_temp = calc_df['temp above'].diff(); delta_time = calc_df['time'].diff()
    ror = (delta_temp / delta_time).replace([np.inf, -np.inf], 0).fillna(0)
    calc_df['ror_calc'] = ror; df.update(calc_df)
    return df

# --- UI 및 앱 실행 로직 ---
st.set_page_config(layout="wide")
st.title("🔥 Ikawa Roast Log Analyzer")
st.markdown("**(v.0.9 - Dynamic Fan Axis)**") # 버전 업데이트

# --- Session State 초기화 (변경 없음) ---
if 'processed_logs' not in st.session_state: st.session_state.processed_logs = {}
if 'selected_time' not in st.session_state: st.session_state.selected_time = 0
if 'axis_ranges' not in st.session_state:
    st.session_state.axis_ranges = {
        'x': [0, 480], 'y_temp': [60, 290], 'y_ror': [0.0, 50.0],
        'y_fan1': [5500, 15000], 'y_fan2': [900, 1500],
        'y_hum1': [8, 22], 'y_hum2': [-0.04, 0.06]
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
TIME_COL = 'time'; EXHAUST_TEMP_COL = 'temp above'; INLET_TEMP_COL = 'temp below'
EXHAUST_ROR_COL = 'ror_above'; STATE_COL = 'state'; FAN_SPEED_COL = 'fan speed'
HUMIDITY_COL = 'abs_humidity'; HUMIDITY_ROC_COL = 'abs_humidity_roc'

# --- 사이드바 UI (변경 없음) ---
with st.sidebar:
    st.header("⚙️ 보기 옵션")
    profile_names_sidebar = list(st.session_state.processed_logs.keys())
    if profile_names_sidebar:
        default_selected = st.session_state.get('selected_profiles', profile_names_sidebar)
        default_selected = [p for p in default_selected if p in profile_names_sidebar]
        if not default_selected: default_selected = profile_names_sidebar
        st.session_state.selected_profiles = st.multiselect("그래프에 표시할 로그 선택", options=profile_names_sidebar, default=default_selected)
    else:
        st.info("CSV 파일을 업로드하면 로그 목록이 나타납니다.")
        st.session_state.selected_profiles = []
    st.subheader("축 범위 조절")
    axis_ranges = st.session_state.axis_ranges
    col1, col2 = st.columns(2)
    with col1:
        x_min = st.number_input("X축 최소값(시간)", value=axis_ranges['x'][0])
        y_temp_min = st.number_input("Y축(온도) 최소값", value=axis_ranges['y_temp'][0])
        y_ror_min = st.number_input("보조Y축(ROR) 최소값", value=float(axis_ranges['y_ror'][0]), format="%.2f")
        y_fan1_min = st.number_input("Y축(팬1 High) 최소값", value=axis_ranges['y_fan1'][0])
        y_fan2_min = st.number_input("보조Y축(팬2 Low) 최소값", value=axis_ranges['y_fan2'][0])
        y_hum1_min = st.number_input("Y축(습도) 최소값", value=axis_ranges['y_hum1'][0])
        y_hum2_min = st.number_input("보조Y축(습도RoC) 최소값", value=float(axis_ranges['y_hum2'][0]), format="%.4f")
    with col2:
        x_max = st.number_input("X축 최대값(시간)", value=axis_ranges['x'][1])
        y_temp_max = st.number_input("Y축(온도) 최대값", value=axis_ranges['y_temp'][1])
        y_ror_max = st.number_input("보조Y축(ROR) 최대값", value=float(axis_ranges['y_ror'][1]), format="%.2f")
        y_fan1_max = st.number_input("Y축(팬1 High) 최대값", value=axis_ranges['y_fan1'][1])
        y_fan2_max = st.number_input("보조Y축(팬2 Low) 최대값", value=axis_ranges['y_fan2'][1])
        y_hum1_max = st.number_input("Y축(습도) 최대값", value=axis_ranges['y_hum1'][1])
        y_hum2_max = st.number_input("보조Y축(습도RoC) 최대값", value=float(axis_ranges['y_hum2'][1]), format="%.4f")
    st.session_state.axis_ranges = {
        'x': [x_min, x_max], 'y_temp': [y_temp_min, y_temp_max], 'y_ror': [y_ror_min, y_ror_max],
        'y_fan1': [y_fan1_min, y_fan1_max], 'y_fan2': [y_fan2_min, y_fan2_max],
        'y_hum1': [y_hum1_min, y_hum1_max], 'y_hum2': [y_hum2_min, y_hum2_max]
    }

# --- 파일 업로드 UI (변경 없음) ---
uploaded_files = st.file_uploader("CSV 로그 파일을 여기에 업로드하세요.", type="csv", accept_multiple_files=True)

# --- 데이터 로딩 및 정제 (변경 없음) ---
if uploaded_files:
    current_file_names = sorted([f.name for f in uploaded_files])
    previous_file_names = st.session_state.get('uploaded_file_names', [])
    if current_file_names != previous_file_names:
        # (코드 생략 - 이전과 동일)
        st.session_state.processed_logs.clear(); st.session_state.selected_profiles = []
        st.write("---"); st.subheader("⏳ 파일 처리 중...")
        all_files_valid = True; log_dfs_for_processing = {}
        for uploaded_file in uploaded_files:
            profile_name = uploaded_file.name.replace('.csv', '')
            try:
                bytes_data = uploaded_file.getvalue()
                try: decoded_data = bytes_data.decode('utf-8-sig')
                except UnicodeDecodeError: decoded_data = bytes_data.decode('utf-8')
                stringio = io.StringIO(decoded_data)
                stringio.seek(0); header_line = stringio.readline().strip(); headers = [h.strip() for h in header_line.split(',')]
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
                cols_to_convert = [EXHAUST_TEMP_COL, INLET_TEMP_COL, EXHAUST_ROR_COL, FAN_SPEED_COL, HUMIDITY_COL, HUMIDITY_ROC_COL]
                for col in cols_to_convert:
                    if col in roasting_df.columns:
                        roasting_df[col] = pd.to_numeric(roasting_df[col], errors='coerce')
                    else:
                        if col not in [HUMIDITY_COL, HUMIDITY_ROC_COL]:
                             st.warning(f"'{uploaded_file.name}': 필수 열 '{col}'이 없습니다.")
                        roasting_df[col] = np.nan
                log_dfs_for_processing[profile_name] = roasting_df
            except Exception as e:
                st.error(f"'{uploaded_file.name}' 파일을 처리하는 중 오류 발생: {e}"); all_files_valid = False
        if all_files_valid and log_dfs_for_processing:
            st.session_state.processed_logs = log_dfs_for_processing
            st.session_state.selected_profiles = list(log_dfs_for_processing.keys())
            st.session_state.uploaded_file_names = current_file_names
            st.success("✅ 파일 처리 완료!")
            st.rerun()


# --- 그래프 및 분석 패널 UI ---
if st.session_state.processed_logs:
    st.header("📈 그래프 및 분석")
    graph_col, analysis_col = st.columns([0.7, 0.3])
    max_time = 0
    # --- 여기가 수정된 부분: 팬 스케일 확인 로직 추가 ---
    selected_logs = {name: st.session_state.processed_logs[name] for name in st.session_state.get('selected_profiles', []) if name in st.session_state.processed_logs}
    has_high_scale_fan = False
    has_low_scale_fan = False
    FAN_SCALE_THRESHOLD = 2000
    for df in selected_logs.values():
        if TIME_COL in df.columns and not df[TIME_COL].dropna().empty:
            max_time = max(max_time, df[TIME_COL].max())
        if FAN_SPEED_COL in df.columns and not df[FAN_SPEED_COL].dropna().empty:
            max_fan = df[FAN_SPEED_COL].max()
            if max_fan > FAN_SCALE_THRESHOLD: has_high_scale_fan = True
            else: has_low_scale_fan = True
    max_time = max(max_time, 1)
    # --- 수정 끝 ---

    with graph_col:
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.5, 0.25, 0.25], vertical_spacing=0.03, specs=[[{"secondary_y": True}], [{"secondary_y": True}], [{"secondary_y": True}]])
        selected_profiles_data = st.session_state.get('selected_profiles', [])
        colors = px.colors.qualitative.Plotly
        color_map = {name: colors[i % len(colors)] for i, name in enumerate(st.session_state.processed_logs.keys())}

        for name in selected_profiles_data:
            df = st.session_state.processed_logs.get(name); color = color_map.get(name)
            if df is not None and color is not None:
                # --- 온도/ROR 그래프 (row=1) ---
                if TIME_COL in df.columns and EXHAUST_TEMP_COL in df.columns:
                    valid_df_exhaust = df.dropna(subset=[TIME_COL, EXHAUST_TEMP_COL])
                    if len(valid_df_exhaust) > 1: fig.add_trace(go.Scatter(x=valid_df_exhaust[TIME_COL], y=valid_df_exhaust[EXHAUST_TEMP_COL], mode='lines', name=f'{name} Exhaust Temp', line=dict(color=color, dash='solid')), row=1, col=1, secondary_y=False)
                if TIME_COL in df.columns and INLET_TEMP_COL in df.columns:
                     valid_df_inlet = df.dropna(subset=[TIME_COL, INLET_TEMP_COL])
                     if len(valid_df_inlet) > 1: fig.add_trace(go.Scatter(x=valid_df_inlet[TIME_COL], y=valid_df_inlet[INLET_TEMP_COL], mode='lines', name=f'{name} Inlet Temp', line=dict(color=color, dash='solid')), row=1, col=1, secondary_y=False)
                if TIME_COL in df.columns and EXHAUST_ROR_COL in df.columns:
                    valid_df_ror = df.dropna(subset=[TIME_COL, EXHAUST_ROR_COL])
                    if len(valid_df_ror) > 1:
                        ror_df = valid_df_ror.iloc[1:];
                        if not ror_df.empty: fig.add_trace(go.Scatter(x=ror_df[TIME_COL], y=ror_df[EXHAUST_ROR_COL], mode='lines', name=f'{name} ROR', line=dict(color=color, dash='dot'), showlegend=False), row=1, col=1, secondary_y=True)

                # --- 습도 그래프 (row=2) ---
                humidity_plotted_row2 = False
                if TIME_COL in df.columns and HUMIDITY_COL in df.columns:
                     valid_df_hum = df.dropna(subset=[TIME_COL, HUMIDITY_COL])
                     if len(valid_df_hum) > 1:
                         fig.add_trace(go.Scatter(x=valid_df_hum[TIME_COL], y=valid_df_hum[HUMIDITY_COL], mode='lines', name=f'{name} Humidity', line=dict(color=color, dash='solid'), showlegend=True), row=2, col=1, secondary_y=False)
                         humidity_plotted_row2 = True
                if TIME_COL in df.columns and HUMIDITY_ROC_COL in df.columns:
                     valid_df_hum_roc = df.dropna(subset=[TIME_COL, HUMIDITY_ROC_COL])
                     if len(valid_df_hum_roc) > 1:
                         fig.add_trace(go.Scatter(x=valid_df_hum_roc[TIME_COL], y=valid_df_hum_roc[HUMIDITY_ROC_COL], mode='lines', name=f'{name} Humidity RoC', line=dict(color=color, dash='solid'), showlegend=True), row=2, col=1, secondary_y=True)
                         humidity_plotted_row2 = True

                # --- 팬 그래프 (row=3) ---
                if TIME_COL in df.columns and FAN_SPEED_COL in df.columns:
                    valid_df_fan = df.dropna(subset=[TIME_COL, FAN_SPEED_COL])
                    if len(valid_df_fan) > 1:
                        if valid_df_fan[FAN_SPEED_COL].max() > FAN_SCALE_THRESHOLD:
                            fig.add_trace(go.Scatter(x=valid_df_fan[TIME_COL], y=valid_df_fan[FAN_SPEED_COL], mode='lines', name=f'{name} Fan Speed (High)', line=dict(color=color, dash='solid'), showlegend=True), row=3, col=1, secondary_y=False)
                        else:
                            fig.add_trace(go.Scatter(x=valid_df_fan[TIME_COL], y=valid_df_fan[FAN_SPEED_COL], mode='lines', name=f'{name} Fan Speed (Low)', line=dict(color=color, dash='solid'), showlegend=True), row=3, col=1, secondary_y=True)

        selected_time_int = int(st.session_state.get('selected_time', 0)); fig.add_vline(x=selected_time_int, line_width=1, line_dash="dash", line_color="grey")
        axis_ranges = st.session_state.axis_ranges
        fig.update_layout(height=1100, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        fig.update_xaxes(range=axis_ranges['x'], showticklabels=False, dtick=60, row=1, col=1)
        fig.update_xaxes(range=axis_ranges['x'], showticklabels=False, dtick=60, row=2, col=1)
        fig.update_xaxes(range=axis_ranges['x'], title_text='시간 (초)', dtick=60, row=3, col=1)
        fig.update_yaxes(title_text="온도 (°C)", range=axis_ranges['y_temp'], dtick=10, row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="ROR (℃/sec)", range=axis_ranges['y_ror'], showgrid=False, row=1, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Abs Humidity", range=axis_ranges['y_hum1'], row=2, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Humidity RoC", range=axis_ranges['y_hum2'], showgrid=False, row=2, col=1, secondary_y=True)

        # --- 여기가 수정된 부분: 팬 Y축 범위 동적 설정 ---
        if has_high_scale_fan and not has_low_scale_fan: # High 스케일만 있을 때
            fig.update_yaxes(title_text="Fan Speed (High)", range=axis_ranges['y_fan1'], row=3, col=1, secondary_y=False)
            fig.update_yaxes(showticklabels=False, showgrid=False, row=3, col=1, secondary_y=True) # 보조축 숨김
        elif not has_high_scale_fan and has_low_scale_fan: # Low 스케일만 있을 때
             fig.update_yaxes(title_text="Fan Speed (Low)", range=axis_ranges['y_fan2'], row=3, col=1, secondary_y=True) # 보조축만 사용
             fig.update_yaxes(range=axis_ranges['y_fan2'], showticklabels=False, showgrid=False, row=3, col=1, secondary_y=False) # 주축은 범위만 맞추고 숨김
        elif has_high_scale_fan and has_low_scale_fan: # 둘 다 있을 때
             fig.update_yaxes(title_text="Fan Speed (High)", range=axis_ranges['y_fan1'], row=3, col=1, secondary_y=False)
             fig.update_yaxes(title_text="Fan Speed (Low)", range=axis_ranges['y_fan2'], showgrid=False, row=3, col=1, secondary_y=True)
        else: # 팬 데이터 없을 때 (기본값)
            fig.update_yaxes(title_text="Fan Speed (High)", range=axis_ranges['y_fan1'], row=3, col=1, secondary_y=False)
            fig.update_yaxes(title_text="Fan Speed (Low)", range=axis_ranges['y_fan2'], showgrid=False, row=3, col=1, secondary_y=True)
        # --- 수정 끝 ---

        st.plotly_chart(fig, use_container_width=True)

    with analysis_col:
        # (분석 패널 코드는 이전과 동일 - 코드 생략)
        st.subheader("🔍 분석 정보"); st.markdown("---")
        st.write("**총 로스팅 시간**"); # ... (이하 동일) ...
        # ... (슬라이더 및 상세 정보 표시 코드 동일) ...


elif not uploaded_files:
    st.info("분석할 CSV 파일을 업로드해주세요.")
