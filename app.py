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
st.markdown("**(v.0.6 - Final Style Adjustments)**")

# --- Session State 초기화 (변경 없음) ---
if 'processed_logs' not in st.session_state: st.session_state.processed_logs = {}
if 'selected_time' not in st.session_state: st.session_state.selected_time = 0
if 'axis_ranges' not in st.session_state:
    st.session_state.axis_ranges = {
        'x': [0, 480], 'y_temp': [60, 290], 'y_ror': [0.0, 50.0],
        'y_fan1': [5500, 15000], 'y_fan2': [900, 1500],
        'y_hum1': [8, 22], 'y_hum2': [-0.01, 0.06]
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
    # (코드 생략)
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
        # (코드 생략)
        pass # Placeholder for actual data loading/cleaning code


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
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.5, 0.25, 0.25], vertical_spacing=0.03, specs=[[{"secondary_y": True}], [{"secondary_y": True}], [{"secondary_y": True}]])
        selected_profiles_data = st.session_state.get('selected_profiles', [])
        colors = px.colors.qualitative.Plotly
        color_map = {name: colors[i % len(colors)] for i, name in enumerate(st.session_state.processed_logs.keys())}
        FAN_SCALE_THRESHOLD = 2000

        for name in selected_profiles_data:
            df = st.session_state.processed_logs.get(name); color = color_map.get(name)
            if df is not None and color is not None:
                # --- 온도/ROR 그래프 (row=1) ---
                if TIME_COL in df.columns and EXHAUST_TEMP_COL in df.columns:
                    valid_df_exhaust = df.dropna(subset=[TIME_COL, EXHAUST_TEMP_COL])
                    if len(valid_df_exhaust) > 1:
                        # legendgroup 제거
                        fig.add_trace(go.Scatter(x=valid_df_exhaust[TIME_COL], y=valid_df_exhaust[EXHAUST_TEMP_COL], mode='lines', name=f'{name} Exhaust Temp', line=dict(color=color, dash='solid')), row=1, col=1, secondary_y=False)
                if TIME_COL in df.columns and INLET_TEMP_COL in df.columns:
                     valid_df_inlet = df.dropna(subset=[TIME_COL, INLET_TEMP_COL])
                     if len(valid_df_inlet) > 1:
                         # legendgroup 제거
                         fig.add_trace(go.Scatter(x=valid_df_inlet[TIME_COL], y=valid_df_inlet[INLET_TEMP_COL], mode='lines', name=f'{name} Inlet Temp', line=dict(color=color, dash='solid')), row=1, col=1, secondary_y=False)
                if TIME_COL in df.columns and EXHAUST_ROR_COL in df.columns:
                    valid_df_ror = df.dropna(subset=[TIME_COL, EXHAUST_ROR_COL])
                    if len(valid_df_ror) > 1:
                        ror_df = valid_df_ror.iloc[1:];
                        if not ror_df.empty:
                            # legendgroup 제거
                            fig.add_trace(go.Scatter(x=ror_df[TIME_COL], y=ror_df[EXHAUST_ROR_COL], mode='lines', name=f'{name} ROR', line=dict(color=color, dash='dot'), showlegend=False), row=1, col=1, secondary_y=True)

                # --- 습도 그래프 (row=2) ---
                humidity_plotted_row2 = False
                if TIME_COL in df.columns and HUMIDITY_COL in df.columns:
                     valid_df_hum = df.dropna(subset=[TIME_COL, HUMIDITY_COL])
                     if len(valid_df_hum) > 1:
                         # legendgroup 제거
                         fig.add_trace(go.Scatter(x=valid_df_hum[TIME_COL], y=valid_df_hum[HUMIDITY_COL], mode='lines', name=f'{name} Humidity', line=dict(color=color, dash='solid'), showlegend=False), row=2, col=1, secondary_y=False)
                         humidity_plotted_row2 = True
                if TIME_COL in df.columns and HUMIDITY_ROC_COL in df.columns:
                     valid_df_hum_roc = df.dropna(subset=[TIME_COL, HUMIDITY_ROC_COL])
                     if len(valid_df_hum_roc) > 1:
                         # legendgroup 제거
                         fig.add_trace(go.Scatter(x=valid_df_hum_roc[TIME_COL], y=valid_df_hum_roc[HUMIDITY_ROC_COL], mode='lines', name=f'{name} Humidity RoC', line=dict(color=color, dash='solid'), showlegend=False), row=2, col=1, secondary_y=True)
                         humidity_plotted_row2 = True

                # --- 팬 그래프 (row=3) ---
                if TIME_COL in df.columns and FAN_SPEED_COL in df.columns:
                    valid_df_fan = df.dropna(subset=[TIME_COL, FAN_SPEED_COL])
                    if len(valid_df_fan) > 1:
                        if valid_df_fan[FAN_SPEED_COL].max() > FAN_SCALE_THRESHOLD:
                            # legendgroup 제거
                            fig.add_trace(go.Scatter(x=valid_df_fan[TIME_COL], y=valid_df_fan[FAN_SPEED_COL], mode='lines', name=f'{name} Fan Speed (High)', line=dict(color=color, dash='solid'), showlegend=False), row=3, col=1, secondary_y=False)
                        else:
                            # legendgroup 제거
                            fig.add_trace(go.Scatter(x=valid_df_fan[TIME_COL], y=valid_df_fan[FAN_SPEED_COL], mode='lines', name=f'{name} Fan Speed (Low)', line=dict(color=color, dash='solid'), showlegend=False), row=3, col=1, secondary_y=True)

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
        fig.update_yaxes(title_text="Fan Speed (High)", range=axis_ranges['y_fan1'], row=3, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Fan Speed (Low)", range=axis_ranges['y_fan2'], showgrid=False, row=3, col=1, secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

    with analysis_col:
        # (코드 생략)
        pass # Placeholder for actual analysis panel code

elif not uploaded_files:
    st.info("분석할 CSV 파일을 업로드해주세요.")
