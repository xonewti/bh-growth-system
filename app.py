import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 설정 (선생님의 ID와 URL을 다시 한번만 확인해주세요) ---
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
    except Exception as e:
        st.error(f"시트 연결 실패: {e}")
        return None

# --- 2. 메인 화면 ---
st.set_page_config(page_title="법환초 성장 시스템", layout="wide")
grade = st.sidebar.selectbox("나의 학년", [3, 4, 5, 6])
menu = st.sidebar.radio("메뉴", ["🌱 기록 및 조회", "🔐 선생님 관리"])

sheet = connect_spreadsheet(grade)

if sheet:
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
                    all_data = ws.get_all_values()
                    
                    if len(all_data) > 1:
                        df = pd.DataFrame(all_data[1:], columns=all_data[0])
                        
                        # --- [초강력 매칭 로직] 열 이름이 뭐든 글자만 포함되면 바꿈 ---
                        new_cols = {}
                        for col in df.columns:
                            c_clean = col.replace(" ", "")
                            if '시간' in c_clean or '타임' in c_clean: new_cols[col] = '시간'
                            elif '번호' in c_clean: new_cols[col] = '번호'
                            elif '이름' in c_clean: new_cols[col] = '이름'
                            elif '반성' in c_clean or '다짐' in c_clean: new_cols[col] = '반성'
                            elif '피드백' in c_clean: new_cols[col] = '피드백'
                            else:
                                for p in ['성장', '공감', '행복']:
                                    for i in range(1, 6):
                                        if f"{p}{i}" in c_clean: new_cols[col] = f"{p}{i}"
                        
                        df = df.rename(columns=new_cols)
                        
                        # 데이터 형식 강제 통일 (공백 제거)
                        df['이름'] = df['이름'].str.strip()
                        df['번호'] = df['번호'].astype(str).str.strip()
                        search_id = str(int(student_id))
                        search_name = student_name.strip()

                        # 학생 필터링
                        my_df = df[(df['번호'] == search_id) & (df['이름'] == search_name)].copy()

                        if not my_df.empty:
                            st.success(f"✅ {student_name} 학생 확인!")
                            
                            # 그래프 그리기 (가장 최근 1회분만 우선 복구)
                            latest = my_df.iloc[-1]
                            for cat in ['성장', '공감', '행복']:
                                st.subheader(f"📍 {cat} 분석")
                                cols = [f"{cat}{i}" for i in range(1, 6)]
                                r_values = []
                                for c in cols:
                                    val = latest.get(c, 0)
                                    try: r_values.append(float(val))
                                    except: r_values.append(0)
                                
                                if len(r_values) == 5:
                                    r_values.append(r_values[0])
                                    fig = go.Figure(data=go.Scatterpolar(
                                        r=r_values,
                                        theta=['1','2','3','4','5','1'], # 우선 숫자로 표시
                                        fill='toself'
                                    ))
                                    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[1, 5])), height=350)
                                    st.plotly_chart(fig, use_container_width=True)
                                
                            # 다짐/피드백 표시
                            st.info(f"📝 나의 다짐: {latest.get('반성', '내용 없음')}")
                            if latest.get('피드백'):
                                st.success(f"💬 선생님 피드백: {latest['피드백']}")
                                
                        else:
                            st.warning(f"데이터를 찾을 수 없습니다. (입력값: {search_id}번 {search_name})")
                            st.write("시트의 이름/번호와 정확히 일치하는지 확인해주세요.")
                except Exception as e:
                    st.error(f"시스템 오류: {e}")

    elif menu == "🔐 선생님 관리":
        st.title("선생님 전용 페이지")
        st.write("여기는 잘 작동합니다!")
