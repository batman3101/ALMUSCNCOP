import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from google.oauth2 import service_account
from googleapiclient.discovery import build
import bcrypt
import json
import numpy as np

# Google Sheets API 설정
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# 구글 시트 ID 설정
SPREADSHEET_ID = '12l3VeNoTvBQwhKZ29-VqWElEt_vkXEP1wcr73v6ODFs'  # URL에서 ID 부분만 추출

# 세션 스테이트 초기화
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'workers' not in st.session_state:
    st.session_state.workers = pd.DataFrame(columns=['STT', '사번', '이름', '부서', '라인번호'])
if 'daily_records' not in st.session_state:
    st.session_state.daily_records = pd.DataFrame(
        columns=['날짜', '작업자', '라인번호', '모델차수', '목표수량', '생산수량', '불량수량', '특이사항']
    )
if 'users' not in st.session_state:
    st.session_state.users = pd.DataFrame(
        columns=['이메일', '비밀번호', '이름', '권한']  # '이름' 컬럼 추가
    )
if 'clear_users' not in st.session_state:
    st.session_state.clear_users = False
if 'models' not in st.session_state:
    st.session_state.models = pd.DataFrame(columns=['STT', 'MODEL', 'PROCESS'])

def init_google_sheets():
    try:
        # 서비스 계정 정보 가져오기 시도
        try:
            # Streamlit Cloud 환경
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=SCOPES
            )
        except Exception:
            # 로컬 환경
            credentials = service_account.Credentials.from_service_account_file(
                'cnc-op-kpi-management-d552546430e8.json',
                scopes=SCOPES
            )
        
        service = build('sheets', 'v4', credentials=credentials)
        sheets = service.spreadsheets()
        return sheets
    except Exception as e:
        st.error(f"Google Sheets API 초기화 중 오류 발생: {str(e)}")
        return None

def show_login():
    st.title("🔐 CNC 작업자 KPI 관리 시스템 로그인")
    
    # 먼저 사용자 데이터 동기화
    sync_users_with_sheets()
    
    with st.form("login_form"):
        email = st.text_input("이메일")
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인")
        
        if submitted:
            # 디버깅을 위한 정보 출력
            st.write("현재 등록된 사용자:", st.session_state.users['이메일'].tolist())
            
            user = st.session_state.users[st.session_state.users['이메일'] == email]
            if len(user) > 0:
                try:
                    stored_password = user.iloc[0]['비밀번호']
                    if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                        st.session_state.authenticated = True
                        st.session_state.user_role = user.iloc[0]['권한']
                        st.success("로그인 성공!")
                        st.rerun()
                    else:
                        st.error("비밀번호가 일치하지 않습니다.")
                except Exception as e:
                    st.error(f"로그인 처리 중 오류 발생: {str(e)}")
            else:
                st.error("등록되지 않은 이메일입니다.")

def init_admin_account():
    """관리자 계정 초기화"""
    if st.session_state.clear_users or len(st.session_state.users) == 0:
        admin_email = 'zetooo1972@gmail.com'
        admin_password = 'admin7472'
        admin_name = '관리자'
        
        # 비밀번호 해싱
        hashed_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())
        
        # 관리자 계정 생성
        admin_user = pd.DataFrame({
            '이메일': [admin_email],
            '비밀번호': [hashed_password.decode('utf-8')],
            '이름': [admin_name],
            '권한': ['admin']
        })
        
        # users DataFrame을 새로 생성
        st.session_state.users = admin_user
        
        # 구글 시트에 백업
        backup_users_to_sheets()
        
        st.session_state.clear_users = False
        return True
    return False

def sync_workers_with_sheets():
    """구글 시트에서 작업자 데이터 동기화"""
    try:
        sheets = init_google_sheets()
        
        # 구글 시트에서 작업자 데이터 읽기
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range='worker!A2:E'  # A2부터 E열까지 (STT, 사번, 이름, 부서, 라인번호)
        ).execute()
        
        values = result.get('values', [])
        if values:
            # 데이터가 5개 컬럼을 가지도록 보장
            formatted_values = []
            for row in values:
                # 부족한 컬럼을 빈 문자열로 채움
                while len(row) < 5:
                    row.append('')
                formatted_values.append(row[:5])  # 5개 컬럼만 사용
            
            # 구글 시트 데이터를 DataFrame으로 변환
            workers_df = pd.DataFrame(
                formatted_values,
                columns=['STT', '사번', '이름', '부서', '라인번호']
            )
            # 세션 스테이트 업데이트
            st.session_state.workers = workers_df
            return True
        return False
    except Exception as e:
        st.error(f"작업자 데이터 동기화 중 오류 발생: {str(e)}")
        return False

def print_service_account_email():
    try:
        try:
            # Streamlit Cloud 환경
            service_account_info = st.secrets["gcp_service_account"]
        except Exception:
            # 로컬 환경
            with open('cnc-op-kpi-management-d552546430e8.json', 'r') as f:
                service_account_info = json.load(f)
        
        st.info(f"구글 시트 공유 설정에 추가할 이메일: {service_account_info['client_email']}")
    except Exception as e:
        st.error(f"서비스 계정 정보 읽기 중 오류 발생: {str(e)}")

def sync_production_with_sheets():
    try:
        sheets = init_google_sheets()
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range='production!A2:H'  # A부터 H까지 8개 컬럼
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return False
            
        # 데이터 정리 및 변환
        formatted_values = []
        for row in values:
            # 부족한 컬럼을 빈 문자열로 채움
            while len(row) < 8:  # 8개 컬럼이 되도록 보장
                row.append('')
            formatted_values.append(row[:8])
        
        # DataFrame 생성 (8개 컬럼 모두 포함)
        columns = [
            '날짜', '작업자', '라인번호', '모델차수',
            '목표수량', '생산수량', '불량수량', '특이사항'
        ]
        production_df = pd.DataFrame(formatted_values, columns=columns)
        
        # 숫자 데이터 변환
        numeric_columns = ['목표수량', '생산수량', '불량수량']
        for col in numeric_columns:
            production_df[col] = pd.to_numeric(production_df[col], errors='coerce').fillna(0)
        
        # 날짜 형식 통일
        production_df['날짜'] = pd.to_datetime(production_df['날짜']).dt.strftime('%Y-%m-%d')
        
        # 세션 스테이트 업데이트
        st.session_state.daily_records = production_df
        return True
        
    except Exception as e:
        st.error(f"생산 데이터 동기화 중 오류 발생: {str(e)}")
        return False

def get_worker_name(worker_id):
    """작업자 사번으로 이름 조회"""
    if len(st.session_state.workers) > 0:
        worker = st.session_state.workers[st.session_state.workers['사번'] == worker_id]
        if len(worker) > 0:
            return worker.iloc[0]['이름']
    return None

def backup_production_to_sheets():
    try:
        if len(st.session_state.daily_records) == 0:
            return False
            
        sheets = init_google_sheets()
        
        # 백업할 데이터 준비
        backup_data = st.session_state.daily_records.copy()
        
        # 날짜 형식 통일
        backup_data['날짜'] = pd.to_datetime(backup_data['날짜']).dt.strftime('%Y-%m-%d')
        
        # 필요한 컬럼만 선택 (순서 유지)
        columns = [
            '날짜', '작업자', '라인번호', '모델차수',
            '목표수량', '생산수량', '불량수량', '특이사항'
        ]
        backup_data = backup_data[columns]
        
        # DataFrame을 리스트로 변환
        values = [columns]  # 헤더 추가
        values.extend(backup_data.values.tolist())
        
        # 기존 데이터 삭제
        sheets.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range='production!A1:H'
        ).execute()
        
        # 새 데이터 쓰기
        body = {
            'values': values
        }
        sheets.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range='production!A1',
            valueInputOption='RAW',
            body=body
        ).execute()
        
        return True
        
    except Exception as e:
        st.error(f"생산 데이터 백업 중 오류 발생: {str(e)}")
        return False

def show_data_backup():
    st.title("💾 데이터 백업 및 동기화")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 구글 시트에서 데이터 가져오기"):
            if sync_production_with_sheets():
                st.success("생산 데이터가 구글 시트와 동기화되었습니다.")
            else:
                st.warning("동기화할 데이터가 없거나 오류가 발생했습니다.")
    
    with col2:
        if st.button("💾 구글 시트로 데이터 백업"):
            if backup_production_to_sheets():
                st.success("생산 데이터가 구글 시트에 백업되었습니다.")
            else:
                st.warning("백업할 데이터가 없거나 오류가 발생했습니다.")
    
    if len(st.session_state.daily_records) > 0:
        st.subheader("현재 저장된 생산 데이터")
        st.dataframe(st.session_state.daily_records, hide_index=True)

def create_production_chart(data, x_col, title='생산 현황'):
    """생산 현황 차트 생성"""
    # 데이터 정렬
    data = data.sort_values(x_col)
    
    # 차트 생성
    fig = go.Figure()
    
    # 목표수량 막대 그래프 (하늘색)
    fig.add_trace(go.Bar(
        name='목표수량',
        x=data[x_col],
        y=data['목표수량'],
        marker_color='rgba(135, 206, 235, 0.7)',  # 하늘색
        hovertemplate='목표수량: %{y}<extra></extra>'
    ))
    
    # 생산수량 선 그래프 (진한 파란색)
    fig.add_trace(go.Scatter(
        name='생산수량',
        x=data[x_col],
        y=data['생산수량'],
        mode='lines+markers',
        line=dict(color='rgb(0, 0, 139)', width=2),  # 진한 파란색
        marker=dict(size=8),
        hovertemplate='생산수량: %{y}<extra></extra>'
    ))
    
    # 불량수량 선 그래프 (빨간색)
    fig.add_trace(go.Scatter(
        name='불량수량',
        x=data[x_col],
        y=data['불량수량'],
        mode='lines+markers',
        line=dict(color='rgb(255, 0, 0)', width=2),  # 빨간색
        marker=dict(size=8),
        hovertemplate='불량수량: %{y}<extra></extra>'
    ))
    
    # 차트 레이아웃 설정
    fig.update_layout(
        title=title,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        plot_bgcolor='white',
        xaxis=dict(
            title=x_col,
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            tickangle=45 if x_col == '작업자' else 0
        ),
        yaxis=dict(
            title='수량',
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)',
            zeroline=True,
            zerolinecolor='rgba(128, 128, 128, 0.2)'
        ),
        margin=dict(l=50, r=50, t=50, b=50),
        height=400
    )
    
    return fig

def calculate_kpi(data):
    """안전한 KPI 계산을 위한 헬퍼 함수"""
    try:
        # 데이터 타입 변환 및 NaN 처리
        목표수량 = float(pd.to_numeric(data['목표수량'].sum(), errors='coerce') or 0)
        생산수량 = float(pd.to_numeric(data['생산수량'].sum(), errors='coerce') or 0)
        불량수량 = float(pd.to_numeric(data['불량수량'].sum(), errors='coerce') or 0)
        
        # KPI 계산
        달성률 = round((생산수량 / 목표수량 * 100), 2) if 목표수량 > 0 else 0.0
        불량률 = round((불량수량 / 생산수량 * 100), 2) if 생산수량 > 0 else 0.0
        작업효율 = round((달성률 * (1 - 불량률/100)), 2)
        
        return 달성률, 불량률, 작업효율
    except Exception as e:
        st.error(f"KPI 계산 중 오류 발생: {str(e)}")
        return 0.0, 0.0, 0.0

def calculate_worker_kpi(worker_data):
    """작업자별 KPI 계산을 위한 헬퍼 함수"""
    try:
        # 데이터 타입 변환
        worker_data['목표수량'] = pd.to_numeric(worker_data['목표수량'], errors='coerce').fillna(0)
        worker_data['생산수량'] = pd.to_numeric(worker_data['생산수량'], errors='coerce').fillna(0)
        worker_data['불량수량'] = pd.to_numeric(worker_data['불량수량'], errors='coerce').fillna(0)
        
        # KPI 계산
        worker_data['달성률'] = worker_data.apply(
            lambda x: round((x['생산수량'] / x['목표수량'] * 100), 2) if x['목표수량'] > 0 else 0.0,
            axis=1
        )
        worker_data['불량률'] = worker_data.apply(
            lambda x: round((x['불량수량'] / x['생산수량'] * 100), 2) if x['생산수량'] > 0 else 0.0,
            axis=1
        )
        worker_data['작업효율'] = worker_data.apply(
            lambda x: round((x['달성률'] * (1 - x['불량률']/100)), 2),
            axis=1
        )
        
        return worker_data
    except Exception as e:
        st.error(f"작업자별 KPI 계산 중 오류 발생: {str(e)}")
        return pd.DataFrame()

def show_best_kpi_dashboard(current_data, previous_data=None, period=""):
    st.subheader(f"{period} 최우수 KPI 작업자")
    
    try:
        # 작업자별 데이터 집계
        worker_summary = current_data.groupby('작업자').agg({
            '목표수량': 'sum',
            '생산수량': 'sum',
            '불량수량': 'sum'
        }).reset_index()
        
        # 작업자 이름 매핑
        worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
        worker_summary['작업자명'] = worker_summary['작업자'].map(worker_names)
        
        # KPI 계산
        worker_summary = calculate_worker_kpi(worker_summary)
        
        if len(worker_summary) > 0:
            # 최우수 KPI 찾기
            best_achievement = worker_summary.loc[worker_summary['달성률'].idxmax()]
            best_quality = worker_summary.loc[worker_summary['불량률'].idxmin()]
            best_efficiency = worker_summary.loc[worker_summary['작업효율'].idxmax()]
            
            # 이전 데이터와 비교
            delta_achievement = None
            delta_quality = None
            delta_efficiency = None
            
            if previous_data is not None and len(previous_data) > 0:
                prev_summary = previous_data.groupby('작업자').agg({
                    '목표수량': 'sum',
                    '생산수량': 'sum',
                    '불량수량': 'sum'
                }).reset_index()
                prev_summary = calculate_worker_kpi(prev_summary)
                prev_summary['작업효율'] = (prev_summary['달성률'] * (1 - prev_summary['불량률']/100)).round(2)
                
                if len(prev_summary) > 0:
                    prev_best_achievement = prev_summary['달성률'].max()
                    prev_best_quality = prev_summary['불량률'].min()
                    prev_best_efficiency = prev_summary['작업효율'].max()
                    
                    delta_achievement = best_achievement['달성률'] - prev_best_achievement
                    delta_quality = best_quality['불량률'] - prev_best_quality
                    delta_efficiency = best_efficiency['작업효율'] - prev_best_efficiency
            
            # 대시보드 표시
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("##### 🎯 최고 목표달성")
                st.markdown(f"**{best_achievement['작업자명']}**")
                delta_text = f"{delta_achievement:+.2f}%" if delta_achievement is not None else None
                st.metric(
                    "달성률",
                    f"{best_achievement['달성률']:.2f}%",
                    delta_text
                )
            
            with col2:
                st.markdown("##### ✨ 최저 불량률")
                st.markdown(f"**{best_quality['작업자명']}**")
                delta_text = f"{delta_quality:+.2f}%" if delta_quality is not None else None
                st.metric(
                    "불량률",
                    f"{best_quality['불량률']:.2f}%",
                    delta_text
                )
            
            with col3:
                st.markdown("##### 🏆 최고 작업효율")
                st.markdown(f"**{best_efficiency['작업자명']}**")
                delta_text = f"{delta_efficiency:+.2f}%" if delta_efficiency is not None else None
                st.metric(
                    "작업효율",
                    f"{best_efficiency['작업효율']:.2f}%",
                    delta_text
                )
        else:
            st.info("표시할 데이터가 없습니다.")
            
    except Exception as e:
        st.error(f"대시보드 표시 중 오류 발생: {str(e)}")

def main():
    # 페이지 설정
    st.set_page_config(
        page_title="CNC 작업자 KPI 관리 시스템",
        page_icon="🏭",
        layout="wide"
    )

    # 세션 상태 초기화
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'users' not in st.session_state:
        st.session_state.users = pd.DataFrame(
            columns=['이메일', '비밀번호', '이름', '권한']
        )
    if 'clear_users' not in st.session_state:
        st.session_state.clear_users = False  # True에서 False로 변경
    
    # 먼저 사용자 데이터 동기화
    sync_users_with_sheets()
    
    # 관리자 계정이 없을 때만 초기화
    if len(st.session_state.users) == 0:
        init_admin_account()
        sync_users_with_sheets()  # 관리자 계정 생성 후 다시 동기화
    
    # 나머지 데이터 초기화
    if 'workers' not in st.session_state:
        st.session_state.workers = pd.DataFrame(
            columns=['STT', '사번', '이름', '부서', '라인번호']
        )
    if 'daily_records' not in st.session_state:
        st.session_state.daily_records = pd.DataFrame(
            columns=['날짜', '작업자', '라인번호', '모델차수', '목표수량', '생산수량', '불량수량', '특이사항']
        )
    if 'models' not in st.session_state:
        st.session_state.models = pd.DataFrame(
            columns=['STT', 'MODEL', 'PROCESS']
        )

    # 나머지 데이터 동기화
    sync_workers_with_sheets()
    sync_production_with_sheets()
    sync_models_with_sheets()

    # 인증 상태에 따른 화면 표시
    if not st.session_state.authenticated:
        show_login()
    else:
        show_main_menu()

def show_main_menu():
    st.sidebar.title("CNC 작업자 KPI 관리 시스템")
    
    if st.session_state.user_role == 'admin':
        menu_options = [
            "종합 대시보드",
            "사용자 관리",
            "작업자 등록",
            "일일 생산 실적 입력",
            "일간 리포트",
            "주간 리포트",
            "월간 리포트",
            "연간 리포트",
            "데이터 백업 및 동기화"
        ]
    else:
        menu_options = [
            "종합 대시보드",
            "작업자 등록",
            "일일 생산 실적 입력",
            "일간 리포트",
            "주간 리포트",
            "월간 리포트",
            "연간 리포트"
        ]
    
    menu = st.sidebar.selectbox("메뉴 선택", menu_options)
    
    # 로그아웃 버튼
    if st.sidebar.button("로그아웃"):
        st.session_state.authenticated = False
        st.session_state.user_role = None
        st.rerun()
    
    # 작업자 데이터 동기화
    if len(st.session_state.workers) == 0:
        sync_workers_with_sheets()
    
    # 모델차수 데이터 동기화
    if len(st.session_state.models) == 0:
        sync_models_with_sheets()
    
    if menu == "종합 대시보드":
        show_dashboard()
    elif menu == "사용자 관리":
        show_user_management()
    elif menu == "작업자 등록":
        show_worker_registration()
    elif menu == "일일 생산 실적 입력":
        show_daily_production()
    elif menu == "일간 리포트":
        show_daily_report()
    elif menu == "주간 리포트":
        show_weekly_report()
    elif menu == "월간 리포트":
        show_monthly_report()
    elif menu == "연간 리포트":
        show_yearly_report()
    elif menu == "데이터 백업 및 동기화":
        show_data_backup()

def show_dashboard():
    st.title("📊 종합 대시보드")
    
    if len(st.session_state.daily_records) > 0:
        # 작업자 선택 드롭다운 추가
        worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
        all_workers = ['전체'] + list(worker_names.values())
        selected_worker = st.selectbox("작업자 선택", options=all_workers)
        
        # 데이터 필터링
        dashboard_data = st.session_state.daily_records.copy()
        
        # 선택된 작업자에 대한 필터링
        if selected_worker != '전체':
            worker_id = [k for k, v in worker_names.items() if v == selected_worker][0]
            dashboard_data = dashboard_data[dashboard_data['작업자'] == worker_id]
        
        # 이전 기간과 현재 기간의 데이터 분리
        current_date = datetime.now().date()
        previous_date = current_date - pd.Timedelta(days=7)  # 7일 전과 비교
        
        current_data = dashboard_data[
            pd.to_datetime(dashboard_data['날짜']).dt.date > previous_date
        ]
        previous_data = dashboard_data[
            pd.to_datetime(dashboard_data['날짜']).dt.date <= previous_date
        ]
        
        # KPI 계산
        achievement_rate, defect_rate, efficiency_rate = calculate_kpi(current_data)
        
        # 이전 기간 KPI 계산
        prev_achievement, prev_defect, prev_efficiency = calculate_kpi(previous_data)
        
        # KPI 변화량 계산
        delta_achievement = achievement_rate - prev_achievement
        delta_defect = defect_rate - prev_defect
        delta_efficiency = efficiency_rate - prev_efficiency
        
        st.header("종합 대시보드")
        
        # KPI 지표 표시
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "전체 생산목표달성률",
                f"{achievement_rate:.1f}%",
                f"{delta_achievement:+.1f}%"
            )
        with col2:
            st.metric(
                "평균 불량률",
                f"{defect_rate:.1f}%",
                f"{delta_defect:+.1f}%"
            )
        with col3:
            st.metric(
                "평균 작업효율",
                f"{efficiency_rate:.1f}%",
                f"{delta_efficiency:+.1f}%"
            )
        
        st.subheader("생산 현황")
        
        # 월별 데이터 집계
        monthly_summary = dashboard_data.copy()
        monthly_summary['년월'] = pd.to_datetime(monthly_summary['날짜']).dt.strftime('%Y-%m')
        monthly_summary = monthly_summary.groupby('년월').agg({
            '목표수량': 'sum',
            '생산수량': 'sum',
            '불량수량': 'sum'
        }).reset_index()
        
        # 최근 6개월 데이터만 표시
        monthly_summary = monthly_summary.sort_values('년월', ascending=True).tail(6)
        
        # 차트 생성
        fig = go.Figure()
        
        # 목표수량 - 하늘색 막대
        fig.add_trace(go.Bar(
            name='목표수량',
            x=monthly_summary['년월'],
            y=monthly_summary['목표수량'],
            marker_color='skyblue'
        ))
        
        # 생산수량 - 청색 선
        fig.add_trace(go.Scatter(
            name='생산수량',
            x=monthly_summary['년월'],
            y=monthly_summary['생산수량'],
            line=dict(color='blue')
        ))
        
        # 불량수량 - 빨간색 선
        fig.add_trace(go.Scatter(
            name='불량수량',
            x=monthly_summary['년월'],
            y=monthly_summary['불량수량'],
            line=dict(color='red')
        ))
        
        # 차트 레이아웃 설정
        fig.update_layout(
            title='월별 생산 현황',
            xaxis_title='년월',
            yaxis_title='수량',
            barmode='group',
            height=400,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # 차트 표시
        st.plotly_chart(fig, use_container_width=True)
        
        # 월별 실적 데이터 표시
        st.subheader("월별 실적")
        display_cols = ['년월', '목표수량', '생산수량', '불량수량']
        st.dataframe(monthly_summary[display_cols], hide_index=True)
        
    else:
        st.info("표시할 데이터가 없습니다.")

def show_daily_production():
    st.title("📝 일일 생산 실적 입력/수정")
    
    tab1, tab2, tab3 = st.tabs(["신규 입력", "데이터 수정", "중복 데이터 관리"])
    
    with tab1:
        show_new_production_input()
    
    with tab2:
        show_production_edit()
    
    with tab3:
        show_duplicate_management()

def show_new_production_input():
    """신규 생산 데이터 입력 폼"""
    st.subheader("신규 생산 데이터 입력")
    
    with st.form("production_input_form"):
        # 날짜 선택
        input_date = st.date_input("날짜", datetime.now())
        
        # 작업자 선택 (이름으로 표시, ID로 저장)
        worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
        selected_worker_name = st.selectbox("작업자", options=list(worker_names.values()))
        worker_id = [k for k, v in worker_names.items() if v == selected_worker_name][0]
        
        # 나머지 입력 필드
        line_number = st.text_input("라인번호")
        model = st.text_input("모델차수")
        target_qty = st.number_input("목표수량", min_value=0)
        prod_qty = st.number_input("생산수량", min_value=0)
        defect_qty = st.number_input("불량수량", min_value=0)
        note = st.text_area("특이사항")
        
        submitted = st.form_submit_button("저장")
        
        if submitted:
            # 새 생산 기록 생성
            new_record = pd.DataFrame({
                '날짜': [input_date.strftime('%Y-%m-%d')],
                '작업자': [worker_id],
                '라인번호': [line_number],
                '모델차수': [model],
                '목표수량': [target_qty],
                '생산수량': [prod_qty],
                '불량수량': [defect_qty],
                '특이사항': [note]
            })
            
            # 세션 스테이트 업데이트
            st.session_state.daily_records = pd.concat(
                [st.session_state.daily_records, new_record],
                ignore_index=True
            )
            
            # 구글 시트에 백업
            if backup_production_to_sheets():
                st.success("생산 데이터가 저장되었습니다.")
                st.rerun()
            else:
                st.error("데이터 저장 중 오류가 발생했습니다.")

def show_production_edit():
    """데이터 수정 탭"""
    st.subheader("생산 데이터 수정")
    
    # 날짜 선택
    edit_date = st.date_input("수정할 날짜 선택", datetime.now())
    date_str = edit_date.strftime('%Y-%m-%d')
    
    # 해당 날짜의 데이터 필터링
    daily_data = st.session_state.daily_records[
        st.session_state.daily_records['날짜'].astype(str) == date_str
    ]
    
    if len(daily_data) > 0:
        # 수정할 레코드 선택
        selected_index = st.selectbox(
            "수정할 레코드 선택",
            options=daily_data.index,
            format_func=lambda x: f"{daily_data.loc[x, '작업자']} - {daily_data.loc[x, '모델차수']}"
        )
        
        selected_record = daily_data.loc[selected_index]
        
        with st.form("edit_form"):
            line_number = st.text_input("라인번호", value=selected_record['라인번호'])
            model = st.text_input("모델차수", value=selected_record['모델차수'])
            target_qty = st.number_input("목표수량", value=int(selected_record['목표수량']))
            prod_qty = st.number_input("생산수량", value=int(selected_record['생산수량']))
            defect_qty = st.number_input("불량수량", value=int(selected_record['불량수량']))
            note = st.text_area("특이사항", value=selected_record['특이사항'])
            
            if st.form_submit_button("수정"):
                if update_production_record(
                    edit_date, selected_record, line_number, model,
                    target_qty, prod_qty, defect_qty, note
                ):
                    st.success("데이터가 수정되었습니다.")
                    backup_production_to_sheets()
                    st.rerun()
    else:
        st.info(f"{date_str} 날짜의 생산 데이터가 없습니다.")

def show_duplicate_management():
    """중복 데이터 관리 탭"""
    st.subheader("중복 데이터 관리")
    
    if st.button("중복 데이터 검사"):
        duplicates = check_duplicate_records()
        if duplicates:
            st.success("중복 데이터가 제거되었습니다.")
            backup_production_to_sheets()
            st.rerun()
        else:
            st.info("중복 데이터가 없습니다.")

def show_worker_registration():
    st.title("👥 작업자 등록")
    
    # 관리자 계정일 때만 서비스 계정 이메일 표시
    if st.session_state.user_role == 'admin':
        print_service_account_email()
    
    # 구글 시트 동기화 버튼
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔄 구글 시트 동기화"):
            if sync_workers_with_sheets():
                st.success("작업자 데이터가 구글 시트와 동기화되었습니다.")
            else:
                st.warning("동기화할 데이터가 없거나 오류가 발생했습니다.")
    
    # 현재 등록된 작업자 목록 표시
    if len(st.session_state.workers) > 0:
        st.subheader("등록된 작업자 목록")
        # hide_index=True를 추가하여 인덱스 열 숨기기
        st.dataframe(st.session_state.workers, hide_index=True)
    
    # 새 작업자 등록 폼
    st.subheader("새 작업자 등록")
    with st.form("worker_registration_form"):
        emp_id = st.text_input("사번")
        name = st.text_input("이름")
        department = st.text_input("부서")
        line_numbers = st.text_input("담당 라인번호")
        
        submitted = st.form_submit_button("등록")
        
        if submitted:
            if not emp_id or not name or not department or not line_numbers:
                st.error("모든 필드를 입력해주세요.")
                return
            
            # 사번 중복 체크
            if emp_id in st.session_state.workers['사번'].values:
                st.error("이미 등록된 사번입니다.")
                return
            
            # 새로운 STT 번호 생성 (기존 번호 중 최대값 + 1)
            if len(st.session_state.workers) > 0:
                next_stt = f"{int(st.session_state.workers['STT'].max()) + 1:02d}"
            else:
                next_stt = "01"
            
            new_worker = pd.DataFrame({
                'STT': [next_stt],
                '사번': [emp_id],
                '이름': [name],
                '부서': [department],
                '라인번호': [line_numbers]
            })
            
            # 로컬 데이터 업데이트
            st.session_state.workers = pd.concat([st.session_state.workers, new_worker], ignore_index=True)
            
            # 구글 시트 업데이트
            try:
                sheets = init_google_sheets()
                values = [[next_stt, emp_id, name, department, line_numbers]]
                body = {
                    'values': values
                }
                sheets.values().append(
                    spreadsheetId=SPREADSHEET_ID,
                    range='worker!A2:E',  # STT 컬럼 포함
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body=body
                ).execute()
                
                st.success(f"작업자 {name}이(가) 등록되었습니다.")
                st.rerun()
            except Exception as e:
                st.error(f"구글 시트 업데이트 중 오류 발생: {str(e)}")

def show_monthly_report():
    """월간 리포트"""
    st.title("📊 월간 리포트")
    
    # 연도와 월 선택
    col1, col2 = st.columns(2)
    with col1:
        year = st.selectbox("연도 선택", 
                           options=range(2030, 2024, -1),
                           index=5)
    with col2:
        month = st.selectbox("월 선택",
                           options=range(1, 13),
                           index=datetime.now().month-1)
    
    # 선택된 월의 시작일과 종료일 계산
    start_date = datetime(year, month, 1).date()
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
    
    # 해당 월의 데이터 필터링 (날짜 컬럼 이름 수정)
    monthly_data = st.session_state.daily_records[
        (pd.to_datetime(st.session_state.daily_records['날짜']).dt.year == year) &
        (pd.to_datetime(st.session_state.daily_records['날짜']).dt.month == month)
    ]
    
    # 리포트 템플릿 표시
    show_report_content(monthly_data, "월간", start_date, end_date)

def show_yearly_report():
    """연간 리포트"""
    st.title("📊 연간 리포트")
    year = st.selectbox("연도 선택", 
                       options=range(2030, 2024, -1),
                       index=5)
    st.markdown("---")
    
    start_date = datetime(year, 1, 1).date()
    end_date = datetime(year, 12, 31).date()
    
    yearly_data = st.session_state.daily_records[
        pd.to_datetime(st.session_state.daily_records['날짜']).dt.year == year
    ]
    
    show_report_content(yearly_data, "연간", start_date, end_date)

def show_user_management():
    st.title("👤 사용자 관리")
    
    # 사용자 데이터 동기화
    sync_users_with_sheets()
    
    # 기존 사용자 목록 표시
    if len(st.session_state.users) > 0:
        st.subheader("등록된 사용자 목록")
        display_users = st.session_state.users[['이메일', '이름', '권한']].copy()
        display_users.insert(0, 'STT', range(1, len(display_users) + 1))
        display_users['STT'] = display_users['STT'].apply(lambda x: f"{x:02d}")
        st.dataframe(display_users, hide_index=True)
    
    # 새 사용자 등록 폼
    st.subheader("새 사용자 등록")
    with st.form("user_registration_form"):
        email = st.text_input("이메일")
        password = st.text_input("비밀번호", type="password")
        name = st.text_input("이름")
        role = st.selectbox("권한", ["user", "admin"])
        
        submitted = st.form_submit_button("저장")
        
        if submitted:
            if email in st.session_state.users['이메일'].values:
                st.error("이미 등록된 이메일입니다.")
                return
            
            if not email or not password or not name:
                st.error("모든 필드를 입력해주세요.")
                return
            
            # 비밀번호 해싱
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            # 새 사용자 추가
            new_user = pd.DataFrame({
                '이메일': [email],
                '비밀번호': [hashed_password.decode('utf-8')],
                '이름': [name],
                '권한': [role]
            })
            
            st.session_state.users = pd.concat([st.session_state.users, new_user], ignore_index=True)
            
            # 구글 시트에 백업
            if backup_users_to_sheets():
                st.success(f"사용자 {email}가 등록되었습니다.")
                st.rerun()
            else:
                st.error("사용자 등록 중 오류가 발생했습니다.")

    # 사용자 삭제 섹션 추가
    if len(st.session_state.users) > 0:
        st.subheader("사용자 삭제")
        # 관리자 계정(zetooo1972@gmail.com)을 제외한 사용자 목록
        delete_email = st.selectbox(
            "삭제할 사용자 선택", 
            options=st.session_state.users[
                st.session_state.users['이메일'] != 'zetooo1972@gmail.com'
            ]['이메일'].tolist()
        )
        
        if st.button("선택한 사용자 삭제"):
            if delete_email:
                # 관리자 계정은 삭제 불가
                if delete_email == 'zetooo1972@gmail.com':
                    st.error("관리자 계정은 삭제할 수 없습니다.")
                else:
                    # 선택한 사용자 삭제
                    st.session_state.users = st.session_state.users[
                        st.session_state.users['이메일'] != delete_email
                    ]
                    # 구글 시트에 백업
                    if backup_users_to_sheets():
                        st.success(f"사용자 {delete_email}가 삭제되었습니다.")
                        st.rerun()
                    else:
                        st.error("사용자 삭제 중 오류가 발생했습니다.")

def show_daily_report():
    """일간 리포트"""
    st.title("📊 일간 리포트")
    selected_date = st.date_input("날짜 선택", datetime.now())
    daily_data = st.session_state.daily_records[
        pd.to_datetime(st.session_state.daily_records['날짜']).dt.date == selected_date
    ]
    show_report_content(daily_data, "일간", selected_date, selected_date)

def show_weekly_report():
    """주간 리포트"""
    st.title("📊 주간 리포트")
    selected_date = st.date_input("조회할 주의 시작일 선택", datetime.now())
    start_of_week = selected_date - pd.Timedelta(days=selected_date.weekday())
    end_of_week = start_of_week + pd.Timedelta(days=6)
    weekly_data = st.session_state.daily_records[
        (pd.to_datetime(st.session_state.daily_records['날짜']).dt.date >= start_of_week) &
        (pd.to_datetime(st.session_state.daily_records['날짜']).dt.date <= end_of_week)
    ]
    show_report_content(weekly_data, "주간", start_of_week, end_of_week)

def show_report_content(data, period_type, start_date, end_date):
    """리포트 내용 표시"""
    # 이전 기간 데이터 가져오기
    prev_data = get_previous_period_data(period_type, start_date, end_date)
    
    # 1. 전체 KPI 표시
    st.subheader("📊 전체 KPI")
    total_kpi = calculate_kpi(data)
    prev_total_kpi = calculate_kpi(prev_data)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        delta = total_kpi[0] - prev_total_kpi[0]
        st.metric("🎯 생산목표달성률", f"{total_kpi[0]:.2f}%", f"{delta:+.2f}%")
    with col2:
        delta = total_kpi[1] - prev_total_kpi[1]
        st.metric("⚠️ 불량률", f"{total_kpi[1]:.2f}%", f"{delta:+.2f}%")
    with col3:
        delta = total_kpi[2] - prev_total_kpi[2]
        st.metric("⚡ 작업효율", f"{total_kpi[2]:.2f}%", f"{delta:+.2f}%")
    
    # 2. 최우수 작업자 KPI 표시
    st.subheader("🏆 최우수 작업자 KPI")
    best_workers = get_best_workers(data)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("##### 🎯 최고 목표달성")
        st.markdown(f"**{best_workers['achievement']['name']}**")
        delta = best_workers['achievement']['value'] - best_workers['achievement']['previous_value']
        st.metric("달성률", 
                 f"{best_workers['achievement']['value']:.2f}%",
                 f"{delta:+.2f}%")
    
    with col2:
        st.markdown("##### ✨ 최저 불량률")
        st.markdown(f"**{best_workers['defect']['name']}**")
        delta = best_workers['defect']['value'] - best_workers['defect']['previous_value']
        st.metric("불량률",
                 f"{best_workers['defect']['value']:.2f}%",
                 f"{delta:+.2f}%")
    
    with col3:
        st.markdown("##### 🏆 최고 작업효율")
        st.markdown(f"**{best_workers['efficiency']['name']}**")
        delta = best_workers['efficiency']['value'] - best_workers['efficiency']['previous_value']
        st.metric("작업효율",
                 f"{best_workers['efficiency']['value']:.2f}%",
                 f"{delta:+.2f}%")
    
    # 3. 작업자 선택 및 KPI 표시
    worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
    all_workers = ['전체'] + list(worker_names.values())
    selected_worker = st.selectbox("👥 작업자 선택", options=all_workers)
    
    if selected_worker != '전체':
        worker_id = [k for k, v in worker_names.items() if v == selected_worker][0]
        worker_data = data[data['작업자'] == worker_id]
        prev_worker_data = prev_data[prev_data['작업자'] == worker_id]
        
        if len(worker_data) > 0:
            st.subheader(f"👤 {selected_worker} KPI")
            worker_kpi = calculate_kpi(worker_data)
            prev_worker_kpi = calculate_kpi(prev_worker_data)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                delta = worker_kpi[0] - prev_worker_kpi[0]
                st.metric("🎯 생산목표달성률", f"{worker_kpi[0]:.2f}%", f"{delta:+.2f}%")
            with col2:
                delta = worker_kpi[1] - prev_worker_kpi[1]
                st.metric("⚠️ 불량률", f"{worker_kpi[1]:.2f}%", f"{delta:+.2f}%")
            with col3:
                delta = worker_kpi[2] - prev_worker_kpi[2]
                st.metric("⚡ 작업효율", f"{worker_kpi[2]:.2f}%", f"{delta:+.2f}%")
    
    # 작업자별 실적 표시
    st.subheader("📋 작업자별 실적")
    worker_stats = calculate_worker_stats(data)
    st.dataframe(worker_stats, hide_index=True)
    
    # 생산 현황 차트
    st.subheader(f"📈 {period_type} 생산 현황")
    if len(data) > 0:
        chart_data = prepare_chart_data(data, period_type)
        fig = create_production_chart(
            chart_data,
            '작업자' if period_type == '작업자별' else '날짜'
        )
        st.plotly_chart(fig, use_container_width=True)

def sync_models_with_sheets():
    """구글 시트에서 모델차수 데이터 동기화"""
    try:
        sheets = init_google_sheets()
        
        # 구글 시트에서 모델차수 데이터 읽기
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range='model!A2:C'  # A2부터 C열까지
        ).execute()
        
        values = result.get('values', [])
        if values:
            # 구글 시트 데이터를 DataFrame으로 변환
            models_df = pd.DataFrame(values, columns=['STT', 'MODEL', 'PROCESS'])
            # 세션 스테이트 업데이트
            st.session_state.models = models_df
            return True
        return False
    except Exception as e:
        st.error(f"모델차수 데이터 동기화 중 오류 발생: {str(e)}")
        return False

def sync_users_with_sheets():
    """구글 시트에서 사용자 데이터 동기화"""
    try:
        sheets = init_google_sheets()
        
        # 구글 시트에서 사용자 데이터 읽기
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range='user!A2:D'  # A2부터 D열까지 (이메일, 비밀번호, 이름, 권한)
        ).execute()
        
        values = result.get('values', [])
        if values:
            # 구글 시트 데이터를 DataFrame으로 변환
            users_df = pd.DataFrame(values, columns=['이메일', '비밀번호', '이름', '권한'])
            # 세션 스테이트 업데이트
            st.session_state.users = users_df
            return True
        return False
    except Exception as e:
        st.error(f"사용자 데이터 동기화 중 오류 발생: {str(e)}")
        return False

def backup_users_to_sheets():
    """사용자 데이터를 구글 시트에 백업"""
    try:
        if len(st.session_state.users) > 0:
            sheets = init_google_sheets()
            
            # DataFrame을 리스트로 변환
            values = [['이메일', '비밀번호', '이름', '권한']]  # 헤더 추가
            values.extend(st.session_state.users.values.tolist())
            
            # 기존 데이터 삭제
            sheets.values().clear(
                spreadsheetId=SPREADSHEET_ID,
                range='user!A1:D'
            ).execute()
            
            # 새 데이터 쓰기
            body = {
                'values': values
            }
            
            sheets.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range='user!A1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            return True
        return False
    except Exception as e:
        st.error(f"사용자 데이터 백업 중 오류 발생: {str(e)}")
        return False

def check_duplicate_records():
    """중복 데이터 검사"""
    try:
        # 중복 체크를 위한 키 컬럼
        key_columns = ['날짜', '작업자', '라인번호', '모델차수']
        
        # 중복 레코드 찾기
        duplicates = st.session_state.daily_records[
            st.session_state.daily_records.duplicated(subset=key_columns, keep='first')
        ]
        
        if len(duplicates) > 0:
            # 중복 제거 (첫 번째 레코드 유지)
            st.session_state.daily_records.drop_duplicates(
                subset=key_columns, 
                keep='first', 
                inplace=True
            )
            return True
            
        return False
    except Exception as e:
        st.error(f"중복 검사 중 오류 발생: {str(e)}")
        return False

def update_production_record(date, old_record, line_number, model, target_qty, prod_qty, defect_qty, note):
    """생산 기록 업데이트"""
    try:
        # 기존 레코드 찾기
        idx = st.session_state.daily_records[
            (st.session_state.daily_records['날짜'] == date.strftime('%Y-%m-%d')) &
            (st.session_state.daily_records['작업자'] == old_record['작업자'])
        ].index[0]
        
        # 레코드 업데이트
        st.session_state.daily_records.loc[idx, '라인번호'] = line_number
        st.session_state.daily_records.loc[idx, '모델차수'] = model
        st.session_state.daily_records.loc[idx, '목표수량'] = target_qty
        st.session_state.daily_records.loc[idx, '생산수량'] = prod_qty
        st.session_state.daily_records.loc[idx, '불량수량'] = defect_qty
        st.session_state.daily_records.loc[idx, '특이사항'] = note
        
        return True
    except Exception as e:
        st.error(f"데이터 업데이트 중 오류 발생: {str(e)}")
        return False

def show_worker_report():
    st.title("👥 작업자별 실적")
    
    if len(st.session_state.daily_records) > 0:
        # 날짜 필터 추가
        col1, col2 = st.columns(2)
        with col1:
            current_date = datetime.now()
            selected_year = st.selectbox(
                "연도 선택",
                options=range(2024, 2020, -1),
                index=0
            )
        with col2:
            selected_month = st.selectbox(
                "월 선택",
                options=range(1, 13),
                index=current_date.month-1
            )
        
        # 작업자 선택 드롭다운
        worker_names = st.session_state.workers['이름'].unique().tolist()
        all_workers = ['전체'] + worker_names
        selected_worker = st.selectbox("작업자 선택", options=all_workers)
        
        # 선택된 연월의 데이터 필터링
        date_mask = (
            pd.to_datetime(st.session_state.daily_records['날짜']).dt.year == selected_year
        ) & (
            pd.to_datetime(st.session_state.daily_records['날짜']).dt.month == selected_month
        )
        
        monthly_data = st.session_state.daily_records[date_mask].copy()
        
        if len(monthly_data) > 0:
            if selected_worker != '전체':
                monthly_data = monthly_data[monthly_data['작업자'] == selected_worker]
            
            # 작업자별 집계
            worker_stats = monthly_data.groupby('작업자').agg({
                '목표수량': 'sum',
                '생산수량': 'sum',
                '불량수량': 'sum'
            }).reset_index()
            
            # 달성률과 불량률 계산
            worker_stats['달성률'] = (worker_stats['생산수량'] / worker_stats['목표수량'] * 100).round(1)
            worker_stats['불량률'] = (worker_stats['불량수량'] / worker_stats['생산수량'] * 100).round(1)
            
            # 컬럼 순서 변경
            worker_stats = worker_stats[[
                '작업자', '목표수량', '생산수량', '불량수량', '달성률', '불량률'
            ]]
            
            # 데이터 표시
            st.subheader(f"{selected_year}년 {selected_month}월 작업자별 실적")
            st.dataframe(
                worker_stats,
                column_config={
                    '달성률': st.column_config.NumberColumn(
                        '달성률(%)',
                        format="%.1f%%"
                    ),
                    '불량률': st.column_config.NumberColumn(
                        '불량률(%)',
                        format="%.1f%%"
                    )
                },
                hide_index=True
            )
            
            # 차트 표시
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='생산수량',
                x=worker_stats['작업자'],
                y=worker_stats['생산수량'],
                text=worker_stats['생산수량'],
                textposition='auto',
            ))
            fig.add_trace(go.Bar(
                name='불량수량',
                x=worker_stats['작업자'],
                y=worker_stats['불량수량'],
                text=worker_stats['불량수량'],
                textposition='auto',
            ))
            fig.update_layout(
                title=f'{selected_year}년 {selected_month}월 작업자별 생산/불량 현황',
                barmode='group'
            )
            st.plotly_chart(fig)
        else:
            st.info(f"{selected_year}년 {selected_month}월의 생산 데이터가 없습니다.")
    else:
        st.info("등록된 생산 실적이 없습니다.")

def show_report_template(data, period_type, start_date, end_date):
    """리포트 템플릿"""
    st.title(f"📊 {period_type} 리포트")
    
    # 작업자 선택 드롭다운
    worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
    all_workers = ['전체'] + list(worker_names.values())
    selected_worker = st.selectbox("작업자 선택", options=all_workers)
    
    # 데이터 필터링
    filtered_data = data.copy()
    if selected_worker != '전체':
        worker_id = [k for k, v in worker_names.items() if v == selected_worker][0]
        filtered_data = filtered_data[filtered_data['작업자'] == worker_id]
    
    # 1. 최우수 KPI 작업자 섹션
    st.subheader(f"{period_type} 최우수 KPI 작업자")
    
    # 이전 기간 데이터와 비교하여 KPI 변화량 계산
    current_kpi = calculate_best_kpi(filtered_data)
    previous_kpi = calculate_best_kpi(get_previous_period_data(start_date, end_date))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("##### 🎯 최고 목표달성")
        st.markdown(f"**{current_kpi['best_achievement_worker']}**")
        delta = current_kpi['achievement_rate'] - previous_kpi['achievement_rate']
        st.metric("달성률", 
                 f"{current_kpi['achievement_rate']:.2f}%",
                 f"{delta:+.2f}%")
    
    with col2:
        st.markdown("##### ✨ 최저 불량률")
        st.markdown(f"**{current_kpi['best_quality_worker']}**")
        delta = current_kpi['defect_rate'] - previous_kpi['defect_rate']
        st.metric("불량률",
                 f"{current_kpi['defect_rate']:.2f}%",
                 f"{delta:+.2f}%")
    
    with col3:
        st.markdown("##### 🏆 최고 작업효율")
        st.markdown(f"**{current_kpi['best_efficiency_worker']}**")
        delta = current_kpi['efficiency_rate'] - previous_kpi['efficiency_rate']
        st.metric("작업효율",
                 f"{current_kpi['efficiency_rate']:.2f}%",
                 f"{delta:+.2f}%")
    
    # 2. 기간 표시
    st.markdown(f"**기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}**")
    
    # 3. 전체 KPI 지표
    total_kpi = calculate_kpi(filtered_data)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(f"{period_type} 생산목표달성률", f"{total_kpi[0]:.2f}%")
    with col2:
        st.metric(f"{period_type} 불량률", f"{total_kpi[1]:.2f}%")
    with col3:
        st.metric(f"{period_type} 작업효율", f"{total_kpi[2]:.2f}%")
    
    # 4. 작업자별 실적
    st.subheader("작업자별 실적")
    worker_stats = calculate_worker_stats(filtered_data)
    st.dataframe(worker_stats, hide_index=True)
    
    # 5. 일별 생산 현황 차트
    st.subheader("일별 생산 현황")
    
    # 작업자 이름 매핑 가져오기
    worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
    
    # 데이터 복사 및 작업자 이름 매핑
    chart_data = data.copy()
    chart_data['작업자명'] = chart_data['작업자'].map(worker_names)
    
    # 작업자별로 데이터 그룹화
    worker_production = chart_data.groupby('작업자명').agg({
        '목표수량': 'sum',
        '생산수량': 'sum',
        '불량수량': 'sum'
    }).reset_index()
    
    fig = create_production_chart(
        worker_production, 
        '작업자명',  # x축에 작업자명 사용
        f'{period_type} 작업자별 생산 현황'
    )
    st.plotly_chart(fig, use_container_width=True)

def calculate_worker_stats(data):
    """작업자별 통계 계산"""
    try:
        # 빈 데이터 체크
        if len(data) == 0:
            return pd.DataFrame(columns=['작업자명', '목표수량', '생산수량', '불량수량', '달성률', '불량률', '작업효율'])
        
        # 데이터 복사
        data = data.copy()
        
        # 작업자별 집계 (작업자명 매핑 없이 직접 사용)
        worker_stats = data.groupby('작업자').agg({
            '목표수량': 'sum',
            '생산수량': 'sum',
            '불량수량': 'sum'
        }).reset_index()
        
        # 컬럼명 변경
        worker_stats = worker_stats.rename(columns={'작업자': '작업자명'})
        
        # KPI 계산
        worker_stats['달성률'] = np.where(
            worker_stats['목표수량'] > 0,
            (worker_stats['생산수량'] / worker_stats['목표수량'] * 100).round(2),
            0.0
        )
        
        worker_stats['불량률'] = np.where(
            worker_stats['생산수량'] > 0,
            (worker_stats['불량수량'] / worker_stats['생산수량'] * 100).round(2),
            0.0
        )
        
        worker_stats['작업효율'] = (worker_stats['달성률'] * (1 - worker_stats['불량률']/100)).round(2)
        
        # 숫자 컬럼 정수로 변환
        int_columns = ['목표수량', '생산수량', '불량수량']
        worker_stats[int_columns] = worker_stats[int_columns].astype(int)
        
        return worker_stats
        
    except Exception as e:
        st.error(f"작업자별 통계 계산 중 오류 발생: {str(e)}")
        return pd.DataFrame(columns=['작업자명', '목표수량', '생산수량', '불량수량', '달성률', '불량률', '작업효율'])

def calculate_best_kpi(data):
    """최우수 KPI 계산"""
    if len(data) == 0:
        return {
            'best_achievement_worker': 'nan',
            'best_quality_worker': 'nan',
            'best_efficiency_worker': 'nan',
            'achievement_rate': 0.0,
            'defect_rate': 0.0,
            'efficiency_rate': 0.0
        }
    
    worker_stats = calculate_worker_stats(data)
    
    try:
        # 최고 달성률
        best_achievement = worker_stats.loc[worker_stats['달성률'].idxmax()]
        # 최저 불량률
        best_quality = worker_stats.loc[worker_stats['불량률'].idxmin()]
        # 최고 작업효율
        best_efficiency = worker_stats.loc[worker_stats['작업효율'].idxmax()]
        
        return {
            'best_achievement_worker': best_achievement['작업자명'],
            'best_quality_worker': best_quality['작업자명'],
            'best_efficiency_worker': best_efficiency['작업자명'],
            'achievement_rate': float(best_achievement['달성률']),
            'defect_rate': float(best_quality['불량률']),
            'efficiency_rate': float(best_efficiency['작업효율'])
        }
    except Exception as e:
        st.error(f"KPI 계산 중 오류 발생: {str(e)}")
        return {
            'best_achievement_worker': 'nan',
            'best_quality_worker': 'nan',
            'best_efficiency_worker': 'nan',
            'achievement_rate': 0.0,
            'defect_rate': 0.0,
            'efficiency_rate': 0.0
        }

def get_previous_period_data(period_type, start_date, end_date):
    """이전 기간 데이터 가져오기"""
    if period_type == "일간":
        prev_start = start_date - pd.Timedelta(days=1)
        prev_end = prev_start
    elif period_type == "주간":
        prev_start = start_date - pd.Timedelta(days=7)
        prev_end = end_date - pd.Timedelta(days=7)
    elif period_type == "월간":
        prev_start = (start_date.replace(day=1) - pd.Timedelta(days=1)).replace(day=1)
        prev_end = start_date - pd.Timedelta(days=1)
    else:  # 연간
        prev_start = datetime(start_date.year - 1, 1, 1).date()
        prev_end = datetime(start_date.year - 1, 12, 31).date()
    
    return st.session_state.daily_records[
        (pd.to_datetime(st.session_state.daily_records['날짜']).dt.date >= prev_start) &
        (pd.to_datetime(st.session_state.daily_records['날짜']).dt.date <= prev_end)
    ]

def get_best_workers(data):
    """최우수 작업자 KPI 계산"""
    if len(data) == 0:
        return {
            'achievement': {'name': 'N/A', 'value': 0.0, 'previous_value': 0.0},
            'defect': {'name': 'N/A', 'value': 0.0, 'previous_value': 0.0},
            'efficiency': {'name': 'N/A', 'value': 0.0, 'previous_value': 0.0}
        }
    
    # 작업자별 KPI 계산
    worker_stats = data.groupby('작업자').agg({
        '목표수량': 'sum',
        '생산수량': 'sum',
        '불량수량': 'sum'
    }).reset_index()
    
    # 작업자 정보 가져오기
    workers_df = st.session_state.workers.copy()
    worker_stats = worker_stats.merge(
        workers_df[['사번', '이름']], 
        left_on='작업자', 
        right_on='사번', 
        how='left'
    )
    
    # 달성률 계산
    worker_stats['달성률'] = (worker_stats['생산수량'] / worker_stats['목표수량'] * 100).round(2)
    # 불량률 계산
    worker_stats['불량률'] = (worker_stats['불량수량'] / worker_stats['생산수량'] * 100).round(2)
    # 작업효율 계산
    worker_stats['작업효율'] = (worker_stats['달성률'] * (1 - worker_stats['불량률']/100)).round(2)
    
    # 최우수 작업자 선정
    best_achievement = worker_stats.loc[worker_stats['달성률'].idxmax()]
    best_defect = worker_stats.loc[worker_stats['불량률'].idxmin()]
    best_efficiency = worker_stats.loc[worker_stats['작업효율'].idxmax()]
    
    return {
        'achievement': {
            'name': best_achievement['이름'],
            'value': best_achievement['달성률'],
            'previous_value': 0.0
        },
        'defect': {
            'name': best_defect['이름'],
            'value': best_defect['불량률'],
            'previous_value': 0.0
        },
        'efficiency': {
            'name': best_efficiency['이름'],
            'value': best_efficiency['작업효율'],
            'previous_value': 0.0
        }
    }

def prepare_chart_data(data, period_type):
    """차트 데이터 준비"""
    if period_type == "작업자별":
        # 작업자별 데이터 집계
        chart_data = data.groupby('작업자').agg({
            '목표수량': 'sum',
            '생산수량': 'sum',
            '불량수량': 'sum'
        }).reset_index()
        
        # 작업자 사번을 이름으로 변환
        worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
        chart_data['작업자'] = chart_data['작업자'].map(worker_names)
        
    else:
        # 날짜별 데이터 집계
        chart_data = data.groupby('날짜').agg({
            '목표수량': 'sum',
            '생산수량': 'sum',
            '불량수량': 'sum'
        }).reset_index()
        
        # 날짜 형식 변환
        chart_data['날짜'] = pd.to_datetime(chart_data['날짜']).dt.strftime('%Y-%m-%d')
    
    return chart_data

if __name__ == "__main__":
    main()