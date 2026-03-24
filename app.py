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
    try:
        creds_info = st.secrets["gcp_service_account"]
        # 함수 이름 주의: from_json_keyfile_dict
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        # 선생님의 시트 ID를 아래 따옴표 안에 넣어주세요
        sheet = client.open_by_key("1SU5O5K40TMLaBWdeViEKGCes6QT9y6qykYhkNzGF5Ew") 
        return sheet
    except Exception as e:
        st.error(f"시트 연결 오류: {e}")
        return None

def get_settings(sheet, grade):
    try:
        settings_sheet = sheet.worksheet("Settings")
        records = settings_sheet.get_all_records()
        # 해당 학년에 맞는 덕목만 필터링
        return {r['구분']: r['덕목이름'] for r in records if str(r['학년']) == str(grade)}
    except: return {}

# --- 2. 시각화 함수 ---
def create_radar(data_df, cat_name, virtues_dict):
    cols = [f'{cat_name}{i}' for i in range(1,6)]
    v_names = [virtues_dict.get(c, c) for c in cols]
    
    # [학생1] 주차가 계속 쌓이지 않도록 이번 달 데이터만 필터링
    current_month = datetime.now().month
    this_month_df = data_df[data_df['시간'].dt.month == current_month].copy()
    
    if this_month_df.empty: return None

    fig = go.Figure()
    for idx, (index, row) in enumerate(this_month_df.sort_values('시간').iterrows()):
        r_values = [row[c] for c in cols]
        r_values.append(r_values[0])
        fig.add_trace(go.Scatterpolar(
            r=r_values, theta=v_names + [v_names[0]], fill='toself',
            name=f"{idx+1}회차"
        ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[1, 5])),
        title=f"이번 달 {cat_name} 세부 분석", height=400
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
        
        virtues = get_settings(sheet, grade) # 학년별 덕목 로드

        t1, t2 = st.tabs(["📝 기록하기", "📈 나의 성장 데이터"])

        with t1:
            # 기록 양식 생략 (기존과 동일)
            v_tabs = st.tabs(["🌱 성장", "🤝 공감", "🌈 행복"])
            scores = {}
            for idx, cat in enumerate(["성장", "공감", "행복"]):
                with v_tabs[idx]:
                    for i in range(1, 6):
                        k = f"{cat}{i}"
                        scores[k] = st.slider(virtues.get(k, k), 1, 5, 3, key=f"s_{k}")
            reflection = st.text_area("✍️ 반성의 글")
            if st.button("🚀 기록 저장하기"):
                # 저장 로직 (기존과 동일)
                ws = sheet.worksheet(f"{grade}학년{class_num}반")
                row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grade, class_num, student_id, name]
                row += [scores[f"성장{i}"] for i in range(1,6)] + [scores[f"공감{i}"] for i in range(1,6)] + [scores[f"행복{i}"] for i in range(1,6)]
                row += [reflection, ""]
                ws.append_row(row)
                st.success("기록 완료!")

        with t2:
            if name:
                ws = sheet.worksheet(f"{grade}학년{class_num}반")
                df = pd.DataFrame(ws.get_all_records())
                if not df.empty:
                    df['시간'] = pd.to_datetime(df['시간'], format='mixed')
                    my_df = df[(df['번호'] == student_id) & (df['이름'] == name)].copy()
                    
                    if not my_df.empty:
                        # [학생1] 한 줄에 하나씩 방사형 그래프
                        st.plotly_chart(create_radar(my_df, '성장', virtues), use_container_width=True)
                        st.plotly_chart(create_radar(my_df, '공감', virtues), use_container_width=True)
                        st.plotly_chart(create_radar(my_df, '행복', virtues), use_container_width=True)
                        
                        # [학생3] 월별 평균 꺾은선 그래프
                        st.subheader("📊 월별 성장 추이")
                        my_df['월'] = my_df['시간'].dt.strftime('%m월')
                        monthly_avg = my_df.groupby('월')[['성장1','성장2','성장3','성장4','성장5','공감1','공감2','공감3','공감4','공감5','행복1','행복2','행복3','행복4','행복5']].mean()
                        monthly_summary = pd.DataFrame({
                            '성장': monthly_avg[[f'성장{i}' for i in range(1,6)]].mean(axis=1),
                            '공감': monthly_avg[[f'공감{i}' for i in range(1,6)]].mean(axis=1),
                            '행복': monthly_avg[[f'행복{i}' for i in range(1,6)]].mean(axis=1)
                        }).reset_index()
                        
                        fig_line = px.line(monthly_summary, x='월', y=['성장', '공감', '행복'], markers=True)
                        fig_line.update_layout(yaxis=dict(range=[1, 5], dtick=0.5), title="대영역별 월간 평균 변화")
                        st.plotly_chart(fig_line, use_container_width=True)

    elif menu == "🔐 선생님 관리 페이지":
        st.title("🔐 관리자 대시보드")
        pw = st.text_input("비밀번호", type="password")
        if pw == "bh1123":
            grade_sel = st.selectbox("조회 학년", [3,4,5,6])
            class_sel = st.selectbox("조회 반", [1,2])
            virtues = get_settings(sheet, grade_sel) # [선생님2] 학년별 덕목 변경 대응
            
            # 모든 반 데이터 통합 로드 (학년 평균 계산용)
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
                
                # [선생님1] 개요: 학년 평균 vs 학급 평균
                st.subheader(f"📍 {grade_sel}학년 전체 vs {class_sel}반 비교")
                col1, col2 = st.columns(2)
                
                # 계산 로직
                target_cols = [f'성장{i}' for i in range(1,6)] + [f'공감{i}' for i in range(1,6)] + [f'행복{i}' for i in range(1,6)]
                for c in target_cols: 
                    full_df[c] = pd.to_numeric(full_df[c], errors='coerce')
                    class_df[c] = pd.to_numeric(class_df[c], errors='coerce')
                
                grade_avg = full_df[target_cols].mean()
                class_avg = class_df[target_cols].mean()
                
                with col1:
                    fig_grade = px.bar(x=target_cols, y=grade_avg, title=f"{grade_sel}학년 전체 평균")
                    st.plotly_chart(fig_grade, use_container_width=True)
                with col2:
                    fig_class = px.bar(x=target_cols, y=class_avg, title=f"{class_sel}반 전체 평균", color_discrete_sequence=['orange'])
                    st.plotly_chart(fig_class, use_container_width=True)

                # [선생님3] 주간 평균 (막대)
                st.subheader("📅 우리반 주간 세부 덕목 현황")
                class_df['주차'] = class_df['시간'].dt.isocalendar().week
                recent_week = class_df[class_df['주차'] == class_df['주차'].max()]
                week_avg = recent_week[target_cols].mean().reset_index()
                week_avg['덕목명'] = week_avg['index'].map(virtues)
                fig_week = px.bar(week_avg, x='덕목명', y=0, title="이번 주 세부 덕목 평균")
                st.plotly_chart(fig_week, use_container_width=True)

                # [선생님4] 월간 평균 (꺾은선)
                st.subheader("📈 우리반 월간 세부 덕목 추이")
                class_df['월'] = class_df['시간'].dt.strftime('%m월')
                mon_detail = class_df.groupby('월')[target_cols].mean().T
                fig_mon_line = px.line(mon_detail, title="세부 덕목 월별 변화 추이")
                st.plotly_chart(fig_mon_line, use_container_width=True)
