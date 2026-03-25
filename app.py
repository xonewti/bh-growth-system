import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. 학년별 설정 ---
GRADE_CONFIG = {
    3: {"sheet_id": "1qxJcwM6igCcB4rjChzkCQmuyx8luhO15PPtEBCtZjHw", "form_url": "https://forms.gle/o53FumajR25CRs486"},
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

@st.cache_data(ttl=300)
def get_virtue_names(_sheet, grade):
    try:
        ws = _sheet.worksheet("Settings")
        data = ws.get_all_records()
        # 공백 제거 및 문자열 일치를 위해 strip() 사용
        mapping = {str(r['구분']).strip(): str(r['덕목이름']).strip() for r in data if str(r['학년']) == str(grade)}
        return mapping
    except: return {}

# --- 2. 비교용 그래프 생성 함수 ---
def create_comparison_radar(df, cat_name, virtues_dict, mode='weekly'):
    cols = [f'{cat_name}{i}' for i in range(1, 6)]
    # Settings에 정의된 이름이 있으면 쓰고, 없으면 기본값(성장1 등) 사용
    v_labels = [virtues_dict.get(c, c) for c in cols]
    
    if df.empty: return None

    fig = go.Figure()

    if mode == 'monthly':
        # 월간 평균 데이터
        current_month = datetime.now().month
        m_df = df[df['시간'].dt.month == current_month]
        if m_df.empty: m_df = df
        r_values = [m_df[c].mean() for c in cols]
        title = f"📅 {current_month}월 나의 평균"
        color = "rgba(100, 149, 237, 0.6)"
    else:
        # 이번 주 데이터 (최근 7일) 평균 또는 가장 최근 데이터
        recent_row = df.sort_values('시간').iloc[-1]
        r_values = [recent_row[c] for c in cols]
        title = "🚀 이번 주의 나의 모습" # 제목 수정됨
        color = "rgba(255, 99, 132, 0.8)"

    r_values = [float(v) for v in r_values]
    r_values.append(r_values[0])
    
    fig.add_trace(go.Scatterpolar(
        r=r_values,
        theta=v_labels + [v_labels[0]],
        fill='toself',
        fillcolor=color,
        line=dict(color=color.replace("0.6", "1").replace("0.8", "1")),
        name=title
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[1, 5], dtick=1)),
        title=dict(text=title, x=0.5, font=dict(size=16)),
        height=350,
        margin=dict(l=45, r=45, t=60, b=45),
        showlegend=False
    )
    return fig

# --- 메인 앱 ---
st.set_page_config(page_title="법환초 성장 시스템", layout="wide")
grade = st.sidebar.selectbox("나의 학년", [3, 4, 5, 6])
menu = st.sidebar.radio("메뉴", ["🌱 기록 및 조회", "🔐 선생님 관리"])

sheet = connect_spreadsheet(grade)
if sheet:
    virtue_mapping = get_virtue_names(sheet, grade)

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
                    df = pd.DataFrame(data[1:], columns=data[0])
                    
                    # 열 이름 정리
                    new_cols = {}
                    for col in df.columns:
                        c = col.replace(" ", "").replace("[", "").replace("]", "")
                        if '타임스탬프' in c or '시간' in c: new_cols[col] = '시간'
                        if '번호' in c: new_cols[col] = '번호'
                        if '이름' in c: new_cols[col] = '이름'
                        if '반성의글' in c or '다짐' in c: new_cols[col] = '반성의글'
                        if '피드백' in c: new_cols[col] = '선생님피드백'
                        for p in ['성장', '공감', '행복']:
                            for i in range(1, 6):
                                if f"{p}{i}" in c: new_cols[col] = f"{p}{i}"
                    df = df.rename(columns=new_cols)
                    
                    df['시간'] = pd.to_datetime(df['시간'], errors='coerce')
                    df['번호'] = pd.to_numeric(df['번호'], errors='coerce')
                    for c in df.columns:
                        if any(p in c for p in ['성장', '공감', '행복']):
                            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

                    my_df = df[(df['번호'] == student_id) & (df['이름'].str.strip() == student_name.strip())].copy()

                    if not my_df.empty:
                        st.success(f"✅ {student_name} 학생의 데이터를 분석했습니다.")
                        
                        # 주제별 그래프 출력
                        for cat in ['성장', '공감', '행복']:
                            st.subheader(f"📍 {cat} 영역 분석")
                            left_col, right_col = st.columns(2)
                            with left_col:
                                fig_m = create_comparison_radar(my_df, cat, virtue_mapping, mode='monthly')
                                if fig_m: st.plotly_chart(fig_m, use_container_width=True)
                            with right_col:
                                fig_r = create_comparison_radar(my_df, cat, virtue_mapping, mode='weekly')
                                if fig_r: st.plotly_chart(fig_r, use_container_width=True)
                            st.divider()

                        # --- [추가] 반성의 글 및 선생님 피드백 ---
                        st.subheader("📝 나의 다짐과 선생님의 한마디")
                        recent_data = my_df.sort_values('시간', ascending=False)
                        
                        for _, row in recent_data.iterrows():
                            # 반성의 글이나 피드백 중 하나라도 있으면 출력
                            has_reflection = str(row.get('반성의글', '')).strip() != ""
                            has_feedback = str(row.get('선생님피드백', '')).strip() != ""
                            
                            if has_reflection or has_feedback:
                                with st.expander(f"📅 {row['시간'].strftime('%Y-%m-%d')} 기록 보기"):
                                    if has_reflection:
                                        st.write("**나의 다짐:**")
                                        st.info(row['반성의글'])
                                    if has_feedback:
                                        st.write("**선생님의 피드백:**")
                                        st.success(row['선생님피드백'])
                                    elif not has_feedback:
                                        st.write("*(선생님의 피드백을 기다리고 있어요!)*")
                    else:
                        st.warning("데이터를 찾을 수 없습니다.")
                except Exception as e:
                    st.error(f"오류 발생: {e}")
