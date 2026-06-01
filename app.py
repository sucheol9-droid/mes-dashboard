import streamlit as st
import plotly.express as px
import pandas as pd
import os
from data_loader import load_downtime_data, get_data_summary
from gemini_chatbot import init_gemini, build_context_message, chat_with_context, reset_chat

st.set_page_config(page_title="비가동 분석 AI 챗봇", page_icon="🏭", layout="wide")

# ==========================================
# 1. 세션 상태(Session State) 최우선 초기화
# ==========================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "context_message" not in st.session_state:
    st.session_state.context_message = ""
if "df" not in st.session_state:
    st.session_state.df = None
if "summary" not in st.session_state:
    st.session_state.summary = None

# ==========================================
# 2. API 키 로드 (배포 서버 및 로컬 key.txt 하이브리드 대응)
# ==========================================
API_KEY = None

# 만약 Streamlit 클라우드 배포 서버 환경이라면 비밀 금고(Secrets)에서 키를 가져옵니다.
if "API_KEY" in st.secrets:
    API_KEY = st.secrets["API_KEY"]
else:
    # 내 컴퓨터(로컬) 환경이라면 프로젝트 폴더의 key.txt 파일을 읽어옵니다.
    KEY_FILE_PATH = "key.txt"
    if not os.path.exists(KEY_FILE_PATH):
        with open(KEY_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("")  # 파일이 없으면 빈 파일 자동 생성

    with open(KEY_FILE_PATH, "r", encoding="utf-8") as f:
        API_KEY = f.read().strip()

# ==========================================
# 3. 메인 화면 타이틀 영역
# ==========================================
st.title("🏭 설비 비가동 분석 AI 챗봇")
st.caption("MES 비가동 데이터 기반 | Gemini 2.5 Flash")
st.divider()

# ==========================================
# 4. 사이드바 설정 영역 (파일 업로드 방식으로 변경)
# ==========================================
with st.sidebar:
    st.header("⚙️ 설정")
    
    # API 키 상태 체크
    if API_KEY and (API_KEY.startswith("AIzaSy") or API_KEY.startswith("AQ.")):
        st.success("🔑 key.txt 파일 기반 API 인증 완료")
    else:
        st.error("⚠️ API Key 입력이 필요합니다.")
        st.info(f"프로젝트 폴더에 생성된 **'{KEY_FILE_PATH}'** 파일을 열고 발급받으신 Gemini API Key를 붙여넣은 뒤 저장해 주세요.")
        
    st.markdown("---")
    st.subheader("📂 데이터 업로드")
    
    # [변경] 지정 경로 입력 대신 드래그 앤 드롭 파일 업로더 추가
    uploaded_file = st.file_uploader(
        "MES 비가동 엑셀 파일 선택", 
        type=["xlsx", "xls", "xlsm"],
        help="분석하고자 하는 MES 비가동 엑셀 파일을 여기에 끌어다 놓으세요."
    )
    
    # 파일이 업로드되었을 때만 분석 시작 버튼 활성화
    load_btn = st.button(
        "🔄 데이터 분석 시작하기", 
        use_container_width=True, 
        type="primary",
        disabled=(uploaded_file is None)
    )
    
    if st.session_state.df is not None:
        st.success(f"✅ 데이터 로드 완료\n{len(st.session_state.df):,}건")
        if st.button("🗑️ 대화 초기화", use_container_width=True):
            st.session_state.chat_history = reset_chat()
            st.rerun()

# ==========================================
# 5. 데이터 로드 로직 실행
# ==========================================
if load_btn and uploaded_file is not None:
    if not API_KEY or not (API_KEY.startswith("AIzaSy") or API_KEY.startswith("AQ.")):
        st.error("key.txt 파일에 올바른 API 키를 먼저 입력하고 저장해 주세요.")
    else:
        try:
            with st.spinner("엑셀 파일 파싱 및 AI 분석 준비 중..."):
                # [변경] 폴더 경로 대신 업로드된 파일 자체를 함수로 전달
                df = load_downtime_data(uploaded_file)
                summary = get_data_summary(df)
                
            st.session_state.df = df
            st.session_state.summary = summary
            st.session_state.context_message = build_context_message(summary)
            st.session_state.chat_history = reset_chat()
            st.success("데이터 로드 완료!")
            st.rerun()
        except Exception as e:
            st.error(f"오류 발생: {e}")

# ==========================================
# 6. 메인 대시보드 및 대화창 시각화 연출
# ==========================================
if st.session_state.df is not None:
    df = st.session_state.df
    summary = st.session_state.summary

    # 상단 핵심 지표 요약(Metrics)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📋 전체 건수", f"{summary.get('total_records', 0):,}건")
    total_min = summary.get("total_downtime_min", 0)
    col2.metric("⏱️ 총 비가동시간", f"{int(total_min // 60)}h {int(total_min % 60)}m")
    col3.metric("⚠️ 변동점 건수", f"{summary.get('change_point_count', 0)}건")
    if "period" in summary:
        col4.metric("📅 데이터 기간", summary["period"])

    st.divider()
    
    # 시각화 차트 영역 (2열 레이아웃)
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("대분류별 비가동시간")
        if "대분류" in df.columns and "비가동시간" in df.columns:
            cause_df = (df.groupby("대분류")["비가동시간"].sum()
                        .reset_index().sort_values("비가동시간", ascending=True))
            fig1 = px.bar(cause_df, x="비가동시간", y="대분류", orientation="h",
                          color="비가동시간", color_continuous_scale="Reds", text="비가동시간")
            fig1.update_traces(texttemplate="%{text:.0f}분", textposition="outside")
            fig1.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(l=0, r=40, t=20, b=0))
            st.plotly_chart(fig1, use_container_width=True)

    with chart_col2:
        st.subheader("작업장별 비가동시간")
        if "작업장명" in df.columns and "비가동시간" in df.columns:
            zone_df = (df.groupby("작업장명")["비가동시간"].sum()
                       .reset_index().sort_values("비가동시간", ascending=False).head(10))
            fig2 = px.bar(zone_df, x="작업장명", y="비가동시간", color="비가동시간", color_continuous_scale="Blues", text="비가동시간")
            fig2.update_traces(texttemplate="%{text:.0f}분", textposition="outside")
            fig2.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(l=0, r=0, t=20, b=60), xaxis_tickangle=-30)
            st.plotly_chart(fig2, use_container_width=True)

    # 하단 트렌드 차트 (일별 추이)
    if "시작일자" in df.columns and "비가동시간" in df.columns:
        st.subheader("📈 일별 비가동시간 추이")
        daily_df = (df.groupby(df["시작일자"].dt.date)["비가동시간"].sum().reset_index())
        daily_df.columns = ["날짜", "비가동시간"]
        fig3 = px.line(daily_df, x="날짜", y="비가동시간", markers=True, color_discrete_sequence=["#E74C3C"])
        fig3.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig3, use_container_width=True)

    # 원본 데이터 스크롤 테이블
    with st.expander("📄 원본 데이터 보기"):
        st.dataframe(df, use_container_width=True, height=300)

    st.divider()
    
    # AI 챗봇 대화 인터페이스 영역
    st.subheader("💬 AI 비가동 분석 챗봇")

    # 질문 추천 프리셋 버튼
    q_col1, q_col2, q_col3 = st.columns(3)
    preset_q = None
    if q_col1.button("🔍 비가동 주요 원인은?", use_container_width=True):
        preset_q = "이번 데이터에서 비가동 주요 원인을 분석하고 개선 우선순위를 알려줘"
    if q_col2.button("⚠️ 변동점 연관성 분석", use_container_width=True):
        preset_q = "변동점이 있는 건들과 비가동 패턴 사이에 연관성이 있는지 분석해줘"
    if q_col3.button("🏭 집중 점검 작업장은?", use_container_width=True):
        preset_q = "어떤 작업장을 가장 먼저 점검해야 할지 우선순위를 알려줘"

    for msg in st.session_state.chat_history:
        role = "assistant" if msg["role"] == "model" else "user"
        content = msg["parts"][0]
        if role == "user" and "[참고 데이터 요약]" in content:
            content = content.split("작업자 질문:")[-1].strip()
        with st.chat_message(role):
            st.write(content)

    user_input = st.chat_input("비가동 데이터에 대해 질문하세요...")
    final_query = preset_q or user_input

    if final_query:
        model = init_gemini(API_KEY)
        with st.chat_message("user"):
            st.write(final_query)
        with st.chat_message("assistant"):
            with st.spinner("Gemini 분석 중..."):
                reply, st.session_state.chat_history = chat_with_context(
                    model, st.session_state.chat_history,
                    final_query, st.session_state.context_message
                )
            st.write(reply)
        st.rerun()
else:
    st.info("👈 사이드바에서 분석할 MES 비가동 엑셀 파일을 업로드해 주세요.")