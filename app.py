import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 설정 (ID와 URL을 꼭 확인하세요!) ---
GRADE_CONFIG = {
    3: {"sheet_id": "1qxJcwM6igCcB4rjChzkCQmuyx8luhO15PPtEBCtZjHw", "form_url": "https://forms.gle/MU3Mtie7kemq6rif7"},
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
    # 해당 영역(성장, 공감, 행복)의 컬럼들 찾기
    cols = [f'{cat_name}{i}' for i in range(1,6)]
    
    # 데이터프레임에 해당 컬럼이 하나도 없으면 중단
    if not any(c in data_df.columns for c in cols): return None
    
    # 그래프에 표시할 덕목 이름 준비
    v_names = [virtues_dict.get(c, c) for c in cols]
    
    # 이번 달 데이터 필터링
    current_month = datetime.now().month
    this_month_df = data_df[data_df['시간'].dt.month == current_month].copy()
    
    if this_month_df.empty: return None

    fig = go.Figure()
    # 회차별로 선 그리기
    for idx, (index, row) in enumerate(this_month_df.sort_values('시간').iterrows()):
        r_values = []
        for c in cols:
            val = row[c] if c in row else 0
            r_values.append(float(val) if pd.notnull(val) else 0)
        
        r_values.append(r_values[0]) # 폐곡선 만들기
        fig.add_trace(go.Scatterpolar(
            r=r_values, 
            theta=v_names + [v_names[0]], 
            fill='toself', 
            name=f"{idx+1}회차"
        ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[1, 5], dtick=1)),
        title=f"이번 달 {cat_name} 분석", 
        height=400,
        margin=dict(l=30, r=30, t=50, b=30)
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
            with c1: class_num = st.selectbox("반", [1, 2])
            with c2: student_name = st.text_input("이름")
            with c3: student_id = st.number_input("번호", 1, 40, 1)

            if student_name:
                try:
                    ws = sheet.worksheet(f"{class_num}반")
                    data = ws.get_all_values()
                    df = pd.DataFrame(data[1:], columns=data[0])
                    
                    # 1. 열 이름 자동 매칭 (타임스탬프, 성장1~5 등)
                    new_cols = {}
                    for col in df.columns:
                        if '타임스탬프' in col or '시간' in col: new_cols[col] = '시간'
                        if '번호' in col: new_cols[col] = '번호'
                        if '이름' in col: new_cols[col] = '이름'
                        if '피드백' in col: new_cols[col] = '선생님피드백'
                        for p in ['성장', '공감', '행복']:
                            for i in range(1, 6):
                                if f"{p}{i}" in col: new_cols[col] = f"{p}{i}"
                    df = df.rename(columns=new_cols)
                    
                    # 2. 데이터 타입 변환 (숫자로 강제 변환)
                    df['시간'] = pd.to_datetime(df['시간'], errors='coerce')
                    df['번호'] = pd.to_numeric(df['번호'], errors='coerce')
                    for c in df.columns:
                        if any(p in c for p in ['성장', '공감', '행복']):
                            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

                    # 3. 학생 필터링
                    my_df = df[(df['번호'] == student_id) & (df['이름'] == student_name)].copy()

                    if not my_df.empty:
                        st.success(f"✅ {student_name} 학생 확인되었습니다.")
                        
                        # 그래프 영역
                        chart_cols = st.columns(3)
                        categories = ['성장', '공감', '행복']
                        for i, cat in enumerate(categories):
                            with chart_cols[i]:
                                fig = create_radar(my_df, cat, virtues)
                                if fig: st.plotly_chart(fig, use_container_width=True)
                                else: st.info(f"{cat} 데이터가 아직 없습니다.")
                        
                        # 피드백 영역
                        if '선생님피드백' in my_df.columns:
                            fb_list = my_df[my_df['선생님피드백'].astype(str).str.strip() != ""].sort_values('시간', ascending=False)
                            if not fb_list.empty:
                                with st.expander("💬 선생님의 따뜻한 한마디", expanded=True):
                                    for _, r in fb_list.iterrows():
                                        st.info(f"**[{r['시간'].strftime('%m/%d')}]** {r['선생님피드백']}")
                    else:
                        st.warning("데이터를 찾을 수 없습니다. 번호와 이름을 확인하세요.")
                except Exception as e:
                    st.error(f"분석 중 오류 발생: {e}")
