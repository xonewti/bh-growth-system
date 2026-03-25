import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# --- 1. 학년별 설정 (여기에 실제 ID와 URL을 꼭 넣어주세요!) ---
GRADE_CONFIG = {
    3: {"sheet_id": "1qxJcwM6igCcB4rjChzkCQmuyx8luhO15PPtEBCtZjHw", "form_url": "https://forms.gle/ByecMuyCb6uwv7D28"},
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
        sheet = client.open_by_key(GRADE_CONFIG[grade]["sheet_id"])
        return sheet
    except Exception as e:
        st.error(f"시트 연결 실패: {e}")
        return None

@st.cache_data(ttl=600)
def get_settings(_sheet, grade):
    try:
        ws = _sheet.worksheet("Settings")
        records = ws.get_all_records()
        return {r['구분']: r['덕목이름'] for r in records if str(r['학년']) == str(grade)}
    except: return {}

def create_radar(data_df, cat_name, virtues_dict):
    cols = [f'{cat_name}{i}' for i in range(1,6)]
    # 만약 데이터에 해당 컬럼이 없으면 빈 그래프 반환
    if not all(c in data_df.columns for c in cols): return None
    
    v_names = [virtues_dict.get(c, c) for c in cols]
    current_month = datetime.now().month
    this_month_df = data_df[data_df['시간'].dt.month == current_month].copy()
    
    if this_month_df.empty: return None

    fig = go.Figure()
    for idx, (index, row) in enumerate(this_month_df.sort_values('시간').iterrows()):
        r_values = [row[c] for c in cols]
        r_values.append(r_values[0])
        fig.add_trace(go.Scatterpolar(r=r_values, theta=v_names + [v_names[0]], fill='toself', name=f"{idx+1}회차"))
    
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[1, 5])), title=f"{cat_name} 분석", height=400)
    return fig

# --- 메인 앱 ---
st.set_page_config(page_title="법환초 성장 시스템", layout="wide")
st.sidebar.title("🏫 법환초 성장 시스템")
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
            col1, col2, col3 = st.columns(3)
            with col1: class_num = st.selectbox("반", [1, 2])
            with col2: student_name = st.text_input("이름")
            with col3: student_id = st.number_input("번호", 1, 40, 1)

            if student_name:
                try:
                    ws = sheet.worksheet(f"{class_num}반")
                    data = ws.get_all_values()
                    df = pd.DataFrame(data[1:], columns=data[0])
                    
                    # --- [핵심: 열 이름 매칭 로직] ---
                    new_cols = {}
                    for col in df.columns:
                        if '타임스탬프' in col: new_cols[col] = '시간'
                        for p in ['성장', '공감', '행복']:
                            for i in range(1, 6):
                                if f"{p}{i}" in col: new_cols[col] = f"{p}{i}"
                    df = df.rename(columns=new_cols)
                    
                    # 데이터 타입 변환
                    df['시간'] = pd.to_datetime(df['시간'], errors='coerce')
                    df['번호'] = pd.to_numeric(df['번호'], errors='coerce')
                    for c in df.columns:
                        if any(p in c for p in ['성장', '공감', '행복']):
                            df[c] = pd.to_numeric(df[c], errors='coerce')

                    my_df = df[(df['번호'] == student_id) & (df['이름'] == student_name)].copy()

                    if not my_df.empty:
                        st.success(f"{student_name} 학생 확인되었습니다.")
                        # 그래프 출력
                        cols = st.columns(3)
                        for i, cat in enumerate(['성장', '공감', '행복']):
                            with cols[i]:
                                fig = create_radar(my_df, cat, virtues)
                                if fig: st.plotly_chart(fig, use_container_width=True)
                        
                        # 피드백 출력
                        if '선생님피드백' in df.columns:
                            fb_df = my_df[my_df['선생님피드백'].str.strip() != ""].sort_values('시간', ascending=False)
                            for _, r in fb_df.iterrows():
                                st.info(f"**[{r['시간'].strftime('%m/%d')}]** {r['선생님피드백']}")
                    else: st.warning("데이터를 찾을 수 없습니다.")
                except Exception as e: st.error(f"오류 발생: {e}")

    elif menu == "🔐 선생님 관리":
        st.title(f"🔐 {grade}학년 관리자 페이지")
        pw = st.text_input("비밀번호", type="password")
        if pw == "bh1123":
            class_sel = st.selectbox("조회할 반", [1, 2])
            try:
                ws = sheet.worksheet(f"{class_sel}반")
                data = ws.get_all_values()
                if len(data) > 1:
                    class_df = pd.DataFrame(data[1:], columns=data[0])
                    class_df['sheet_row'] = class_df.index + 2
                    
                    sel_name = st.selectbox("학생 선택", sorted(class_df['이름'].unique()))
                    s_data = class_df[class_df['이름'] == sel_name].sort_values('시간', ascending=False)
                    
                    for i, row in s_data.iterrows():
                        with st.expander(f"📅 기록 확인 (다짐: {row['반성의글'][:15]}...)"):
                            st.write(f"**아이의 다짐:** {row['반성의글']}")
                            fb_val = st.text_input("피드백 입력", value=str(row.get('선생님피드백', '')), key=f"fb_{i}")
                            if st.button("저장", key=f"btn_{i}"):
                                # 학년 열이 빠져서 피드백은 21번째 열(U열)입니다.
                                ws.update_cell(int(row['sheet_row']), 21, fb_val)
                                st.success("피드백 저장 성공!")
                                st.cache_data.clear()
            except:
                st.error("해당 반의 시트 데이터를 가져올 수 없습니다.")
