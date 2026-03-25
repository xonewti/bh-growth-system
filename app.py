import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 설정 (ID와 URL을 꼭 확인하세요!) ---
GRADE_CONFIG = {
    3: {"sheet_id": "1qxJcwM6igCcB4rjChzkCQmuyx8luhO15PPtEBCtZjHw", "form_url": "https://forms.gle/iVRt84WvXafKJi568"},
    4: {"sheet_id": "4학년_시트_ID", "form_url": "4학년_설문지_URL"},
    5: {"sheet_id": "5학년_시트_ID", "form_url": "5학년_설문지_URL"},
    6: {"sheet_id": "6학년_시트_ID", "form_url": "6학년_설문지_URL"}
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
def get_settings(_sheet, grade):
    try:
        ws = _sheet.worksheet("Settings")
        records = ws.get_all_records()
        return {r['구분']: r['덕목이름'] for r in records if str(r['학년']) == str(grade)}
    except: return {}

def create_radar(data_df, cat_name, virtues_dict):
    cols = [f'{cat_name}{i}' for i in range(1,6)]
    # 데이터에 해당 컬럼들이 있는지 확인
    available_cols = [c for c in cols if c in data_df.columns]
    if not available_cols: return None
    
    v_names = [virtues_dict.get(c, c) for c in cols]
    
    # [수정] 날짜 필터를 없애고 모든 데이터를 표시하도록 변경 (가장 최근 5회 분량)
    plot_df = data_df.sort_values('시간').tail(5)

    fig = go.Figure()
    for idx, (index, row) in enumerate(plot_df.iterrows()):
        r_values = []
        for c in cols:
            val = row[c] if c in row else 0
            try: r_values.append(float(val))
            except: r_values.append(0)
        
        r_values.append(r_values[0])
        fig.add_trace(go.Scatterpolar(
            r=r_values, 
            theta=v_names + [v_names[0]], 
            fill='toself', 
            name=f"{idx+1}회차"
        ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[1, 5], dtick=1)),
        title=f"{cat_name} 성장 곡선", 
        height=400,
        margin=dict(l=40, r=40, t=50, b=40)
    )
    return fig

# --- 메인 앱 ---
st.set_page_config(page_title="법환초 성장 시스템", layout="wide")
grade = st.sidebar.selectbox("나의 학년", [3, 4, 5, 6])
menu = st.sidebar.radio("메뉴", ["🌱 기록 및 조회", "🔐 선생님 관리"])

sheet = connect_spreadsheet(grade)
if sheet:
    virtues = get_settings(sheet, grade)

    if menu == "🌱 기록 및 조회":
        st.title(f"🌱 {grade}학년 성장 기록장")
        t1, t2 = st.tabs(["📝 기록하기", "📈 나의 데이터"])

        with t1:
            st.link_button(f"🚀 {grade}학년 설문지 열기", GRADE_CONFIG[grade]["form_url"], use_container_width=True)

        with t2:
            c1, c2, c3 = st.columns(3)
            with c1: 
                class_num = st.selectbox("반", [1, 2])
            with c2: 
                student_name = st.text_input("이름")
            with c3: 
                student_id = st.number_input("번호", 1, 40, 1)

            if student_name:
                try:
                    ws = sheet.worksheet(f"{class_num}반")
                    data = ws.get_all_values()
                    if len(data) > 1:
                        df = pd.DataFrame(data[1:], columns=data[0])
                        
                        # 열 이름 매칭 로직 (포함 관계 확인)
                        new_cols = {}
                        for col in df.columns:
                            low_col = col.replace(" ", "")
                            if '타임스탬프' in low_col or '시간' in low_col: new_cols[col] = '시간'
                            if '번호' in low_col: new_cols[col] = '번호'
                            if '이름' in low_col: new_cols[col] = '이름'
                            if '피드백' in low_col: new_cols[col] = '선생님피드백'
                            for p in ['성장', '공감', '행복']:
                                for i in range(1, 6):
                                    if f"{p}{i}" in low_col: new_cols[col] = f"{p}{i}"
                        df = df.rename(columns=new_cols)
                        
                        # 타입 변환
                        df['시간'] = pd.to_datetime(df['시간'], errors='coerce')
                        df['번호'] = pd.to_numeric(df['번호'], errors='coerce')
                        
                        # 해당 학생 필터링
                        my_df = df[(df['번호'] == student_id) & (df['이름'].str.strip() == student_name.strip())].copy()

                        if not my_df.empty:
                            st.success(f"✅ {student_name} 학생의 데이터를 불러왔습니다.")
                            
                            chart_cols = st.columns(3)
                            for i, cat in enumerate(['성장', '공감', '행복']):
                                with chart_cols[i]:
                                    fig = create_radar(my_df, cat, virtues)
                                    if fig: st.plotly_chart(fig, use_container_width=True)
                                    else: st.info(f"{cat} 영역 데이터가 부족합니다.")
                        else:
                            st.warning("일치하는 학생 데이터를 찾을 수 없습니다.")
                    else:
                        st.warning("시트에 데이터가 한 건도 없습니다.")
                except Exception as e:
                    st.error(f"데이터 조회 오류: {e}")
