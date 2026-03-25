import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# --- 1. 학년별 데이터 설정 (선생님께서 채워주세요!) ---
# 각 학년별 구글 설문지 주소와 시트 파일 ID를 매칭합니다.
GRADE_CONFIG = {
    3: {
        "sheet_id": "1qxJcwM6igCcB4rjChzkCQmuyx8luhO15PPtEBCtZjHw",
        "form_url": "https://forms.gle/YfnnX7qcD5rfRXJUA"
    },
    4: {
        "sheet_id": "4학년_시트_ID_입력",
        "form_url": "4학년_구글설문지_링크_입력"
    },
    5: {
        "sheet_id": "5학년_시트_ID_입력",
        "form_url": "5학년_구글설문지_링크_입력"
    },
    6: {
        "sheet_id": "6학년_시트_ID_입력",
        "form_url": "6학년_구글설문지_링크_입력"
    }
}

# --- 2. 구글 시트 연결 함수 ---
def connect_spreadsheet(grade):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        
        # 선택한 학년의 시트 ID 가져오기
        sheet_id = GRADE_CONFIG[grade]["sheet_id"]
        sheet = client.open_by_key(sheet_id)
        return sheet
    except Exception as e:
        st.error(f"{grade}학년 시트 연결 오류: {e}")
        return None

# 설정값 캐싱 (10분)
@st.cache_data(ttl=600)
def get_settings(_sheet, grade):
    try:
        settings_sheet = _sheet.worksheet("Settings")
        records = settings_sheet.get_all_records()
        return {r['구분']: r['덕목이름'] for r in records if str(r['학년']) == str(grade)}
    except:
        return {}

# --- 3. 시각화 함수 ---
def create_radar(data_df, cat_name, virtues_dict):
    cols = [f'{cat_name}{i}' for i in range(1,6)]
    v_names = [virtues_dict.get(c, c) for c in cols]
    
    # 이번 달 데이터만 필터링
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
        title=f"이번 달 {cat_name} 세부 분석", height=400
    )
    return fig

# --- 메인 앱 시작 ---
st.set_page_config(page_title="법환초 성장 시스템", layout="wide")

# 사이드바 설정
st.sidebar.title("🏫 법환초 성장 시스템")
grade = st.sidebar.selectbox("나의 학년", [3, 4, 5, 6])
menu = st.sidebar.radio("메뉴 선택", ["🌱 기록 및 조회", "🔐 선생님 관리"])

# 학년별 시트 연결
sheet = connect_spreadsheet(grade)

if sheet:
    virtues = get_settings(sheet, grade)

    if menu == "🌱 기록 및 조회":
        st.title(f"🌱 {grade}학년 성장 기록장")
        
        t1, t2 = st.tabs(["📝 기록하기 (설문지)", "📈 나의 성장 데이터"])

        with t1:
            st.info("기록은 구글 설문지를 통해 안전하게 저장됩니다. 아래 버튼을 눌러주세요!")
            form_url = GRADE_CONFIG[grade]["form_url"]
            st.link_button(f"🚀 {grade}학년 성장 기록하러 가기", form_url, use_container_width=True)
            st.caption("※ 설문 제출 후 아래 '나의 성장 데이터' 탭에서 결과를 확인하세요.")

        with t2:
            st.subheader("🔍 내 데이터 조회하기")
            col_id, col_name = st.columns(2)
            with col_id: class_num = st.selectbox("반", [1, 2], key="std_class")
            with col_name: student_name = st.text_input("이름을 입력하세요")
            student_id = st.number_input("번호", 1, 40, 1)

            if student_name:
                try:
                    # QUERY 함수로 분류된 '1반' 혹은 '2반' 탭을 읽음
                    ws = sheet.worksheet(f"{class_num}반")
                    df = pd.DataFrame(ws.get_all_records())
                    
                    if not df.empty:
                        # 컬럼명 전처리 (설문지 연결 시 생기는 '타임스탬프' 대응)
                        if '타임스탬프' in df.columns:
                            df = df.rename(columns={'타임스탬프': '시간'})
                        
                        df['시간'] = pd.to_datetime(df['시간'], format='mixed')
                        my_df = df[(df['번호'] == student_id) & (df['이름'] == student_name)].copy()
                        
                        if not my_df.empty:
                            # 1. 선생님 피드백 (V열)
                            fb_df = my_df[my_df['선생님피드백'].astype(str).str.strip() != ""].sort_values('시간', ascending=False)
                            if not fb_df.empty:
                                with st.expander("💬 선생님의 따뜻한 한마디", expanded=True):
                                    for _, r in fb_df.iterrows():
                                        st.info(f"**[{r['시간'].strftime('%m월 %d일')}]** {r['선생님피드백']}")
                            
                            # 2. 방사형 그래프
                            st.divider()
                            c1, c2, c3 = st.columns(3)
                            with c1: 
                                fig1 = create_radar(my_df, '성장', virtues)
                                if fig1: st.plotly_chart(fig1, use_container_width=True)
                            with c2:
                                fig2 = create_radar(my_df, '공감', virtues)
                                if fig2: st.plotly_chart(fig2, use_container_width=True)
                            with c3:
                                fig3 = create_radar(my_df, '행복', virtues)
                                if fig3: st.plotly_chart(fig3, use_container_width=True)

                            # 3. 월별 추이
                            st.subheader("📊 대영역별 성장 추이")
                            my_df['월'] = my_df['시간'].dt.strftime('%m월')
                            monthly = my_df.groupby('월').apply(lambda x: pd.Series({
                                '성장': x[[f'성장{i}' for i in range(1,6)]].mean().mean(),
                                '공감': x[[f'공감{i}' for i in range(1,6)]].mean().mean(),
                                '행복': x[[f'행복{i}' for i in range(1,6)]].mean().mean()
                            })).reset_index()
                            st.plotly_chart(px.line(monthly, x='월', y=['성장', '공감', '행복'], markers=True, range_y=[1,5]), use_container_width=True)
                        else:
                            st.warning("입력된 데이터가 없습니다. 이름과 번호를 확인해 주세요.")
                except:
                    st.error("데이터를 불러오는 중 오류가 발생했습니다. 시트의 탭 이름(1반, 2반)을 확인해 주세요.")

    elif menu == "🔐 선생님 관리":
        st.title(f"🔐 {grade}학년 관리자 페이지")
        pw = st.text_input("비밀번호", type="password")
        if pw == "bh1123":
            class_sel = st.selectbox("조회할 반 선택", [1, 2])
            try:
                ws = sheet.worksheet(f"{class_sel}반")
                class_df = pd.DataFrame(ws.get_all_records())
                
                if not class_df.empty:
                    if '타임스탬프' in class_df.columns:
                        class_df = class_df.rename(columns={'타임스탬프': '시간'})
                    class_df['시간'] = pd.to_datetime(class_df['시간'], format='mixed')
                    
                    st.subheader(f"✍️ {class_sel}반 학생 피드백 관리")
                    # 피드백 저장을 위한 행 번호 계산 (헤더 포함 +2)
                    class_df['sheet_row'] = class_df.index + 2
                    
                    sel_name = st.selectbox("학생 선택", sorted(class_df['이름'].unique()))
                    student_records = class_df[class_df['이름'] == sel_name].sort_values('시간', ascending=False)
                    
                    for i, row in student_records.iterrows():
                        with st.expander(f"📅 {row['시간'].strftime('%m/%d')} 기록 (다짐: {row['반성의글'][:15]}...)"):
                            st.write(f"**아이의 다짐:** {row['반성의글']}")
                            fb_text = st.text_input("피드백 입력", value=str(row['선생님피드백']), key=f"fb_{grade}_{class_sel}_{i}")
                            if st.button("피드백 저장", key=f"btn_{grade}_{class_sel}_{i}"):
                                # V열(22번째)에 저장
                                ws.update_cell(int(row['sheet_row']), 22, fb_text)
                                st.success("피드백이 시트에 저장되었습니다!")
                                st.cache_data.clear()
            except:
                st.error("해당 반의 시트 데이터를 가져올 수 없습니다.")
