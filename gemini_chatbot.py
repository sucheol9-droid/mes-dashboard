from google import genai
from google.genai import types

SYSTEM_PROMPT = """
당신은 자동차 부품 제조 공장의 설비 비가동(다운타임) 전문 분석 AI입니다.
MES에서 추출한 비가동 데이터를 바탕으로 현장 관리자와 작업자를 지원합니다.

[데이터 구조]
- 공장 / 작업반 / 작업반명 / 작업장 / 작업장명
- 구분 / 작업자 / 시작일자 / 비가동시간 (분 단위) / 입력시간 / 대분류 / 소분류 / 변동점유무

[역할]
1. 비가동 원인 분석 및 개선 우선순위 제안
2. 반복 패턴 및 이상 징후 식별
3. 변동점 발생 구간과 비가동 상관관계 분석
4. 작업장/작업반별 취약 포인트 파악
5. 현장에서 바로 적용 가능한 조치 사항 권고

[답변 원칙]
- 항상 한국어로 답변합니다.
- 데이터 수치가 주어지면 명확히 인용하여 근거로 삼으십시오.
- 추정이나 가능성은 반드시 "추정됩니다" / "가능성이 있습니다"로 명확히 표현합니다.
- 현장 작업자도 즉시 이해할 수 있도록 구조화하여 쉽고 명확하게 설명합니다.
- 모르는 내용은 "현재 요약 데이터만으로는 판단이 어렵습니다"라고 솔직하게 답합니다.
"""


def init_gemini(api_key: str):
    return genai.Client(api_key=api_key)


def build_context_message(summary: dict) -> str:
    lines = ["[현재 비가동 데이터 요약 보고]"]
    if "period" in summary: 
        lines.append(f"- 데이터 기간      : {summary['period']}")
    if "total_records" in summary: 
        lines.append(f"- 전체 비가동 건수 : {summary['total_records']:,}건")
    if "total_downtime_min" in summary:
        total = summary["total_downtime_min"]
        lines.append(f"- 총 비가동시간    : {total:,.1f}분 ({int(total // 60)}시간 {int(total % 60)}분)")
    if "change_point_count" in summary: 
        lines.append(f"- 변동점 발생 건수 : {summary['change_point_count']}건")
        
    if "top_cause" in summary:
        lines.append("\n[대분류별 비가동시간 Top 3]")
        for rank, (cause, minutes) in enumerate(summary["top_cause"].items(), 1):
            lines.append(f"  {rank}위. {cause} : {minutes:,.1f}분")
            
    if "top_workzone" in summary:
        lines.append("\n[작업장별 비가동시간 Top 3]")
        for rank, (zone, minutes) in enumerate(summary["top_workzone"].items(), 1):
            lines.append(f"  {rank}위. {zone} : {minutes:,.1f}분")
    return "\n".join(lines)


def chat_with_context(client, history: list, user_input: str, context_message: str):
    if len(history) == 0:
        full_input = f"[참고 데이터 요약]\n{context_message}\n\n작업자 질문: {user_input}"
    else:
        full_input = user_input

    history.append({"role": "user", "parts": [full_input]})
    contents = [types.Content(role=msg["role"], parts=[types.Part(text=msg["parts"][0])]) for msg in history]

    # 구글 서버에서 제공하는 최신 안정화 모델인 gemini-2.5-flash를 호출합니다.
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.15
        )
    )
    reply = response.text
    history.append({"role": "model", "parts": [reply]})
    return reply, history


def reset_chat() -> list:
    return []