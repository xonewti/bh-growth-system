import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- [불변] 학년별 설정 ---
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
    except:
        return None

@st.cache_data(ttl=60)
def get_virtue_names(_sheet):
    try:
        ws = _sheet.worksheet("Settings")
        data = ws.get_all_records()
        return {str(r.get('구분', '')).strip(): str(r.get('덕목이름', '')).strip() for r in data}
    except:
        return {}

def create_radar(df, cat_name, virtues_dict, mode='weekly'):
    cols = [f'{cat_name}{i}' for i in range(1, 6)]
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

    if not r_vals or len(r_vals) < 5: return None
    r_vals = [float(v) for v in r_vals]
    r_vals.append(r_vals[0])
    
    fig.add_trace(go.Scatterpolar(r=r_vals, theta=v_labels + [v_labels[0]], fill='toself', fillcolor=color))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[1, 5])), title=dict(text=title, x=0.5), height=350)
    return fig

# --- 메인 레이아웃 시작 ---
st.set_page_config(page_title="법환초 성장 시스템", layout="wide")

# [왼쪽 메뉴란 고정]
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

        # --- 1. 기록하기 탭 ---
        with tab1:
            st.markdown("#### 🌱 이번 주의 나는 얼마나 성장했나요? 설문지를 작성하며 나의 성장을 기록해 봅시다. 📝")
            st.link_button(f"🚀 {selected_grade}학년 {selected_class}반 기록장 열기", 
                           GRADE_CONFIG[selected_grade]["form_url"], 
                           use_container_width=True, type="primary")

        # --- 2. 나의 데이터 조회 탭 ---
        with tab2:
            c1, c2 = st.columns([1, 1])
            with c1: student_id_input = st.number_input("번호", 1, 40, 1)
            with c2: student_name_input = st.text_input("이름")

            if student_name_input:
                try:
                    ws = sheet.worksheet(f"{selected_class}반")
                    all_values = ws.get_all_values()
                    
                    if len(all_values) > 1:
                        df = pd.DataFrame(all_values[1:], columns=all_values[0])
                        
                        # 열 이름 강제 매핑 (A열: 타임스탬프 고정)
                        col_map = {}
                        cols = df.columns
                        if len(cols) > 0: col_map[cols[0]] = '시간'
                        if len(cols) > 1: col_map[cols[1]] = '반'
                        if len(cols) > 2: col_map[cols[2]] = '번호'
                        if len(cols) > 3: col_map[cols[3]] = '이름'
                        
                        cats = ['성장', '공감', '행복']
                        for i in range(4, 19):
                            if len(cols) > i:
                                c_idx, s_idx = (i-4) // 5, (i-4) % 5 + 1
                                col_map[cols[i]] = f"{cats[c_idx]}{s_idx}"
                        
                        if len(cols) > 19: col_map[cols[19]] = '반성의글'
                        if len(cols) > 20: col_map[cols[20]] = '선생님피드백'
                        
                        df = df.rename(columns=col_map)

                        # [핵심] 데이터 전처리: 번호(2.0 -> 2) 및 이름 공백 제거
                        def clean_id(x):
                            try: return str(int(float(str(x).strip())))
                            except: return str(x).strip()

                        df['번호'] = df['번호'].apply(clean_id)
                        df['이름'] = df['이름'].astype(str).str.strip()
                        df['시간'] = pd.to_datetime(df['시간'], errors='coerce')
                        df = df.dropna(subset=['시간']).copy()

                        search_id = str(int(student_id_input))
                        search_name = student_name_input.strip()

                        # 필터링 실행
                        my_df = df[(df['번호'] == search_id) & (df['이름'] == search_name)].copy()

                        if not my_df.empty:
                            st.success(f"✅ {search_name} 학생 확인되었습니다.")
                            
                            for cat in ['성장', '공감', '행복']:
                                st.subheader(f"📍 {cat} 영역 분석")
                                l_col, r_col = st.columns(2)
                                with l_col:
                                    fig_m = create_radar(my_df, cat, virtue_mapping, 'monthly')
                                    if fig_m: st.plotly_chart(fig_m, use_container_width=True)
                                with r_col:
                                    fig_w = create_radar(my_df, cat, virtue_mapping, 'weekly')
                                    if fig_w: st.plotly_chart(fig_w, use_container_width=True)
                            
                            st.divider()
                            st.subheader("📝 나의 다짐과 선생님의 한마디")
                            latest = my_df.sort_values('시간', ascending=False).iloc[0]
                            st.write(f"🕒 **기록 시간(타임스탬프):** {latest['시간'].strftime('%Y-%m-%d %H:%M')}")
                            st.info(f"**나의 반성의 글:**\n{latest.get('반성의글', '내용 없음')}")
                            
                            fb = str(latest.get('선생님피드백', '')).strip()
                            if fb and fb not in ['None', 'nan', '']:
                                st.success(f"**선생님의 피드백:**\n{fb}")
                            else:
                                st.write("*(선생님의 피드백을 기다리고 있어요!)*")
                        else:
                            st.warning(f"'{search_name}' 학생의 {search_id}번 데이터를 찾을 수 없습니다.")
                            # 매칭 실패 시 디버깅용 (성공 시 삭제 가능)
                            with st.expander("🔍 매칭 오류 해결 팁"):
                                st.write("입력값:", f"[{search_id}], [{search_name}]")
                                st.write("시트 상단 데이터:", df[['번호', '이름']].head())
                    else:
                        st.info("기록된 데이터가 없습니다.")
                except Exception as e:
                    st.error(f"오류 발생: {e}")

    elif "선생님 관리" in menu:
        st.title("🔐 선생님 관리 페이지")
        st.info("학생 페이지 최적화 완료 후 관리자 기능을 상세 구현할 예정입니다.")
