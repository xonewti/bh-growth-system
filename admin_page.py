import streamlit as st

def show_admin_page(sheet, selected_grade, selected_class):
    st.title("🔐 선생님 관리 페이지")
    st.write(f"현재 선택된 학급: {selected_grade}학년 {selected_class}반")
    
    st.divider()
    st.info("이곳에서 피드백 작성 및 통계 확인 기능을 구현할 예정입니다.")