import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 기본 설정 (ID/URL은 선생님의 것으로 꼭 확인하세요) ---
GRADE_CONFIG = {
    3: {"sheet_id": "1qxJcwM6igCcB4rjChzkCQmuyx8luhO15PPtEBCtZjHw", "form_url": "https://forms.gle/27eJaKgW8maq3k3f8"},
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

@st.cache_data(ttl=60)
def get_virtue_names(_sheet):
    try:
        ws = _sheet.worksheet("Settings")
        data = ws.get_all_records()
        return {str(r.get('구분', '')).strip(): str(r.get('덕목이름', '')).strip() for r in data}
    except: return {}

# --- 2. 그래프 생성 함수 ---
def create_radar(df, cat_name, virtues_dict, mode='weekly'):
    cols = [f'{cat_name}{i}' for i in range(1, 6)]
    # 덕목 이름 매칭 (안되면 기본값)
    v_labels = [virtues_dict.get(c, c) if virtues_dict.get(c, c) else c for c in cols]
    
    if df.empty: return None
    
    fig = go.Figure()
    if mode == 'monthly':
        curr_m = datetime.now().month
        m_df = df[df['시간'].dt.month == curr_m]
        if m_df.empty: m_df = df
        r_vals = [m_df[c].mean() for c in cols if c in m_df.columns]
        title = f"📅 {curr_m}월 나의 평균"
        color = "rgba(100, 149, 237, 0.6)"
    else:
        recent = df.sort_values('시간').iloc[-1]
        r_vals = [recent[c] for c in cols if c in recent.index]
        title = "🚀 이번 주의 나의 모습"
        color = "rgba(255, 99, 132, 0.8)"

    if len(r_vals) < 5: return None
    r_vals = [float(v) for v in r_vals]
    r_vals.append(r_vals[0])
    
    fig.add_trace(go.Scatterpolar(r=r_vals, theta=v_labels + [v_labels[0]], fill='toself', fillcolor=color))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[1, 5])), title=dict(text=title, x=0.5), height=350)
    return fig

# --- 3. 메인 레이아웃 ---
st.set_page_config(page_title="법환초 성장 시스템", layout="wide")
grade = st.sidebar.selectbox("나의 학년", [3, 4, 5, 6])
# 1번 문제 해결: 관리자 페이지 메뉴 다시 추가
menu = st.sidebar.radio("메뉴", ["🌱 기록 및 조회", "🔐 선생님 관리"])

sheet = connect_spreadsheet(grade)
if sheet:
    virtue_mapping = get_virtue_names(sheet)

    if menu == "🌱 기록 및 조회":
        st.title(f"🌱 {grade}학년 성장 기록장")
        t1, t2 = st.tabs(["📝 기록하기", "📈 나의 데이터 비교"])

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
                    if len(data) > 1:
                        df = pd.DataFrame(data[1:], columns=data[0])
                        
                        # 2번 문제 해결: 열 이름 매칭 로직 (이름으로만 찾기)
                        new_cols = {}
                        for col in df.columns:
                            c = col.replace(" ", "").replace("[", "").replace("]", "")
                            if '타임스탬프' in c or '시간' in c: new_cols[col] = '시간'
                            elif '번호' in c: new_cols[col] = '번호'
                            elif '이름' in c: new_cols[col] = '이름'
                            elif '반성' in c or '다짐' in c: new_cols[col] = '반성의글'
                            elif '피드백' in c: new_cols[col] = '선생님피드백'
                            else:
                                for p in ['성장', '공감', '행복']:
                                    for i in range(1, 6):
                                        if f"{p}{i}" in c: new_cols[col] = f"{p}{i}"
                        
                        df = df.rename(columns=new_cols)
                        df['시간'] = pd.to_datetime(df['시간'], errors='coerce')
                        df = df.dropna(subset=['시간']).copy()
                        df['번호'] = pd.to_numeric(df['번호'], errors='coerce')
                        
                        # 숫자 변환
                        for c in df.columns:
                            if any(p in c for p in ['성장', '공감', '행복']):
                                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

                        my_df = df[(df['번호'] == student_id) & (df['이름'].str.strip() == student_name.strip())].copy()

                        if not my_df.empty:
                            st.success(f"✅ {student_name} 학생 확인되었습니다.")
                            # 그래프 출력
                            for cat in ['성장', '공감', '행복']:
                                st.subheader(f"📍 {cat} 영역 분석")
                                l, r = st.columns(2)
                                with l: 
                                    fig_m = create_radar(my_df, cat, virtue_mapping, 'monthly')
                                    if fig_m: st.plotly_chart(fig_m, use_container_width=True)
                                with r: 
                                    fig_w = create_radar(my_df, cat, virtue_mapping, 'weekly')
                                    if fig_w: st.plotly_chart(fig_w, use_container_width=True)

                            # 텍스트 출력
                            st.subheader("📝 나의 다짐과 선생님의 한마디")
                            latest = my_df.sort_values('시간', ascending=False).iloc[0]
                            with st.expander(f"📅 가장 최근 기록 ({latest['시간'].strftime('%Y-%m-%d')})", expanded=True):
                                st.write("**나의 다짐:**")
                                st.info(latest.get('반성의글', '내용 없음'))
                                fb = str(latest.get('선생님피드백', '')).strip()
                                if fb and fb not in ['None', 'nan', '']:
                                    st.write("**선생님의 피드백:**")
                                    st.success(fb)
                                else: st.write("*(선생님의 피드백을 기다리고 있어요!)*")
                        else: st.warning("해당 이름과 번호의 데이터를 찾을 수 없습니다.")
                except Exception as e: st.error(f"데이터 로드 오류: {e}")

    elif menu == "🔐 선생님 관리":
        st.title("🔐 선생님 관리 페이지")
        st.info("관리자 기능을 이곳에 구현할 예정입니다.")
