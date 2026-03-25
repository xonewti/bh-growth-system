import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# --- 1. 기본 설정 및 구글 시트 연결 ---

# 캐싱 적용: 시트 연결 객체는 세션 내에서 유지
def connect_spreadsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        # 선생님의 실제 구글 시트 ID를 아래에 넣어주세요
        sheet = client.open_by_key("1SU5O5K40TMLaBWdeViEKGCes6QT9y6qykYhkNzGF5Ew") 
        return sheet
    except Exception as e:
        st.error(f"시트 연결 오류: {e}")
        return None

# 캐싱 적용: 덕목 설정은 10분 동안 다시 읽지 않고 메모리에서 꺼내씀 (속도 향상 및 오류 방지)
@st.cache_data(ttl=600)
def get_settings(_sheet, grade):
    try:
        settings_sheet = _sheet.worksheet("Settings")
        records = settings_sheet.get_all_records()
        return {r['구분']: r['덕목이름'] for r in records if str(r['학년']) == str(grade)}
    except:
        return {}

# --- 2. 시각화 함수 ---
def create_radar(data_df, cat_name, virtues_dict):
    cols = [f'{cat_name}{i}' for i in range(1,6)]
    v_names = [virtues_dict.get(c, c) for c in cols]
    current_month = datetime.now().month
    this_month_df = data_df[data_df['시간'].dt.month == current_month].copy()
    
    if this_month_df.empty: return None

    fig = go.Figure()
    for idx, (index, row) in enumerate(this_month_df.sort_values('시간').iterrows()):
        r_values = [row[c] for c in cols]
        r_values.append(r_values[0])
        fig.add_trace(go.Scatterpolar(
            r=r_values, theta=v_names + [v_names[0]], fill='toself', name=f"{idx+1}회차"
        ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[1, 5], dtick=1)),
        title=f"이번 달 {cat_name} 세부 분석", height=450
    )
    return fig

# --- 메인 앱 시작 ---
st.set_page_config(page_title="법환초 성장 시스템", layout="wide")

sheet = connect_spreadsheet()

if sheet:
    menu = st.sidebar.radio("메뉴 선택", ["🌱 학생 기록 및 조회", "🔐 선생님 관리 페이지"])

    if menu == "🌱 학생 기록 및 조회":
        st.title("🌱 법환초 학생 성장 기록장")
        with st.sidebar:
            grade = st.selectbox("학년", [3,4,5,6])
            class_num = st.selectbox("반", [1,2])
            student_id = st.number_input("번호", 1, 40, 1)
            name = st.text_input("이름")
        
        virtues = get_settings(sheet, grade)

        t1, t2 = st.tabs(["📝 기록하기", "📈 나의 성장 데이터"])

        with t1:
            v_tabs = st.tabs(["🌱 성장", "🤝 공감", "🌈 행복"])
            scores = {}
            for idx, cat in enumerate(["성장", "공감", "행복"]):
                with v_tabs[idx]:
                    for i in range(1, 6):
                        k = f"{cat}{i}"
                        scores[k] = st.slider(virtues.get(k, k), 1, 5, 3, key=f"s_{k}_{grade}")
            
            reflection = st.text_area("✍️ 반성의 글 (이번 주 다짐을 적어주세요)", height=150)
            
            if st.button("🚀 기록 저장하기"):
                if not name:
                    st.warning("이름을 입력해주세요.")
                else:
                    try:
                        ws = sheet.worksheet(f"{grade}학년{class_num}반")
                        row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grade, class_num, student_id, name]
                        row += [scores[f"성장{i}"] for i in range(1,6)] + [scores[f"공감{i}"] for i in range(1,6)] + [scores[f"행복{i}"] for i in range(1,6)]
                        row += [reflection, ""] 
                        ws.append_row(row)
                        st.success("성공적으로 저장되었습니다!")
                        st.cache_data.clear() # 저장 후에는 새로운 데이터를 위해 캐시 삭제
                    except:
                        st.error("데이터 저장 중 오류가 발생했습니다.")

        with t2:
            if name:
                try:
                    ws = sheet.worksheet(f"{grade}학년{class_num}반")
                    df = pd.DataFrame(ws.get_all_records())
                    if not df.empty:
                        df['시간'] = pd.to_datetime(df['시간'], format='mixed')
                        my_df = df[(df['번호'] == student_id) & (df['이름'] == name)].copy()
                        
                        if not my_df.empty:
                            st.header(f"👋 {name} 학생의 성장 리포트")
                            
                            fb_df = my_df[my_df['선생님피드백'].astype(str).str.strip() != ""].sort_values('시간', ascending=False)
                            if not fb_df.empty:
                                with st.expander("💬 선생님의 따뜻한 한마디", expanded=True):
                                    for _, r in fb_df.iterrows():
                                        st.info(f"**[{r['시간'].strftime('%m월 %d일')}]** {r['선생님피드백']}")
                            
                            for cat in ['성장', '공감', '행복']:
                                fig = create_radar(my_df, cat, virtues)
                                if fig: st.plotly_chart(fig, use_container_width=True)
                            
                            st.subheader("📊 월별 성장 추이")
                            my_df['월'] = my_df['시간'].dt.strftime('%m월')
                            monthly_summary = my_df.groupby('월').apply(lambda x: pd.Series({
                                '성장 평균': x[[f'성장{i}' for i in range(1,6)]].mean().mean(),
                                '공감 평균': x[[f'공감{i}' for i in range(1,6)]].mean().mean(),
                                '행복 평균': x[[f'행복{i}' for i in range(1,6)]].mean().mean()
                            })).reset_index()
                            
                            fig_line = px.line(monthly_summary, x='월', y=['성장 평균', '공감 평균', '행복 평균'], markers=True)
                            fig_line.update_layout(yaxis=dict(range=[1, 5], dtick=0.5))
                            st.plotly_chart(fig_line, use_container_width=True)
                except:
                    st.info("데이터를 불러오는 중입니다...")

    elif menu == "🔐 선생님 관리 페이지":
        st.title("🔐 관리자 대시보드")
        pw = st.text_input("비밀번호", type="password")
        if pw == "bh1123":
            grade_sel = st.selectbox("조회 학년 ", [3,4,5,6])
            class_sel = st.selectbox("조회 반 ", [1,2])
            virtues = get_settings(sheet, grade_sel)
            
            all_data = []
            for c in [1, 2]:
                try:
                    tmp_df = pd.DataFrame(sheet.worksheet(f"{grade_sel}학년{c}반").get_all_records())
                    all_data.append(tmp_df)
                except: pass
            
            if all_data:
                full_df = pd.concat(all_data)
                full_df['시간'] = pd.to_datetime(full_df['시간'], format='mixed')
                class_df = full_df[full_df['반'] == class_sel].copy()
                
                target_cols = [f'성장{i}' for i in range(1,6)] + [f'공감{i}' for i in range(1,6)] + [f'행복{i}' for i in range(1,6)]
                for c in target_cols: 
                    full_df[c] = pd.to_numeric(full_df[c], errors='coerce')
                    class_df[c] = pd.to_numeric(class_df[c], errors='coerce')

                st.subheader(f"📍 {grade_sel}학년 전체 vs {class_sel}반 비교")
                col1, col2 = st.columns(2)
                
                def get_summary(in_df):
                    s = in_df[[f'성장{i}' for i in range(1,6)]].mean().mean()
                    e = in_df[[f'공감{i}' for i in range(1,6)]].mean().mean()
                    h = in_df[[f'행복{i}' for i in range(1,6)]].mean().mean()
                    return [s, e, h]
                
                labels = ['성장 평균', '공감 평균', '행복 평균']
                with col1:
                    st.plotly_chart(px.bar(x=labels, y=get_summary(full_df), title="학년 전체 평균", range_y=[1,5]), use_container_width=True)
                with col2:
                    st.plotly_chart(px.bar(x=labels, y=get_summary(class_df), title="학급 평균", range_y=[1,5], color_discrete_sequence=['orange']), use_container_width=True)

                st.divider()
                st.subheader("✍️ 학생별 피드백 관리")
                class_df['sheet_row'] = class_df.index + 2
                sel_name = st.selectbox("학생 선택", class_df['이름'].unique())
                s_data = class_df[class_df['이름'] == sel_name].sort_values('시간', ascending=False)
                
                for i, row in s_data.iterrows():
                    with st.expander(f"📅 {row['시간'].strftime('%m/%d')} 기록"):
                        st.write(f"**다짐:** {row['반성의글']}")
                        fb_input = st.text_input("피드백 입력", value=str(row['선생님피드백']), key=f"fb_{i}")
                        if st.button("저장", key=f"btn_{i}"):
                            ws_up = sheet.worksheet(f"{grade_sel}학년{class_sel}반")
                            ws_up.update_cell(int(row['sheet_row']), 22, fb_input)
                            st.success("저장되었습니다!")
                            st.cache_data.clear()
