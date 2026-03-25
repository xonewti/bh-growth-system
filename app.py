import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 학년별 설정 (ID와 URL을 꼭 확인하세요!) ---
GRADE_CONFIG = {
    3: {"sheet_id": "1qxJcwM6igCcB4rjChzkCQmuyx8luhO15PPtEBCtZjHw", "form_url": "https://forms.gle/e6wysUfcUUjxwq6o7"},
    4: {"sheet_id": "YOUR_SHEET_ID_4", "form_url": "YOUR_FORM_URL_4"},
    5: {"sheet_id": "YOUR_SHEET_ID_5", "form_url": "YOUR_FORM_URL_5"},
    6: {"sheet_id": "YOUR_SHEET_ID_6", "form_url": "YOUR_FORM_URL_6"}
}

def connect_spreadsheet(grade):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(GRADE_CONFIG[grade]["sheet_id"])
    except: return None

@st.cache_data(ttl=600)
def get_virtue_names(_sheet, grade):
    try:
        ws = _sheet.worksheet("Settings")
        data = ws.get_all_records()
        return {str(r['구분']): str(r['덕목이름']) for r in data if str(r['학년']) == str(grade)}
    except: return {}

# --- 2. 비교용 그래프 생성 함수 ---
def create_comparison_radar(df, cat_name, virtues_dict, mode='recent'):
    cols = [f'{cat_name}{i}' for i in range(1, 6)]
    v_labels = [virtues_dict.get(c, c) for c in cols]
    
    if df.empty: return None

    fig = go.Figure()

    if mode == 'monthly':
        # 월간 평균 데이터 계산
        current_month = datetime.now().month
        m_df = df[df['시간'].dt.month == current_month]
        if m_df.empty: m_df = df # 데이터가 없으면 전체 평균
        r_values = [m_df[c].mean() for c in cols]
        title = f"📅 {datetime.now().month}월 나의 평균"
        color = "rgba(100, 149, 237, 0.6)" # 차분한 파란색
    else:
        # 가장 최근 1회 데이터
        recent_row = df.sort_values('시간').iloc[-1]
        r_values = [recent_row[c] for c in cols]
        title = "🚀 방금 입력한 나의 모습"
        color = "rgba(255, 99, 132, 0.8)" # 강조된 붉은색

    r_values = [float(v) for v in r_values]
    r_values.append(r_values[0]) # 폐곡선
    
    fig.add_trace(go.Scatterpolar(
        r=r_values,
        theta=v_labels + [v_labels[0]],
        fill='toself',
        fillcolor=color,
        line=dict(color=color.replace("0.6", "1").replace("0.8", "1")),
        name=title
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[1, 5], dtick=1)),
        title=dict(text=title, x=0.5, font=dict(size=16)),
        height=350,
        margin=dict(l=40, r=40, t=60, b=40),
        showlegend=False
    )
    return fig

# --- 메인 앱 시작 ---
st.set_page_config(page_title="법환초 성장 시스템", layout="wide")
grade = st.sidebar.selectbox("나의 학년", [3, 4, 5, 6])
menu = st.sidebar.radio("메뉴", ["🌱 기록 및 조회", "🔐 선생님 관리"])

sheet = connect_spreadsheet(grade)
if sheet:
    virtue_mapping = get_virtue_names(sheet, grade)

    if menu == "🌱 기록 및 조회":
        st.title(f"🌱 {grade}학년 성장 기록장")
        t1, t2 = st.tabs(["📝 기록하기", "📈 나의 데이터 비교"])

        with t1:
            st.link_button(f"🚀 {grade}학년 설문지 열기", GRADE_CONFIG[grade]["form_url"], use_container_width=True)

        with t2:
            # 입력 섹션
            c1, c2, c3 = st.columns(3)
            with c1: class_num = st.selectbox("반", [1, 2])
            with c2: student_name = st.text_input("이름")
            with c3: student_id = st.number_input("번호", 1, 40, 1)

            if student_name:
                try:
                    ws = sheet.worksheet(f"{class_num}반")
                    data = ws.get_all_values()
                    df = pd.DataFrame(data[1:], columns=data[0])
                    
                    # 이름표 정리 로직
                    new_cols = {}
                    for col in df.columns:
                        c = col.replace(" ", "").replace("[", "").replace("]", "")
                        if '타임스탬프' in c or '시간' in c: new_cols[col] = '시간'
                        if '번호' in c: new_cols[col] = '번호'
                        if '이름' in c: new_cols[col] = '이름'
                        if '피드백' in c: new_cols[col] = '선생님피드백'
                        for p in ['성장', '공감', '행복']:
                            for i in range(1, 6):
                                if f"{p}{i}" in c: new_cols[col] = f"{p}{i}"
                    df = df.rename(columns=new_cols)
                    
                    df['시간'] = pd.to_datetime(df['시간'], errors='coerce')
                    df['번호'] = pd.to_numeric(df['번호'], errors='coerce')
                    for c in df.columns:
                        if any(p in c for p in ['성장', '공감', '행복']):
                            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

                    my_df = df[(df['번호'] == student_id) & (df['이름'].str.strip() == student_name.strip())].copy()

                    if not my_df.empty:
                        st.success(f"✅ {student_name} 학생의 데이터를 분석했습니다.")
                        
                        # --- 주제별 한 줄 레이아웃 ---
                        for cat in ['성장', '공감', '행복']:
                            st.subheader(f"📍 {cat} 영역 분석")
                            left_col, right_col = st.columns(2)
                            
                            with left_col:
                                fig_m = create_comparison_radar(my_df, cat, virtue_mapping, mode='monthly')
                                if fig_m: st.plotly_chart(fig_m, use_container_width=True)
                                else: st.info("월간 데이터가 없습니다.")
                            
                            with right_col:
                                fig_r = create_comparison_radar(my_df, cat, virtue_mapping, mode='recent')
                                if fig_r: st.plotly_chart(fig_r, use_container_width=True)
                                else: st.info("최근 데이터가 없습니다.")
                            st.divider()

                        # 피드백 섹션
                        if '선생님피드백' in my_df.columns:
                            fb_list = my_df[my_df['선생님피드백'].astype(str).str.strip() != ""].sort_values('시간', ascending=False)
                            if not fb_list.empty:
                                with st.expander("💬 선생님의 응원 메시지", expanded=True):
                                    for _, r in fb_list.iterrows():
                                        st.info(f"**[{r['시간'].strftime('%m/%d')}]** {r['선생님피드백']}")
                    else:
                        st.warning("데이터를 찾을 수 없습니다. 번호와 이름을 확인하세요.")
                except Exception as e:
                    st.error(f"분석 중 오류 발생: {e}")
