def connect_spreadsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # [보안 코드] 파일 대신 스트림릿 금고(Secrets)에서 직접 열쇠를 꺼냅니다.
    creds_info = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_dict(creds_info, scope)
    
    client = gspread.authorize(creds)
    sheet = client.open("법환초_성장데이터시스템") 
    return sheet

import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# --- 1. 기본 설정 및 구글 시트 연결 ---
def connect_spreadsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('key.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open("법환초_성장데이터시스템")
    return sheet

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

# 세션 상태 초기화 (데이터 휘발 방지)
if 'df_admin' not in st.session_state: st.session_state.df_admin = None
if 'target_class' not in st.session_state: st.session_state.target_class = ""

try:
    sheet = connect_spreadsheet()
    virtues = get_settings(sheet)
except Exception as e:
    st.error(f"연결 오류: {e}"); st.stop()

menu = st.sidebar.radio("메뉴 선택", ["🌱 학생 기록 및 조회", "🔐 선생님 관리 페이지"])

# --- [1] 학생 페이지 ---
if menu == "🌱 학생 기록 및 조회":
    st.title("🌱 법환초 학생 성장 기록장")
    with st.sidebar:
        grade, class_num = st.selectbox("학년", [3,4,5,6]), st.selectbox("반", [1,2])
        student_id, name = st.number_input("번호", 1, 40, 1), st.text_input("이름")

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
                except: st.error(f"'{ws_name}' 시트를 찾을 수 없습니다.")

    with t2:
        if name:
            try:
                ws = sheet.worksheet(f"{grade}학년{class_num}반")
                df = pd.DataFrame(ws.get_all_records())
                if not df.empty:
                    score_cols = [f'성장{i}' for i in range(1,6)] + [f'공감{i}' for i in range(1,6)] + [f'행복{i}' for i in range(1,6)]
                    for c in score_cols: df[c] = pd.to_numeric(df[c], errors='coerce')
                    df['시간'] = pd.to_datetime(df['시간'], format='mixed')
                    df['성장_평균'], df['공감_평균'], df['행복_평균'] = df[[f'성장{i}' for i in range(1,6)]].mean(axis=1), df[[f'공감{i}' for i in range(1,6)]].mean(axis=1), df[[f'행복{i}' for i in range(1,6)]].mean(axis=1)
                    df['월'] = df['시간'].dt.strftime('%m월')
                    my_df = df[(df['번호'] == student_id) & (df['이름'] == name)].copy()
                    if not my_df.empty:
                        st.header(f"👋 {name} 학생의 성장 리포트")
                        fb_df = my_df[my_df['선생님피드백'] != ''].sort_values('시간', ascending=False)
                        if not fb_df.empty:
                            for _, r in fb_df.iterrows():
                                with st.chat_message("assistant"): st.write(f"**[{r['시간'].strftime('%m월 %d일')} 피드백]** {r['선생님피드백']}")
                        for cat in ['성장', '공감', '행복']:
                            fig = create_detailed_radar(my_df, cat, virtues)
                            if fig: st.plotly_chart(fig, use_container_width=True)
                        m_avg = my_df.groupby('월')[['성장_평균', '공감_평균', '행복_평균']].mean().reset_index()
                        st.plotly_chart(px.line(m_avg, x='월', y=['성장_평균', '공감_평균', '행복_평균'], markers=True), use_container_width=True)
            except: st.info("데이터를 불러올 수 없습니다. 학년/반을 확인해 주세요.")

# --- [2] 선생님 페이지 ---
elif menu == "🔐 선생님 관리 페이지":
    st.title("🔐 관리자 대시보드")
    pw = st.text_input("비밀번호", type="password", key="admin_pw")
    
    if pw == "bh1123":
        # 1. 학급 조회 섹션
        with st.expander("🔍 학급 선택 및 조회", expanded=st.session_state.df_admin is None):
            c1, c2 = st.columns(2)
            sel_g = c1.selectbox("학년", [3,4,5,6], key="g_select")
            sel_c = c2.selectbox("반", [1,2], key="c_select")
            if st.button("학급 데이터 불러오기"):
                st.session_state.df_admin = None # 초기화
                st.session_state.target_class = f"{sel_g}학년{sel_c}반"
                try:
                    ws_admin = sheet.worksheet(st.session_state.target_class)
                    raw_data = ws_admin.get_all_records()
                    if raw_data:
                        df_l = pd.DataFrame(raw_data)
                        df_l['sheet_row'] = df_l.index + 2
                        score_cols = [f'성장{i}' for i in range(1,6)] + [f'공감{i}' for i in range(1,6)] + [f'행복{i}' for i in range(1,6)]
                        for c in score_cols: df_l[c] = pd.to_numeric(df_l[c], errors='coerce')
                        df_l['시간'] = pd.to_datetime(df_l['시간'], format='mixed')
                        df_l['성장_평균'], df_l['공감_평균'], df_l['행복_평균'] = df_l[[f'성장{i}' for i in range(1,6)]].mean(axis=1), df_l[[f'공감{i}' for i in range(1,6)]].mean(axis=1), df_l[[f'행복{i}' for i in range(1,6)]].mean(axis=1)
                        df_l['월'] = df_l['시간'].dt.strftime('%m월')
                        st.session_state.df_admin = df_l
                        st.rerun()
                    else:
                        st.warning(f"'{st.session_state.target_class}'에 데이터가 없습니다.")
                        st.session_state.df_admin = None
                except Exception as e:
                    st.error(f"❌ '{st.session_state.target_class}' 시트를 찾을 수 없습니다. (시트 이름을 확인해 주세요)")
                    st.session_state.df_admin = None

        # 2. 분석 및 피드백 탭
        if st.session_state.df_admin is not None:
            st.success(f"✅ {st.session_state.target_class} 데이터 로드 완료")
            t_admin = st.tabs(["📊 학급 통계", "👤 학생별 피드백"])
            
            with t_admin[0]:
                st.subheader("📈 학급 월별 성장")
                m_avg = st.session_state.df_admin.groupby('월')[['성장_평균', '공감_평균', '행복_평균']].mean().reset_index()
                st.plotly_chart(px.line(m_avg, x='월', y=['성장_평균', '공감_평균', '행복_평균'], markers=True), use_container_width=True)
                
                st.divider()
                st.subheader("☁️ 이달의 마음 키워드")
                curr_m = datetime.now().strftime('%m월')
                m_text = " ".join(st.session_state.df_admin[st.session_state.df_admin['월'] == curr_m]['반성의글'].astype(str))
                if len(m_text.strip()) > 5:
                    sw = set(['합니다', '하겠습니다', '했다', '하고', '것입니다', '있는', '있습니다'])
                    wc = WordCloud(font_path='/System/Library/Fonts/Supplemental/AppleGothic.ttf', background_color='white', stopwords=sw, width=800, height=400).generate(m_text)
                    fig_wc, ax = plt.subplots(); ax.imshow(wc); ax.axis('off'); st.pyplot(fig_wc)

            with t_admin[1]:
                df = st.session_state.df_admin
                all_nums = sorted(list(df['번호'].unique()))
                # [수정] selectbox를 확실히 작동하게 하는 핵심 로직
                sel_no = st.selectbox("학생 번호 선택", options=all_nums, key="admin_student_sb")
                
                s_data = df[df['번호'] == sel_no].sort_values('시간', ascending=False)
                st.subheader(f"👤 {sel_no}번 {s_data['이름'].iloc[0]} 학생 관리")
                for i, row in s_data.iterrows():
                    with st.expander(f"📅 {row['시간'].strftime('%Y-%m-%d %H:%M')} 기록"):
                        st.write(f"**다짐/반성:** {row['반성의글']}")
                        fb_val = st.text_input("피드백 입력", value=str(row['선생님피드백']), key=f"fbi_{i}")
                        if st.button("피드백 저장", key=f"fbb_{i}"):
                            ws_up = sheet.worksheet(st.session_state.target_class)
                            ws_up.update_cell(row['sheet_row'], df.columns.get_loc("선생님피드백")+1, fb_val)
                            st.success("저장 완료! (다시 조회 버튼을 눌러주세요)")
    elif pw != "": st.error("비밀번호가 틀렸습니다.")
