import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import re

# --- [고정] 학년별 설정 ---
GRADE_CONFIG = {
    3: {"sheet_id": "1qxJcwM6igCcB4rjChzkCQmuyx8luhO15PPtEBCtZjHw", "form_url": "https://forms.gle/EyrzKRutz3tJVqpb8"},
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

def create_radar(df, cat_name, virtues_dict, mode='weekly'):
    cols = [f'{cat_name}{i}' for i in range(1, 6)]
    v_labels = [virtues_dict.get(c, c) if virtues_dict.get(c, c) else c for c in cols]
    if df.empty: return None
    
    fig = go.Figure()
    if mode == 'monthly':
        curr_m = datetime.now().month
        m_df = df[df['시간'].dt.month == curr_m]
        if m_df.empty: m_df = df
        r_vals = [m_df[c].astype(float).mean() for c in cols if c in m_df.columns]
        title = f"📅 {curr_m}월 나의 평균"
        color = "rgba(100, 149, 237, 0.6)"
    else:
        recent = df.sort_values('시간').iloc[-1]
        r_vals = [float(recent[c]) for c in cols if c in recent.index]
        title = "🚀 이번 주의 나의 모습"
        color = "rgba(255, 99, 132, 0.8)"

    if not r_vals or len(r_vals) < 5: return None
    r_vals.append(r_vals[0])
    
    fig.add_trace(go.Scatterpolar(r=r_vals, theta=v_labels + [v_labels[0]], fill='toself', fillcolor=color))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[1, 5])), title=dict(text=title, x=0.5), height=350)
    return fig

# --- 메인 시작 ---
st.set_page_config(page_title="법환초 성장 시스템", layout="wide")
st.sidebar.title("🏫 법환초 성장 시스템")
menu = st.sidebar.radio("메뉴 선택", ["🌱 학생 기록 및 데이터 조회", "🔐 선생님 관리"])
st.sidebar.divider()
selected_grade = st.sidebar.selectbox("나의 학년", [3, 4, 5, 6])
selected_class = st.sidebar.selectbox("나의 반", [1, 2])

sheet = connect_spreadsheet(selected_grade)

if sheet:
    virtue_mapping = get_virtue_names(sheet)

    if "학생 기록" in menu:
        st.title(f"🌱 {selected_grade}학년 {selected_class}반 성장 기록장")
        tab1, tab2 = st.tabs(["📝 기록하기", "📈 나의 데이터 조회"])

        with tab1:
            st.markdown("#### 🌱 이번 주의 나는 얼마나 성장했나요? 설문지를 작성하며 나의 성장을 기록해 봅시다. 📝")
            st.link_button(f"🚀 {selected_grade}학년 {selected_class}반 기록장 열기", 
                           GRADE_CONFIG[selected_grade]["form_url"], 
                           use_container_width=True, type="primary")

        with tab2:
            c1, c2 = st.columns(2)
            with c1: student_id_in = st.number_input("번호", 1, 40, 1)
            with c2: student_name_in = st.text_input("이름")

            if student_name_in:
                try:
                    ws = sheet.worksheet(f"{selected_class}반")
                    raw_data = ws.get_all_values()
                    
                    if len(raw_data) > 1:
                        header = raw_data[0] 
                        df = pd.DataFrame(raw_data[1:], columns=header)
                        
                        # 열 제목 매핑
                        new_col_map = {}
                        for original_col in df.columns:
                            clean = re.sub(r'[^가-힣a-zA-Z0-9]', '', original_col)
                            if '타임' in clean or '시간' in clean: new_col_map[original_col] = '시간'
                            elif '번호' in clean: new_col_map[original_col] = '번호'
                            elif '이름' in clean: new_col_map[original_col] = '이름'
                            elif '반성' in clean or '다짐' in clean: new_col_map[original_col] = '반성'
                            elif '피드백' in clean: new_col_map[original_col] = '피드백'
                            else:
                                for p in ['성장', '공감', '행복']:
                                    for j in range(1, 6):
                                        if f"{p}{j}" in clean: new_col_map[original_col] = f"{p}{j}"
                        
                        df = df.rename(columns=new_col_map)

                        def parse_korean_date(date_str):
                            try:
                                d_str = str(date_str).replace("오전", "AM").replace("오후", "PM")
                                return pd.to_datetime(d_str)
                            except: return pd.to_datetime(date_str, errors='coerce')

                        if '번호' in df.columns and '이름' in df.columns:
                            df['번호'] = df['번호'].apply(lambda x: str(int(float(x))) if str(x).strip() else "")
                            df['이름'] = df['이름'].astype(str).str.strip()
                            df['시간'] = df['시간'].apply(parse_korean_date)
                            df = df.dropna(subset=['시간']).copy()

                            s_id, s_name = str(int(student_id_in)), student_name_in.strip()
                            my_df = df[(df['번호'] == s_id) & (df['이름'] == s_name)].copy()

                            if not my_df.empty:
                                st.success(f"✅ {s_name} 학생 확인되었습니다.")
                                for cat in ['성장', '공감', '행복']:
                                    st.subheader(f"📍 {cat} 영역 분석")
                                    l, r = st.columns(2)
                                    with l: st.plotly_chart(create_radar(my_df, cat, virtue_mapping, 'monthly'), use_container_width=True)
                                    with r: st.plotly_chart(create_radar(my_df, cat, virtue_mapping, 'weekly'), use_container_width=True)
                                
                                # --- [고정 레이아웃] 나의 성장 기록 히스토리 ---
                                st.divider()
                                st.subheader("📝 나의 성장 기록 히스토리")
                                
                                # 제목 고정
                                h_col1, h_col2 = st.columns(2)
                                with h_col1: st.info("🙋‍♂️ **내가 쓴 반성의 글**")
                                with h_col2: st.success("👨‍🏫 **선생님의 피드백**")

                                history_df = my_df.sort_values('시간', ascending=False)
                                for _, row in history_df.iterrows():
                                    # 24시간제 시간 표시
                                    d_time = row['시간'].strftime('%Y-%m-%d %H:%M')
                                    st.caption(f"⏱️ 기록 시간: {d_time}")
                                    
                                    b_col1, b_col2 = st.columns(2)
                                    with b_col1:
                                        content = str(row.get('반성', '내용 없음')).strip()
                                        st.markdown(f'<div style="background-color:#f0f2f6; padding:15px; border-radius:10px;">{content}</div>', unsafe_allow_html=True)
                                    with b_col2:
                                        fb = str(row.get('피드백', '')).strip()
                                        fb_display = fb if fb and fb not in ['None', 'nan', '', '0'] else "*(확인 중)*"
                                        st.markdown(f'<div style="background-color:#e8f4ea; padding:15px; border-radius:10px;">{fb_display}</div>', unsafe_allow_html=True)
                                    st.write("") 
                                    st.divider()
                            else:
                                st.warning(f"'{s_name}' 학생의 {s_id}번 데이터를 찾을 수 없습니다.")
                        else:
                            st.error("열 인식 오류")
                    else:
                        st.info("기록이 없습니다.")
                except Exception as e:
                    st.error(f"오류: {e}")

    elif "선생님 관리" in menu:
        st.title("🔐 선생님 관리 페이지")
        st.info("관리 기능 구현 준비 중")
