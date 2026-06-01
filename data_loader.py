import os
import pandas as pd

COLUMNS = [
    "공장", "작업반", "작업반명", "작업장", "작업장명",
    "구분", "작업자", "시작일자", "비가동시간", "입력시간",
    "대분류", "소분류", "변동점유무"
]

def load_downtime_data(file_obj) -> pd.DataFrame:
    """
    [변경] 폴더 경로 대신 Streamlit의 UploadedFile 객체를 받아와 즉시 pandas로 로드합니다.
    """
    print(f"[✓] 파일 업로드 완료: {file_obj.name}")
    
    # 사용자가 시트를 별도로 지정할 필요가 없도록 첫 번째 시트(sheet_name=0)를 강제 로드
    df = pd.read_excel(file_obj, sheet_name=0, dtype=str)
    
    # 컬럼 공백 제거 및 정형화
    df.columns = [c.strip().replace(" ", "") for c in df.columns]
    
    if "시작일자" in df.columns:
        df["시작일자"] = pd.to_datetime(df["시작일자"], errors="coerce")
        
    for col in ["비가동시간", "입력시간"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
    if "변동점유무" in df.columns:
        df["변동점유무"] = df["변동점유무"].str.strip().map(
            {"Y": True, "N": False, "y": True, "n": False,
             "있음": True, "없음": False, "유": True, "무": False}
        )
    return df


def get_data_summary(df: pd.DataFrame) -> dict:
    summary = {}
    if "시작일자" in df.columns and not df['시작일자'].dropna().empty:
        summary["period"] = f"{df['시작일자'].min().date()} ~ {df['시작일자'].max().date()}"
    
    summary["total_records"] = len(df)
    
    if "비가동시간" in df.columns:
        summary["total_downtime_min"] = round(df["비가동시간"].sum(), 1)
        
    if {"대분류", "비가동시간"}.issubset(df.columns):
        top_cause = (df.groupby("대분류")["비가동시간"].sum()
                     .sort_values(ascending=False).head(3))
        summary["top_cause"] = top_cause.to_dict()
        
    if {"작업장명", "비가동시간"}.issubset(df.columns):
        top_zone = (df.groupby("작업장명")["비가동시간"].sum()
                    .sort_values(ascending=False).head(3))
        summary["top_workzone"] = top_zone.to_dict()
        
    if "변동점유무" in df.columns:
        summary["change_point_count"] = int(df["변동점유무"].sum())
        
    cols_to_show = [c for c in ["시작일자", "작업장명", "대분류", "소분류", "비가동시간", "변동점유무"] if c in df.columns]
    summary["recent_records"] = df[cols_to_show].tail(10).to_dict("records")
    return summary