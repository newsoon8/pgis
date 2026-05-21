import math
import random
import string
from datetime import datetime, timedelta

import pandas as pd
import pydeck as pdk
import streamlit as st


st.set_page_config(
    page_title="P·GIS 재난 조기경보 지도",
    page_icon="P·GIS",
    layout="wide",
    initial_sidebar_state="expanded",
)


HAZARD_META = {
    "flood": {"label": "침수/홍수", "color": "#4a6b8f", "rgb": [74, 107, 143]},
    "fire": {"label": "산불/화재", "color": "#e87456", "rgb": [232, 116, 86]},
    "quake": {"label": "지진", "color": "#e0b85c", "rgb": [224, 184, 92]},
    "storm": {"label": "태풍/강풍", "color": "#7d8f5c", "rgb": [125, 143, 92]},
    "landslide": {"label": "산사태", "color": "#8a6b3f", "rgb": [138, 107, 63]},
}

KNOWLEDGE_CATEGORY = {
    "animal": "동물 행동 지표",
    "plant": "식물·환경 지표",
    "weather": "기상 지표",
    "celestial": "천체·구름 지표",
    "place_memory": "장소 기억",
}

REPORTS = [
    {"id": "r001", "type": "report", "hazard": "flood", "severity": 5, "lng": 127.0276, "lat": 37.4979, "occurred_at": "2025-08-08T22:30:00", "place": "강남역 일대", "reporter": "익명-7A2", "narrative": "강남대로 차도가 무릎까지 잠겼고, 인근 반지하 상가가 침수되어 영업 중단. 배수가 거의 안 되는 상태.", "source": "citizen"},
    {"id": "r002", "type": "report", "hazard": "flood", "severity": 4, "lng": 127.0316, "lat": 37.4988, "occurred_at": "2025-08-08T23:15:00", "place": "역삼동 골목", "reporter": "익명-9B1", "narrative": "지대가 낮아 매년 같은 자리에서 침수. 어르신들은 이 골목을 \"물웅덩이 길\"이라 부른다.", "source": "citizen"},
    {"id": "r003", "type": "report", "hazard": "flood", "severity": 3, "lng": 127.0246, "lat": 37.4946, "occurred_at": "2025-09-12T18:20:00", "place": "서초구 우면동", "reporter": "익명-3C4", "narrative": "소하천 범람으로 인근 도로 일부 통제. 둑이 약해 매년 반복되는 구간.", "source": "citizen"},
    {"id": "r004", "type": "report", "hazard": "landslide", "severity": 4, "lng": 126.9520, "lat": 37.4670, "occurred_at": "2025-07-22T03:45:00", "place": "관악산 자락 신림동", "reporter": "익명-5D9", "narrative": "폭우 후 사면 일부가 무너져 진입로가 막힘. 옆 집 어르신 말씀으로는 1972년에도 비슷한 일이 있었다고 함.", "source": "citizen"},
    {"id": "r005", "type": "report", "hazard": "storm", "severity": 5, "lng": 129.1604, "lat": 35.1635, "occurred_at": "2025-09-05T05:00:00", "place": "해운대 마린시티", "reporter": "익명-2E7", "narrative": "태풍 직격으로 해안가 1층 침수. 방파제 너머로 파도가 넘어왔음. 사진 첨부.", "source": "citizen"},
    {"id": "r006", "type": "report", "hazard": "storm", "severity": 3, "lng": 129.0756, "lat": 35.1796, "occurred_at": "2025-09-05T07:20:00", "place": "부산 동래구", "reporter": "익명-8F3", "narrative": "강풍에 옥상 구조물 일부 파손. 인근 전봇대 흔들림 심각.", "source": "citizen"},
    {"id": "r007", "type": "report", "hazard": "fire", "severity": 5, "lng": 129.1145, "lat": 37.5247, "occurred_at": "2025-04-11T14:30:00", "place": "동해시 망상동", "reporter": "익명-1G8", "narrative": "건조한 봄철, 산림 인접지에서 발화. 강한 양간지풍으로 빠르게 확산. 마을 주민 일부 대피.", "source": "citizen"},
    {"id": "r008", "type": "report", "hazard": "fire", "severity": 4, "lng": 128.5912, "lat": 38.2070, "occurred_at": "2025-03-28T11:00:00", "place": "강원 고성", "reporter": "익명-4H6", "narrative": "낙엽 누적으로 진화 어려움. 헬기 진입 위치도 확인 필요.", "source": "citizen"},
    {"id": "r009", "type": "report", "hazard": "flood", "severity": 3, "lng": 127.9261, "lat": 36.9910, "occurred_at": "2025-07-15T09:30:00", "place": "충주시 살미면", "reporter": "익명-6J2", "narrative": "농경지 침수. 마을회관 주변 물 빠짐 늦어 어르신 이동 어려움.", "source": "citizen"},
    {"id": "r010", "type": "report", "hazard": "flood", "severity": 5, "lng": 127.4625, "lat": 35.2024, "occurred_at": "2025-08-08T03:00:00", "place": "구례군 토지면", "reporter": "익명-0K5", "narrative": "섬진강 수위 급상승. 5년 전 그 자리에 다시 물이 찼다. 2020년 사진과 거의 일치.", "source": "citizen"},
    {"id": "r011", "type": "report", "hazard": "quake", "severity": 2, "lng": 126.6291, "lat": 37.4563, "occurred_at": "2025-06-19T22:14:00", "place": "인천 옹진군 일대", "reporter": "익명-2L9", "narrative": "체감 진동. 책장 흔들림. 기상청 발표 전 SNS 먼저 확인.", "source": "citizen"},
    {"id": "r012", "type": "report", "hazard": "flood", "severity": 2, "lng": 126.9784, "lat": 37.5665, "occurred_at": "2025-08-09T10:00:00", "place": "서울 중구", "reporter": "익명-7M1", "narrative": "청계천 인근 침수, 빠르게 회복됨.", "source": "citizen"},
    {"id": "r013", "type": "report", "hazard": "storm", "severity": 2, "lng": 126.4407, "lat": 33.4996, "occurred_at": "2025-09-15T04:00:00", "place": "제주 한림읍", "reporter": "익명-3N4", "narrative": "바닷가 어선 일부 손상. 어르신들은 바람 방향으로 다음날 날씨 예측.", "source": "citizen"},
    {"id": "r014", "type": "report", "hazard": "fire", "severity": 3, "lng": 128.6014, "lat": 35.8714, "occurred_at": "2025-04-02T16:00:00", "place": "경북 안동", "reporter": "익명-5P7", "narrative": "논두렁 태우다 산림으로 번질 뻔. 마을 자율방재단 조기 진압.", "source": "citizen"},
    {"id": "r015", "type": "report", "hazard": "landslide", "severity": 3, "lng": 127.7297, "lat": 38.0480, "occurred_at": "2025-07-23T05:30:00", "place": "강원 인제", "reporter": "익명-8Q3", "narrative": "집중호우로 비탈면 일부 유실. 인근 도로 우회 필요.", "source": "citizen"},
]

KNOWLEDGE = [
    {"id": "k001", "type": "knowledge", "category": "animal", "lng": 127.0246, "lat": 37.4946, "indicator": "개미떼의 높은 곳 이동", "description": "큰비가 오기 하루이틀 전, 개미들이 줄지어 둑 위쪽이나 담장 위로 이동하면 곧 폭우가 온다. 우면산 자락 어른들이 자주 보는 신호.", "source_year": 1985, "elder": "김○○ (1942년생)"},
    {"id": "k002", "type": "knowledge", "category": "animal", "lng": 127.4625, "lat": 35.2024, "indicator": "두꺼비의 산 위 이동", "description": "섬진강 인근, 두꺼비들이 강에서 산 위쪽으로 거꾸로 올라가면 며칠 안에 큰물이 진다.", "source_year": 1972, "elder": "박○○ (1938년생)"},
    {"id": "k003", "type": "knowledge", "category": "plant", "lng": 128.5912, "lat": 38.2070, "indicator": "소나무 잎 변색", "description": "봄철 산불 직전, 양지바른 곳 소나무 잎 끝이 유난히 빨리 마르고 떨어지면 발화 위험. 양간지풍이 부는 시기와 겹친다.", "source_year": 1996, "elder": "최○○ (1945년생)"},
    {"id": "k004", "type": "knowledge", "category": "plant", "lng": 127.9261, "lat": 36.9910, "indicator": "미꾸리꽝 색 변화", "description": "논 미꾸리꽝(이끼)이 평소보다 진하게 자라면 그 해 장마가 길다. 충주 살미면 노인들의 오랜 경험.", "elder": "정○○ (1936년생)"},
    {"id": "k005", "type": "knowledge", "category": "weather", "lng": 129.1604, "lat": 35.1635, "indicator": "동풍 + 붉은 노을", "description": "해운대 어부들 사이에서 동풍이 강해지고 일몰이 유난히 붉으면 다음날 큰바람(태풍)이 든다.", "elder": "이○○ (1940년생)"},
    {"id": "k006", "type": "knowledge", "category": "celestial", "lng": 126.4407, "lat": 33.4996, "indicator": "한라산 정상의 갓모자 구름", "description": "한라산 정상에 모자 모양 구름이 걸리면 24~48시간 내 강한 비바람. 제주 어선들이 출항 결정에 참고.", "elder": "강○○ (1944년생)"},
    {"id": "k007", "type": "knowledge", "category": "place_memory", "lng": 127.0316, "lat": 37.4988, "indicator": "1959 사라호 침수선", "description": "역삼동 옛 골목, 사라호 때 어른 키 높이까지 물이 찼다는 구전. 지금도 같은 위치 침수 반복.", "source_year": 1959, "elder": "서○○ (1932년생, 작고)"},
    {"id": "k008", "type": "knowledge", "category": "place_memory", "lng": 126.9520, "lat": 37.4670, "indicator": "1972 관악 산사태 지점", "description": "신림동 산자락, 1972년 8월 큰 산사태로 다섯 채가 묻혔던 자리. 지금도 같은 사면이 불안정.", "source_year": 1972, "elder": "구술 채록 (2024)"},
    {"id": "k009", "type": "knowledge", "category": "place_memory", "lng": 128.6014, "lat": 35.8714, "indicator": "안동 논두렁 화재 다발지", "description": "봄철 논두렁 태우기 풍습 지역. 1980년대 이후 산불 비화 사례 5건 이상 누적.", "source_year": 1987, "elder": "문중 기록"},
]

HOTSPOTS = [
    {"id": "h001", "name": "강남역-역삼 침수 클러스터", "lng": 127.0296, "lat": 37.4983, "intensity": 0.92, "hazard": "flood", "reportCount": 14, "method": "Getis-Ord Gi*"},
    {"id": "h002", "name": "관악 산사태 위험 사면", "lng": 126.9520, "lat": 37.4670, "intensity": 0.78, "hazard": "landslide", "reportCount": 6, "method": "DBSCAN"},
    {"id": "h003", "name": "해운대 해안 폭풍 노출구간", "lng": 129.1604, "lat": 35.1635, "intensity": 0.84, "hazard": "storm", "reportCount": 9, "method": "Getis-Ord Gi*"},
    {"id": "h004", "name": "동해안 산불 회랑", "lng": 128.8530, "lat": 37.8660, "intensity": 0.71, "hazard": "fire", "reportCount": 11, "method": "KDE"},
    {"id": "h005", "name": "섬진강 본류 범람구간", "lng": 127.4625, "lat": 35.2024, "intensity": 0.88, "hazard": "flood", "reportCount": 7, "method": "Getis-Ord Gi*"},
]

HISTORICAL_MAPS = [
    {"id": "hm001", "title": "대동여지도 한양 부근 (1861)", "year": 1861, "source": "서울대학교 규장각", "bbox": [126.85, 37.45, 127.10, 37.65], "description": "김정호의 대동여지도 중 한양 일대. 청계천·한강 본류와 산세 표현이 명확하여 현재 침수 지역과의 비교 가능."},
    {"id": "hm002", "title": "구례 섬진강 옛 지도 (1918)", "year": 1918, "source": "국가기록원", "bbox": [127.40, 35.15, 127.55, 35.27], "description": "일제강점기 지적원도. 섬진강 본류 사행과 옛 마을 위치 확인. 100여 년 전 범람 구간이 현재 보고와 거의 일치."},
    {"id": "hm003", "title": "관악산 산림지도 (1925)", "year": 1925, "source": "국립중앙도서관", "bbox": [126.92, 37.45, 126.99, 37.49], "description": "관악산 사면별 식생과 토양 정보를 담은 일제강점기 임상도. 1972년 산사태 지점과 식생 변화 비교 가능."},
]

PRESET_POINTS = {
    "강남역 일대": (127.0276, 37.4979),
    "서초구 우면동": (127.0246, 37.4946),
    "관악산 자락 신림동": (126.9520, 37.4670),
    "해운대 마린시티": (129.1604, 35.1635),
    "구례군 토지면": (127.4625, 35.2024),
    "제주 한림읍": (126.4407, 33.4996),
}


THEME_LABELS = {
    "light": "Light",
    "dark": "Dark",
}


def theme_tokens(theme):
    if theme == "dark":
        return {
            "bg": "#0a0d11",
            "app_bg": "#0a0d11",
            "header_bg": "rgba(10,13,17,.8)",
            "sidebar_bg": "#0e141b",
            "surface": "#111820",
            "surface_2": "#151d26",
            "surface_strong": "#101720",
            "surface_alpha": "rgba(17,24,32,.75)",
            "panel_gradient": "linear-gradient(180deg, rgba(21,29,38,.98), rgba(14,20,27,.98))",
            "border": "#29323d",
            "paper": "#f4ecd8",
            "text": "#d8d1c2",
            "text_dim": "#978f80",
            "text_faint": "#6f6a60",
            "vermillion": "#c8472a",
            "vermillion_soft": "#e87456",
            "ochre": "#c89b3f",
            "ochre_soft": "#e0b85c",
            "header_accent": "linear-gradient(135deg, rgba(200,71,42,.34), rgba(200,155,63,.18) 46%, rgba(74,107,143,.18))",
        }
    return {
        "bg": "#f7f3ea",
        "app_bg": "#f7f3ea",
        "header_bg": "rgba(247,243,234,.88)",
        "sidebar_bg": "#efe7d7",
        "surface": "#fffaf0",
        "surface_2": "#f2eadb",
        "surface_strong": "#fff8eb",
        "surface_alpha": "rgba(255,250,240,.86)",
        "panel_gradient": "linear-gradient(180deg, rgba(255,250,240,.98), rgba(239,231,215,.98))",
        "border": "#d4c7ad",
        "paper": "#211c16",
        "text": "#2d2922",
        "text_dim": "#6f6657",
        "text_faint": "#8b806e",
        "vermillion": "#b43b23",
        "vermillion_soft": "#d45a3b",
        "ochre": "#a7781f",
        "ochre_soft": "#bd8b2d",
        "header_accent": "linear-gradient(135deg, rgba(212,90,59,.22), rgba(189,139,45,.18) 48%, rgba(74,107,143,.14))",
    }


def inject_css(theme):
    tokens = theme_tokens(theme)
    css_vars = f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
        :root {{
          --bg:{tokens["bg"]}; --surface:{tokens["surface"]}; --surface-2:{tokens["surface_2"]}; --border:{tokens["border"]};
          --paper:{tokens["paper"]}; --text:{tokens["text"]}; --text-dim:{tokens["text_dim"]}; --text-faint:{tokens["text_faint"]};
          --vermillion:{tokens["vermillion"]}; --vermillion-soft:{tokens["vermillion_soft"]}; --ochre:{tokens["ochre"]}; --ochre-soft:{tokens["ochre_soft"]};
          --surface-alpha:{tokens["surface_alpha"]}; --surface-strong:{tokens["surface_strong"]}; --panel-gradient:{tokens["panel_gradient"]};
          --header-bg:{tokens["header_bg"]}; --sidebar-bg:{tokens["sidebar_bg"]}; --header-accent:{tokens["header_accent"]};
        }}
        """
    css_rules = """
        html, body, [data-testid="stAppViewContainer"] { background: var(--bg); color: var(--text); font-family: 'Noto Sans KR', sans-serif; }
        [data-testid="stHeader"] { background: transparent; height: 0; }
        [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
          visibility:hidden; height:0; position:fixed;
        }
        [data-testid="stSidebar"] { background: var(--sidebar-bg); border-right: 1px solid var(--border); }
        [data-testid="stSidebar"] * { color: var(--text); }
        .block-container { padding: .45rem 1.2rem 2rem; max-width: 100%; }
        .brandbar {
          display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;
          border:1px solid var(--border); border-left:0; border-right:0; padding:16px 18px 17px; margin-bottom:14px;
          background:var(--header-accent);
          box-shadow: inset 0 1px 0 rgba(255,255,255,.16), 0 10px 26px rgba(0,0,0,.08);
        }
        .brand-lockup { display:flex; align-items:baseline; gap:14px; flex-wrap:wrap; }
        .brand { color:var(--paper); font-size:22px; font-weight:900; letter-spacing:.04em; line-height:1; }
        .vermillion { color:var(--vermillion-soft); }
        .subtitle { color:var(--paper); font-size:34px; font-weight:900; line-height:1; letter-spacing:0; }
        .header-stats { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
        .header-stat {
          min-width:92px; padding:7px 10px; border:1px solid var(--border); background:var(--surface-alpha);
        }
        .header-stat span { display:block; color:var(--text-faint); font-size:10px; letter-spacing:.08em; }
        .header-stat strong { color:var(--paper); font-size:16px; line-height:1.2; }
        .section-label { display:flex; gap:9px; align-items:baseline; margin:8px 0 10px; }
        .section-label-num { color:var(--vermillion-soft); font-size:10px; letter-spacing:.12em; font-weight:800; }
        .section-label-text { color:var(--paper); font-size:15px; font-weight:800; }
        .section-desc { color:var(--text-dim); font-size:12px; line-height:1.65; margin-bottom:12px; }
        .cartouche {
          padding:14px 16px; background:var(--surface-alpha); border:1px solid var(--border);
          border-left:3px solid var(--vermillion-soft); margin-bottom:10px;
        }
        .cartouche-eyebrow { color:var(--vermillion-soft); font-size:10px; letter-spacing:.14em; font-weight:800; }
        .cartouche-title { color:var(--paper); font-size:24px; font-weight:900; margin-top:4px; }
        .cartouche-meta { color:var(--text-dim); font-size:11px; margin-top:4px; }
        .metric-card, .panel-card {
          border:1px solid var(--border); background:var(--panel-gradient);
          padding:13px; border-radius:3px;
        }
        .metric-label { color:var(--text-faint); font-size:10px; letter-spacing:.08em; }
        .metric-value { color:var(--paper); font-size:28px; font-weight:900; line-height:1.1; }
        .metric-trend { color:var(--ochre-soft); font-size:11px; }
        .legend-row {
          display:flex; align-items:center; justify-content:space-between; gap:8px;
          border:1px solid var(--border); padding:8px 9px; margin-bottom:6px; background:var(--surface-alpha);
          font-size:12px;
        }
        .swatch { width:12px; height:12px; display:inline-block; border-radius:2px; margin-right:6px; box-shadow:0 0 10px rgba(255,255,255,.08); }
        .count { color:var(--text-faint); font-family:monospace; }
        .report-card {
          border:1px solid var(--border); background:var(--surface-strong); padding:11px; border-left:3px solid var(--vermillion-soft);
          margin-bottom:8px; border-radius:3px;
        }
        .report-head { display:flex; justify-content:space-between; gap:8px; align-items:center; margin-bottom:7px; }
        .badge {
          display:inline-flex; align-items:center; padding:3px 7px; border:1px solid var(--border); border-radius:999px;
          font-size:10px; font-weight:800; letter-spacing:.03em;
        }
        .report-time { color:var(--text-faint); font-size:10px; font-family:monospace; }
        .report-text { color:var(--text); font-size:12px; line-height:1.55; }
        .report-foot { display:flex; justify-content:space-between; color:var(--text-faint); font-size:10px; margin-top:8px; }
        .stButton > button, .stDownloadButton > button {
          background:var(--surface-2); color:var(--paper); border:1px solid var(--border); border-radius:3px; font-weight:800;
        }
        .stButton > button:hover { border-color:var(--vermillion-soft); color:var(--vermillion-soft); }
        div[data-baseweb="tab-list"] button { color:var(--text-dim); }
        div[data-baseweb="tab-list"] button[aria-selected="true"] { color:var(--vermillion-soft); }
        .stSlider [data-baseweb="slider"] div { color: var(--vermillion-soft); }
        .map-note { color:var(--text-faint); font-size:11px; margin-top:-4px; margin-bottom:8px; }
        @media (max-width: 720px) {
          .brandbar { padding:14px 12px; }
          .brand { font-size:18px; }
          .subtitle { font-size:28px; }
          .header-stat { min-width:82px; }
        }
        </style>
        """
    st.markdown(
        css_vars + css_rules,
        unsafe_allow_html=True,
    )


def uid(prefix):
    return f"{prefix}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"


def parse_time(iso):
    return datetime.fromisoformat(iso)


def format_relative_time(iso):
    diff = datetime.now() - parse_time(iso)
    if diff < timedelta(minutes=1):
        return "방금"
    if diff < timedelta(hours=1):
        return f"{int(diff.total_seconds() // 60)}분 전"
    if diff < timedelta(days=1):
        return f"{int(diff.total_seconds() // 3600)}시간 전"
    if diff < timedelta(days=7):
        return f"{diff.days}일 전"
    if diff < timedelta(days=30):
        return f"{diff.days // 7}주 전"
    if diff < timedelta(days=365):
        return f"{diff.days // 30}개월 전"
    return f"{diff.days // 365}년 전"


def approx_region(lng, lat):
    if 37.4 < lat < 37.7 and 126.8 < lng < 127.2:
        return "서울"
    if 35.0 < lat < 35.3 and 128.9 < lng < 129.3:
        return "부산"
    if 37.4 < lat < 37.6 and 126.5 < lng < 126.8:
        return "인천"
    if 37.4 < lat < 38.4 and 128.0 < lng < 129.4:
        return "강원"
    if 36.8 < lat < 37.1 and 127.8 < lng < 128.1:
        return "충북"
    if 35.0 < lat < 35.4 and 127.3 < lng < 127.7:
        return "전남"
    if 33.2 < lat < 33.6 and 126.2 < lng < 126.7:
        return "제주"
    if 35.7 < lat < 36.0 and 128.5 < lng < 128.8:
        return "경북"
    return "기타"


def init_state():
    defaults = {
        "user_reports": [],
        "user_knowledge": [],
        "perceptions": [],
        "user_drawings": [],
        "picked_lng": 127.7,
        "picked_lat": 36.5,
        "focus_lng": 127.7,
        "focus_lat": 36.5,
        "zoom": 6.4,
        "theme": "light",
        "layers": {
            "reports": True,
            "knowledge": True,
            "heatmap": True,
            "hotspots": True,
            "historical": False,
            "userDrawings": True,
        },
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def report_df(reports):
    df = pd.DataFrame(reports)
    if df.empty:
        return df
    df["label"] = df["hazard"].map(lambda h: HAZARD_META[h]["label"])
    df["color"] = df["hazard"].map(lambda h: HAZARD_META[h]["rgb"] + [235])
    df["radius"] = df["severity"].map(lambda s: 4500 + s * 2400)
    df["tooltip"] = df.apply(lambda r: f"{r['place']} | {HAZARD_META[r['hazard']]['label']} | 심각도 {r['severity']}/5", axis=1)
    return df


def knowledge_df(items):
    df = pd.DataFrame(items)
    if df.empty:
        return df
    palette = {
        "animal": [125, 143, 92, 230],
        "plant": [90, 107, 61, 230],
        "weather": [74, 107, 143, 230],
        "celestial": [224, 184, 92, 230],
        "place_memory": [200, 155, 63, 230],
    }
    df["color"] = df["category"].map(palette)
    df["radius"] = 7500
    df["tooltip"] = df.apply(lambda r: f"{r['indicator']} | {KNOWLEDGE_CATEGORY[r['category']]}", axis=1)
    return df


def hotspot_df(hotspots):
    df = pd.DataFrame(hotspots)
    if df.empty:
        return df
    df["radius"] = df["intensity"].map(lambda v: 18000 + v * 34000)
    df["ring"] = df["intensity"].map(lambda v: [232, 116, 86, int(80 + v * 90)])
    df["fill"] = df["intensity"].map(lambda v: [200, 71, 42, int(35 + v * 45)])
    df["tooltip"] = df.apply(lambda r: f"{r['name']} | {HAZARD_META[r['hazard']]['label']} | {r['method']}", axis=1)
    return df


def historical_polygons():
    rows = []
    for item in HISTORICAL_MAPS:
        w, s, e, n = item["bbox"]
        rows.append(
            {
                **item,
                "polygon": [[w, s], [e, s], [e, n], [w, n], [w, s]],
                "color": [200, 155, 63, 40],
                "line_color": [224, 184, 92, 180],
                "tooltip": f"{item['title']} | {item['source']}",
            }
        )
    return pd.DataFrame(rows)


def drawing_rows():
    rows = []
    for drawing in st.session_state.user_drawings:
        coords = drawing["coords"]
        if drawing["kind"] == "polygon" and len(coords) >= 3:
            rows.append({"kind": "polygon", "polygon": coords + [coords[0]], "color": [200, 71, 42, 55], "tooltip": drawing["label"]})
        elif drawing["kind"] == "line" and len(coords) >= 2:
            rows.append({"kind": "line", "path": coords, "color": [232, 116, 86, 230], "tooltip": drawing["label"]})
    return pd.DataFrame(rows)


def make_deck(filtered_reports, filtered_knowledge, filtered_hotspots):
    layers = []
    is_dark = st.session_state.theme == "dark"
    map_style = (
        "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
        if is_dark
        else "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
    )
    tooltip_bg = "#101720" if is_dark else "#fff8eb"
    tooltip_fg = "#f4ecd8" if is_dark else "#211c16"

    if st.session_state.layers["heatmap"] and filtered_reports:
        layers.append(
            pdk.Layer(
                "HeatmapLayer",
                report_df(filtered_reports),
                get_position="[lng, lat]",
                get_weight="severity",
                radius_pixels=55,
                opacity=0.55,
            )
        )

    if st.session_state.layers["historical"]:
        hist = historical_polygons()
        layers.append(
            pdk.Layer(
                "PolygonLayer",
                hist,
                get_polygon="polygon",
                get_fill_color="color",
                get_line_color="line_color",
                line_width_min_pixels=1,
                pickable=True,
                stroked=True,
                filled=True,
            )
        )

    if st.session_state.layers["hotspots"] and filtered_hotspots:
        hot = hotspot_df(filtered_hotspots)
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                hot,
                get_position="[lng, lat]",
                get_radius="radius",
                get_fill_color="fill",
                get_line_color="ring",
                line_width_min_pixels=2,
                pickable=True,
                stroked=True,
                filled=True,
            )
        )

    drawings = drawing_rows()
    if st.session_state.layers["userDrawings"] and not drawings.empty:
        polygons = drawings[drawings["kind"] == "polygon"]
        lines = drawings[drawings["kind"] == "line"]
        if not polygons.empty:
            layers.append(
                pdk.Layer(
                    "PolygonLayer",
                    polygons,
                    get_polygon="polygon",
                    get_fill_color="color",
                    get_line_color=[232, 116, 86, 230],
                    line_width_min_pixels=2,
                    pickable=True,
                    stroked=True,
                    filled=True,
                )
            )
        if not lines.empty:
            layers.append(
                pdk.Layer(
                    "PathLayer",
                    lines,
                    get_path="path",
                    get_color="color",
                    width_min_pixels=3,
                    pickable=True,
                )
            )

    if st.session_state.layers["knowledge"] and filtered_knowledge:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                knowledge_df(filtered_knowledge),
                get_position="[lng, lat]",
                get_radius="radius",
                get_fill_color="color",
                get_line_color=[244, 236, 216, 220],
                line_width_min_pixels=1,
                pickable=True,
                stroked=True,
                filled=True,
            )
        )

    if st.session_state.layers["reports"] and filtered_reports:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                report_df(filtered_reports),
                get_position="[lng, lat]",
                get_radius="radius",
                get_fill_color="color",
                get_line_color=[244, 236, 216, 220],
                line_width_min_pixels=1,
                pickable=True,
                stroked=True,
                filled=True,
            )
        )

    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            pd.DataFrame([{"lng": st.session_state.picked_lng, "lat": st.session_state.picked_lat, "color": [244, 236, 216, 245]}]),
            get_position="[lng, lat]",
            get_radius=6000,
            get_fill_color="color",
            get_line_color=[232, 116, 86, 255],
            line_width_min_pixels=2,
            stroked=True,
        )
    )

    return pdk.Deck(
        map_style=map_style,
        initial_view_state=pdk.ViewState(
            latitude=st.session_state.focus_lat,
            longitude=st.session_state.focus_lng,
            zoom=st.session_state.zoom,
            pitch=0,
        ),
        layers=layers,
        tooltip={"html": "<b>{tooltip}</b>", "style": {"backgroundColor": tooltip_bg, "color": tooltip_fg}},
    )


def header(total_reports):
    st.markdown(
        f"""
        <div class="brandbar">
          <div class="brand-lockup">
            <span class="brand">P<span class="vermillion">·</span>GIS</span>
            <span class="subtitle">재난 조기경보 지도</span>
          </div>
          <div class="header-stats">
            <div class="header-stat"><span>누적 제보</span><strong>{total_reports:,}</strong></div>
            <div class="header-stat"><span>전통지식</span><strong>{len(KNOWLEDGE) + len(st.session_state.user_knowledge)}</strong></div>
            <div class="header-stat"><span>핫스팟</span><strong>{len(HOTSPOTS)}</strong></div>
            <div class="header-stat"><span>참여 지역</span><strong>8개 시·도</strong></div>
            <div class="header-stat"><span>플랫폼</span><strong style="color:var(--vermillion-soft)">MVP v1.0</strong></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def coordinate_picker():
    st.markdown('<div class="section-label"><span class="section-label-num">LOCATION</span><span class="section-label-text">좌표 선택</span></div>', unsafe_allow_html=True)
    preset = st.selectbox("빠른 위치 선택", ["직접 입력"] + list(PRESET_POINTS.keys()), label_visibility="collapsed")
    if preset != "직접 입력":
        st.session_state.picked_lng, st.session_state.picked_lat = PRESET_POINTS[preset]
        st.session_state.focus_lng, st.session_state.focus_lat = PRESET_POINTS[preset]
        st.session_state.zoom = 11.5
    lng, lat = st.columns(2)
    with lng:
        st.session_state.picked_lng = st.number_input("경도", 124.0, 132.0, float(st.session_state.picked_lng), 0.0001, format="%.4f")
    with lat:
        st.session_state.picked_lat = st.number_input("위도", 32.0, 39.5, float(st.session_state.picked_lat), 0.0001, format="%.4f")
    if st.button("핀 위치로 지도 이동", use_container_width=True):
        st.session_state.focus_lng = st.session_state.picked_lng
        st.session_state.focus_lat = st.session_state.picked_lat
        st.session_state.zoom = 12
        st.toast("위치가 지정되었습니다.", icon="✓")


def collection_panel():
    st.radio(
        "화면 모드",
        options=list(THEME_LABELS),
        format_func=lambda value: THEME_LABELS[value],
        key="theme",
        horizontal=True,
    )
    with st.expander("시민지식 수집", expanded=False):
        st.markdown('<div class="section-label"><span class="section-label-num">LAYER 01</span><span class="section-label-text">시민지식 수집</span></div>', unsafe_allow_html=True)
        st.markdown('<p class="section-desc">재해 경험·위험인식·지역 전통지식을 직접 제보하세요. 모든 자료는 시민과학 데이터로 통합됩니다.</p>', unsafe_allow_html=True)
        coordinate_picker()
        tab_report, tab_perception, tab_knowledge = st.tabs(["재해 제보", "위험 인식", "전통 지식"])

        with tab_report:
            with st.form("report_form"):
                hazard = st.selectbox("재해 유형", list(HAZARD_META), format_func=lambda h: HAZARD_META[h]["label"])
                severity = st.radio("피해 정도 (1-5)", [1, 2, 3, 4, 5], index=2, horizontal=True)
                place = st.text_input("장소명 (선택)", placeholder="예: 우면동 산자락 입구")
                narrative = st.text_area("상황 서술", placeholder="언제, 어떻게, 어디까지 피해가 미쳤는지 기록해 주세요.")
                submitted = st.form_submit_button("제보 등록", use_container_width=True)
            if submitted:
                if not narrative.strip():
                    st.warning("상황 서술을 입력해 주세요.")
                else:
                    st.session_state.user_reports.insert(
                        0,
                        {
                            "id": uid("R"),
                            "type": "report",
                            "hazard": hazard,
                            "severity": severity,
                            "lng": st.session_state.picked_lng,
                            "lat": st.session_state.picked_lat,
                            "occurred_at": datetime.now().replace(microsecond=0).isoformat(),
                            "place": place.strip() or "직접 입력",
                            "reporter": f"익명-{uid('')[1:4]}",
                            "narrative": narrative.strip(),
                            "source": "citizen",
                        },
                    )
                    st.toast("재해 제보가 등록되었습니다.", icon="✓")
                    st.rerun()

        with tab_perception:
            with st.form("perception_form"):
                p_hazard = st.selectbox("대상 재해", list(HAZARD_META), format_func=lambda h: HAZARD_META[h]["label"], key="p_hazard")
                score = st.slider("위험 인식 (7점 리커트)", 1, 7, 4)
                comment = st.text_area("근거·코멘트 (선택)", placeholder="예: 매년 장마철 침수, 배수구 부족 등")
                submitted = st.form_submit_button("인식 점수 등록", use_container_width=True)
            if submitted:
                st.session_state.perceptions.insert(
                    0,
                    {
                        "id": uid("P"),
                        "hazard": p_hazard,
                        "score": score,
                        "comment": comment.strip(),
                        "lng": st.session_state.picked_lng,
                        "lat": st.session_state.picked_lat,
                        "created_at": datetime.now().isoformat(),
                    },
                )
                st.toast(f"위험인식 {score}/7 점이 등록되었습니다.", icon="✓")

        with tab_knowledge:
            with st.form("knowledge_form"):
                category = st.selectbox("지식 유형", list(KNOWLEDGE_CATEGORY), format_func=lambda c: KNOWLEDGE_CATEGORY[c])
                indicator = st.text_input("지표 한 줄 요약", placeholder="예: 두꺼비가 산 위쪽으로 이동")
                description = st.text_area("상세 설명", placeholder="언제, 어떤 조건에서, 어떤 재해의 신호인지 자세히 적어주세요.")
                elder = st.text_input("제공자/출처 (선택)", placeholder="예: 김○○ (1942년생, 마을 어르신)")
                submitted = st.form_submit_button("지식 등록 (FPIC 원칙 준수)", use_container_width=True)
            if submitted:
                if not indicator.strip():
                    st.warning("지표 요약을 입력해 주세요.")
                else:
                    st.session_state.user_knowledge.insert(
                        0,
                        {
                            "id": uid("K"),
                            "type": "knowledge",
                            "category": category,
                            "lng": st.session_state.picked_lng,
                            "lat": st.session_state.picked_lat,
                            "indicator": indicator.strip(),
                            "description": description.strip(),
                            "elder": elder.strip() or None,
                        },
                    )
                    st.toast("전통지식이 등록되었습니다. FPIC 검토 후 공개됩니다.", icon="✓")
                    st.rerun()

        st.markdown('<div class="section-label"><span class="section-label-num">FOOTNOTE</span><span class="section-label-text">데이터 윤리</span></div>', unsafe_allow_html=True)
        st.markdown('<p class="section-desc">모든 토착·지역 지식은 <b style="color:var(--paper)">FPIC</b> 원칙을 따릅니다. 정밀 좌표는 geomasking 처리되며, 개인정보는 익명화됩니다.</p>', unsafe_allow_html=True)


def filter_reports(all_reports, hazard_filter, years_back):
    cutoff = datetime.now() - timedelta(days=365 * years_back)
    return [r for r in all_reports if r["hazard"] in hazard_filter and parse_time(r["occurred_at"]) >= cutoff]


def right_panel(all_reports):
    st.markdown('<div class="section-label"><span class="section-label-num">CONTROL</span><span class="section-label-text">지도 레이어</span></div>', unsafe_allow_html=True)
    for key, label, small in [
        ("reports", "L1 시민 제보", "Point Map"),
        ("knowledge", "L1 전통지식", "Indigenous Knowledge"),
        ("heatmap", "L2 위험도 히트맵", "Kernel Density"),
        ("hotspots", "L2 핫스팟", "Getis-Ord Gi*"),
        ("userDrawings", "L3 사용자 그림", "Drawings & Sketches"),
        ("historical", "L4 역사 지도", "Georeferenced"),
    ]:
        st.session_state.layers[key] = st.toggle(f"{label} · {small}", value=st.session_state.layers[key], key=f"layer_{key}")

    with st.expander("역사지도 아카이브 보기", expanded=False):
        st.markdown("**HISTORICAL MAP ARCHIVE · LAYER 04**")
        for item in HISTORICAL_MAPS:
            st.markdown(f"**{item['title']}**  \n`{item['year']}` · {item['source']}  \n{item['description']}")

    st.markdown('<div class="section-label"><span class="section-label-num">FILTER</span><span class="section-label-text">재해 유형</span></div>', unsafe_allow_html=True)
    hazard_filter = st.multiselect(
        "재해 유형 필터",
        options=list(HAZARD_META),
        default=list(HAZARD_META),
        format_func=lambda h: HAZARD_META[h]["label"],
        label_visibility="collapsed",
    )
    years_back = st.slider("조회 범위", 0.25, 5.0, 2.0, 0.25, format="최근 %.2g년")
    filtered_reports = filter_reports(all_reports, hazard_filter, years_back)

    for h, meta in HAZARD_META.items():
        cnt = len([r for r in filtered_reports if r["hazard"] == h])
        st.markdown(
            f'<div class="legend-row"><span><span class="swatch" style="background:{meta["color"]}"></span>{meta["label"]}</span><span class="count">{cnt}</span></div>',
            unsafe_allow_html=True,
        )

    avg = sum(r["severity"] for r in filtered_reports) / len(filtered_reports) if filtered_reports else math.nan
    hotspots_count = len([h for h in HOTSPOTS if h["hazard"] in hazard_filter])
    regions = {}
    for report in filtered_reports:
        region = approx_region(report["lng"], report["lat"])
        regions[region] = regions.get(region, 0) + 1
    top_regions = sorted(regions.items(), key=lambda item: item[1], reverse=True)[:3]

    st.markdown('<div class="section-label"><span class="section-label-num">LAYER 02</span><span class="section-label-text">통합 분석</span></div>', unsafe_allow_html=True)
    m1, m2 = st.columns(2)
    m3, m4 = st.columns(2)
    for col, label, value, trend in [
        (m1, "누적 제보", len(filtered_reports), f"+{len(st.session_state.user_reports)} 신규"),
        (m2, "평균 심각도", "—" if math.isnan(avg) else f"{avg:.1f}", "/ 5.0"),
        (m3, "핫스팟", hotspots_count, "Gi* 군집"),
        (m4, "지역 다양성", len(regions), "시·도"),
    ]:
        col.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-trend">{trend}</div></div>', unsafe_allow_html=True)

    if top_regions:
        st.markdown("##### 상위 지역 (제보수)")
        for region, cnt in top_regions:
            st.markdown(f'<div class="legend-row"><span><span class="swatch" style="background:var(--ochre-soft)"></span>{region}</span><span class="count">{cnt}</span></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label"><span class="section-label-num">RANK</span><span class="section-label-text">핫스팟 순위</span></div>', unsafe_allow_html=True)
    for i, hotspot in enumerate(sorted([h for h in HOTSPOTS if h["hazard"] in hazard_filter], key=lambda h: h["intensity"], reverse=True)[:5], 1):
        if st.button(f"#{i} {hotspot['name']} · {HAZARD_META[hotspot['hazard']]['label']}", key=f"hot_{hotspot['id']}", use_container_width=True):
            st.session_state.focus_lng = hotspot["lng"]
            st.session_state.focus_lat = hotspot["lat"]
            st.session_state.zoom = 12.5
            st.rerun()
        st.progress(hotspot["intensity"], text=f"{hotspot['method']} · intensity {hotspot['intensity']:.2f}")

    st.markdown('<div class="section-label"><span class="section-label-num">FEED</span><span class="section-label-text">최근 제보</span></div>', unsafe_allow_html=True)
    recent = sorted(all_reports, key=lambda r: parse_time(r["occurred_at"]), reverse=True)[:6]
    for report in recent:
        color = HAZARD_META[report["hazard"]]["color"]
        st.markdown(
            f"""
            <div class="report-card">
              <div class="report-head"><span class="badge" style="border-color:{color}; color:{color};">{HAZARD_META[report["hazard"]]["label"]}</span><span class="report-time">{format_relative_time(report["occurred_at"])}</span></div>
              <div class="report-text">{report["narrative"]}</div>
              <div class="report-foot"><span>{report["place"]}</span><span>심각도 {report["severity"]}/5</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("지도에서 보기", key=f"focus_{report['id']}", use_container_width=True):
            st.session_state.focus_lng = report["lng"]
            st.session_state.focus_lat = report["lat"]
            st.session_state.zoom = 12.5
            st.rerun()

    return hazard_filter, years_back, filtered_reports


def drawing_panel():
    st.markdown('<div class="section-label"><span class="section-label-num">LAYER 03</span><span class="section-label-text">참여형 매핑 도구</span></div>', unsafe_allow_html=True)
    mode = st.radio("도구", ["탐색", "핀", "폴리곤", "라인", "프리핸드"], horizontal=True, label_visibility="collapsed")
    if mode == "핀":
        st.info("좌표 선택에서 위치를 지정하면 지도에 핀이 표시됩니다.")
    elif mode in ["폴리곤", "라인", "프리핸드"]:
        st.caption("좌표는 `경도,위도` 형식으로 줄마다 입력하세요. 프리핸드는 Streamlit 버전에서 라인으로 저장됩니다.")
        sample = "127.0200,37.4900\n127.0500,37.5000\n127.0400,37.5200"
        coords_text = st.text_area("도형 좌표", value=sample if mode == "폴리곤" else "", height=90, placeholder=sample)
        if st.button(f"{mode} 저장", use_container_width=True):
            coords = []
            for line in coords_text.splitlines():
                if "," not in line:
                    continue
                lng, lat = [float(x.strip()) for x in line.split(",", 1)]
                coords.append([lng, lat])
            required = 3 if mode == "폴리곤" else 2
            if len(coords) < required:
                st.warning(f"{mode}은 최소 {required}개 좌표가 필요합니다.")
            else:
                kind = "polygon" if mode == "폴리곤" else "line"
                label = "위험구역" if mode == "폴리곤" else ("범람경로" if mode == "라인" else "자유 스케치")
                st.session_state.user_drawings.append({"kind": kind, "coords": coords, "label": label})
                st.toast(f"{label}이 저장되었습니다.", icon="✓")
                st.rerun()


def detail_panel(all_reports, all_knowledge):
    st.markdown('<div class="section-label"><span class="section-label-num">DETAIL</span><span class="section-label-text">상세 조회</span></div>', unsafe_allow_html=True)
    report_options = {f"{r['place']} · {HAZARD_META[r['hazard']]['label']} · {r['id']}": r for r in all_reports}
    knowledge_options = {f"{k['indicator']} · {KNOWLEDGE_CATEGORY[k['category']]} · {k['id']}": k for k in all_knowledge}
    tab_report, tab_knowledge = st.tabs(["제보", "전통지식"])
    with tab_report:
        selected = st.selectbox("제보 선택", list(report_options), label_visibility="collapsed")
        r = report_options[selected]
        st.markdown(f"**CITIZEN REPORT · LAYER 01**  \n### {r['place']}")
        st.markdown(f"`{HAZARD_META[r['hazard']]['label']}` `심각도 {r['severity']}/5` `{format_relative_time(r['occurred_at'])}`")
        st.write(r["narrative"])
        st.caption(f"제보자 {r['reporter']} · 좌표 {r['lat']:.3f}°N, {r['lng']:.3f}°E · 발생일시 {parse_time(r['occurred_at']).strftime('%Y-%m-%d %H:%M')}")
    with tab_knowledge:
        selected = st.selectbox("지식 선택", list(knowledge_options), label_visibility="collapsed")
        k = knowledge_options[selected]
        st.markdown(f"**LOCAL & INDIGENOUS KNOWLEDGE · LAYER 01**  \n### {k['indicator']}")
        st.markdown(f"`{KNOWLEDGE_CATEGORY[k['category']]}`")
        if k.get("source_year"):
            st.markdown(f"`기록 시점: {k['source_year']}`")
        st.write(k.get("description") or "상세 설명 없음")
        if k.get("elder"):
            st.info(f"구술 제공: {k['elder']}")
        st.caption("FPIC 동의 확보 완료. 본 전통지식은 학술·정책 용도로만 활용됩니다.")


def main():
    init_state()
    inject_css(st.session_state.theme)

    all_reports = REPORTS + st.session_state.user_reports
    all_knowledge = KNOWLEDGE + st.session_state.user_knowledge
    header(len(all_reports))

    left, center, right = st.columns([0.72, 3.1, 0.88], gap="medium")

    with left:
        hazard_filter, years_back, filtered_reports = right_panel(all_reports)
        filtered_knowledge = [k for k in all_knowledge]
        filtered_hotspots = [h for h in HOTSPOTS if h["hazard"] in hazard_filter]

    with center:
        st.markdown(
            """
            <div class="cartouche">
              <div class="cartouche-eyebrow">PARTICIPATORY GIS · 2026</div>
              <div class="cartouche-title">대한민국 재난 통합 지도</div>
              <div class="cartouche-meta">시민지식 × 전통지식 × 과학지식 통합 · WGS84 / EPSG:4326</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.pydeck_chart(make_deck(filtered_reports, filtered_knowledge, filtered_hotspots), use_container_width=True, height=780)
        st.markdown(
            f'<div class="map-note">선택 핀: <b>{st.session_state.picked_lat:.4f}</b>°N, <b>{st.session_state.picked_lng:.4f}</b>°E · zoom <b>{st.session_state.zoom:.1f}</b></div>',
            unsafe_allow_html=True,
        )

        legend_cols = st.columns(5)
        for col, h in zip(legend_cols, HAZARD_META):
            meta = HAZARD_META[h]
            col.markdown(f'<div class="legend-row"><span><span class="swatch" style="background:{meta["color"]}"></span>{meta["label"]}</span></div>', unsafe_allow_html=True)

    with right:
        collection_panel()
        detail_panel(all_reports, all_knowledge)
        with st.expander("참여형 매핑 도구", expanded=False):
            drawing_panel()


if __name__ == "__main__":
    main()
