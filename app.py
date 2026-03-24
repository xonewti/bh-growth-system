import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# --- 1. 기본 설정 및 구글 시트 연결 ---
def connect_spreadsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Secrets에서 정보 가져오기
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_dict(creds_info, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key("1SU5O5K40TMLaBWdeViEKGCes6QT9y6qykYhkNzGF5Ew")
        return sheet
    except Exception as e:
        st.error(f"시트 연결 오류: {e}")
        return None

def get_settings(sheet):
    try:
        settings_sheet = sheet.worksheet("Settings")
        records = settings_sheet.get_all_records()
        return {r['구분']: r['덕목이름'] for r in records}
    except: return {}

# --- 2. 시각화 함수 (오방형 그래프) ---
def create_detailed_radar(data_df, cat_name, virtues_dict):
    cols = [f'{cat_name}{i}' for i in range(1,6)]
    v_names = [virtues_dict.get(c, c) for c in cols]
    current_month = datetime.now().month
    this_month_df = data_df[data_df['시간'].dt.month == current_month].copy()
    
    if this_month_df.empty: return None

    this_month_df = this_month_df.sort_values('시간')
    this_month_df['주차'] = [f"{i+1}주차" for i in range(len(this_month_df))]
    
    fig = go.Figure()
    color_scales = {'성장': px.colors.sequential.Greens[3:], '공감': px.colors.sequential.Blues[3:], '행복': px.colors.sequential.Oranges[3:]}
    current_colors = color_scales.get(cat_name, px.colors.sequential.Purples[3:])
    
    for idx, (index, row) in enumerate(this_month_df.iterrows()):
        r_values = [row[c] for c in cols]
        r_values.append(r_values[0])
        closed_theta = v_names + [v_names[0]]
        fig.add_trace(go.Scatterpolar(
            r=r_values, theta=closed_theta, fill='toself',
            name=row['주차'], line=dict(color=current_colors[idx % len(current_colors)])
        ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[1, 5], dtick=1)),
        showlegend=True, title=dict(text=f"{cat_name} 분석", x=0.5), height=450
    )
    return fig

# --- 메인 앱 시작 ---
st.set_page_config(page_title="법환초 성장 시스템", layout="wide")

if 'df_admin' not in st.session_state: st.session_state.df_admin = None
if 'target_class' not in st.session_state: st.session_state.target_class = ""

sheet = connect_spreadsheet()
if sheet:
    virtues = get_settings(sheet)

    menu = st.sidebar.radio("메뉴 선택", ["🌱 학생 기록 및 조회", "🔐 선생님 관리 페이지"])

    if menu == "🌱 학생 기록 및 조회":
        st.title("🌱 법환초 학생 성장 기록장")
        with st.sidebar:
            grade = st.selectbox("학년", [3,4,5,6])
            class_num = st.selectbox("반", [1,2])
            student_id = st.number_input("번호", 1, 40, 1)
            name = st.text_input("이름")

        t1, t2 = st.tabs(["📝 기록하기", "📈 나의 성장 데이터"])

        with t1:
            v_tabs = st.tabs(["🌱 성장", "🤝 공감", "🌈 행복"])
            scores = {}
            for idx, cat in enumerate(["성장", "공감", "행복"]):
                with v_tabs[idx]:
                    for i in range(1, 6):
                        k = f"{cat}{i}"
                        scores[k] = st.slider(virtues.get(k, k), 1, 5, 3, key=f"s_{k}")
            reflection = st.text_area("✍️ 반성의 글 (이번 주 다짐을 적어주세요)", height=150)
            if st.button("🚀 기록 저장하기"):
                if not name: st.warning("이름을 입력해주세요.")
                else:
                    ws_name = f"{grade}학년{class_num}반"
                    try:
                        ws = sheet.worksheet(ws_name)
                        row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grade, class_num, student_id, name]
                        row += [scores[f"성장{i}"] for i in range(1,6)] + [scores[f"공감{i}"] for i in range(1,6)] + [scores[f"행복{i}"] for i in range(1,6)]
                        row += [reflection, ""]
                        ws.append_row(row)
                        st.success("기록이 저장되었습니다!")
                    except: st.error(f"'{ws_name}' 시트를 찾을 수 없습니다. 시트 이름을 확인해 주세요.")

        with t2:
            if name:
                try:
                    ws = sheet.worksheet(f"{grade}학년{class_num}반")
                    df = pd.DataFrame(ws.get_all_records())
                    if not df.empty:
                        score_cols = [f'성장{i}' for i in range(1,6)] + [f'공감{i}' for i in range(1,6)] + [f'행복{i}' for i in range(1,6)]
                        for c in score_cols: df[c] = pd.to_numeric(df[c], errors='coerce')
                        df['시간'] = pd.to_datetime(df['시간'], format='mixed')
                        df['성장_평균'] = df[[f'성장{i}' for i in range(1,6)]].mean(axis=1)
                        df['공감_평균'] = df[[f'공감{i}' for i in range(1,6)]].mean(axis=1)
                        df['행복_평균'] = df[[f'행복{i}' for i in range(1,6)]].mean(axis=1)
                        df['월'] = df['시간'].dt.strftime('%m월')
                        
                        my_df = df[(df['번호'] == student_id) & (df['이름'] == name)].copy()
                        if not my_df.empty:
                            st.header(f"👋 {name} 학생의 성장 리포트")
                            fb_df = my_df[my_df['선생님피드백'] != ''].sort_values('시간', ascending=False)
                            if not fb_df.empty:
                                with st.expander("💬 선생님의 따뜻한 한마디", expanded=True):
                                    for _, r in fb_df.iterrows():
                                        st.info(f"**[{r['시간'].strftime('%m월 %d일')}]** {r['선생님피드백']}")
                            
                            c1, c2, c3 = st.columns(3)
                            with c1: 
                                fig1 = create_detailed_radar(my_df, '성장', virtues)
                                if fig1: st.plotly_chart(fig1, use_container_width=True)
                            with c2:
                                fig2 = create_detailed_radar(my_df, '공감', virtues)
                                if fig2: st.plotly_chart(fig2, use_container_width=True)
                            with c3:
                                fig3 = create_detailed_radar(my_df, '행복', virtues)
                                if fig3: st.plotly_chart(fig3, use_container_width=True)
                except: st.info("아직 기록된 데이터가 없거나 학년/반 설정이 다릅니다.")

    elif menu == "🔐 선생님 관리 페이지":
        st.title("🔐 관리자 대시보드")
        pw = st.text_input("비밀번호", type="password")
        if pw == "bh1123":
            with st.expander("🔍 학급 조회", expanded=True):
                c1, c2 = st.columns(2)
                sel_g = c1.selectbox("학년 ", [3,4,5,6])
                sel_c = c2.selectbox("반 ", [1,2])
                if st.button("데이터 로드"):
                    st.session_state.target_class = f"{sel_g}학년{sel_c}반"
                    try:
                        ws_admin = sheet.worksheet(st.session_state.target_class)
                        df_l = pd.DataFrame(ws_admin.get_all_records())
                        if not df_l.empty:
                            df_l['sheet_row'] = df_l.index + 2
                            st.session_state.df_admin = df_l
                            st.success(f"{st.session_state.target_class} 로드 완료")
                        else: st.warning("데이터가 없습니다.")
                    except: st.error("시트를 찾을 수 없습니다.")

            if st.session_state.df_admin is not None:
                df = st.session_state.df_admin
                all_names = df['이름'].unique()
                sel_name = st.selectbox("학생 선택", all_names)
                s_data = df[df['이름'] == sel_name].sort_values('시간', ascending=False)
                
                for i, row in s_data.iterrows():
                    with st.expander(f"📅 {row['시간']} 기록"):
                        st.write(f"**기록 내용:** {row['반성의글']}")
                        fb_val = st.text_input("피드백", value=str(row['선생님피드백']), key=f"fb_{i}")
                        if st.button("피드백 저장", key=f"btn_{i}"):
                            ws_up = sheet.worksheet(st.session_state.target_class)
                            ws_up.update_cell(row['sheet_row'], list(df.columns).index("선생님피드백")+1, fb_val)
                            st.success("저장되었습니다!")
