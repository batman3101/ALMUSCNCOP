import streamlit as st
import pandas as pd
from datetime import datetime
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
    st.session_state.clear_users = True
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
    
    with st.form("login_form"):
        email = st.text_input("이메일")
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인")
        
        if submitted:
            user = st.session_state.users[st.session_state.users['이메일'] == email]
            if len(user) > 0 and bcrypt.checkpw(password.encode('utf-8'), 
                                               user.iloc[0]['비밀번호'].encode('utf-8')):
                st.session_state.authenticated = True
                st.session_state.user_role = user.iloc[0]['권한']
                st.success("로그인 성공!")
                st.rerun()
            else:
                st.error("이메일 또는 비밀번호가 잘못되었습니다.")

def init_admin_account():
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
        st.session_state.clear_users = False
        return True
    return False

def sync_workers_with_sheets():
    try:
        sheets = init_google_sheets()
        
        # 구글 시트에서 작업자 데이터 읽기
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range='worker!A2:E'  # A2부터 E열까지
        ).execute()
        
        values = result.get('values', [])
        if values:
            # 구글 시트 데이터를 DataFrame으로 변환
            workers_df = pd.DataFrame(values, columns=['STT', '사번', '이름', '부서', '라인번호'])
            # 숫자로 된 STT를 2자리 문자열로 변환 (예: 1 -> "01")
            workers_df['STT'] = workers_df['STT'].astype(str).str.zfill(2)
            # 세션 스테이트 업데이트
            st.session_state.workers = workers_df
            return True
        return False
    except Exception as e:
        st.error(f"구글 시트 동기화 중 오류 발생: {str(e)}")
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
        
        # 구글 시트에서 생산 데이터 읽기
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range='production!A2:H'  # A2부터 H열까지
        ).execute()
        
        values = result.get('values', [])
        if values:
            # 구글 시트 데이터를 DataFrame으로 변환
            production_df = pd.DataFrame(values, columns=[
                '날짜', '작업자', '라인번호', '모델차수', '목표수량', '생산수량', '불량수량', '특이사항'
            ])
            
            # 날짜 형식 변환
            production_df['날짜'] = pd.to_datetime(production_df['날짜']).dt.strftime('%Y-%m-%d')
            
            # 작업자 이름을 사번으로 변환
            worker_ids = st.session_state.workers.set_index('이름')['사번'].to_dict()
            production_df['작업자'] = production_df['작업자'].map(worker_ids)
            
            # 숫자 데이터 변환
            production_df['목표수량'] = pd.to_numeric(production_df['목표수량'], errors='coerce')
            production_df['생산수량'] = pd.to_numeric(production_df['생산수량'], errors='coerce')
            production_df['불량수량'] = pd.to_numeric(production_df['불량수량'], errors='coerce')
            
            # 세션 스테이트 업데이트
            st.session_state.daily_records = production_df
            return True
        return False
    except Exception as e:
        st.error(f"구글 시트 동기화 중 오류 발생: {str(e)}")
        return False

def backup_production_to_sheets():
    try:
        if len(st.session_state.daily_records) > 0:
            sheets = init_google_sheets()
            
            # 데이터 준비
            backup_data = st.session_state.daily_records.copy()
            
            # 날짜 형식 변환 (datetime을 문자열로)
            backup_data['날짜'] = pd.to_datetime(backup_data['날짜']).dt.strftime('%Y-%m-%d')
            
            # 작업자 사번을 이름으로 변환
            worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
            backup_data['작업자'] = backup_data['작업자'].map(worker_names)
            
            # DataFrame을 리스트로 변환
            values = [backup_data.columns.tolist()] + backup_data.values.tolist()
            
            # 기존 데이터 삭제
            sheets.values().clear(
                spreadsheetId=SPREADSHEET_ID,
                range='production!A1:Z'
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
            
        return False
    except Exception as e:
        st.error(f"구글 시트 백업 중 오류 발생: {str(e)}")
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
    fig = go.Figure()
    
    # 목표수량 - 하늘색 막대
    fig.add_trace(go.Bar(
        name='목표수량',
        x=data[x_col],
        y=data['목표수량'],
        marker_color='skyblue'
    ))
    
    # 생산수량 - 청색 선
    fig.add_trace(go.Scatter(
        name='생산수량',
        x=data[x_col],
        y=data['생산수량'],
        line=dict(color='blue')
    ))
    
    # 불량수량 - 빨간색 선
    fig.add_trace(go.Scatter(
        name='불량수량',
        x=data[x_col],
        y=data['불량수량'],
        line=dict(color='red')
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title=x_col,
        yaxis_title='수량',
        barmode='group'
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
    # 관리자 계정 초기화
    if init_admin_account():
        st.success("관리자 계정이 생성되었습니다.")
    
    if not st.session_state.authenticated:
        show_login()
        return

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
    
    # 모델차수 데이터 동기화
    if len(st.session_state.models) == 0:
        sync_models_with_sheets()
    
    tab1, tab2, tab3 = st.tabs(["신규 입력", "데이터 수정", "중복 데이터 관리"])
    
    with tab1:
        with st.form("daily_production_form"):
            date = st.date_input("작업일자", datetime.now())
            
            # 작업자 선택 드롭다운
            if len(st.session_state.workers) > 0:
                worker_options = st.session_state.workers.set_index('사번')['이름'].to_dict()
                worker_name = st.selectbox(
                    "작업자",
                    options=list(worker_options.values()),
                    format_func=lambda x: x
                )
                worker_id = [k for k, v in worker_options.items() if v == worker_name][0]
                
                # 선택된 작업자의 라인번호 가져오기
                worker_data = st.session_state.workers[st.session_state.workers['사번'] == worker_id].iloc[0]
                
                # 라인번호 선택
                all_line_numbers = st.session_state.workers['라인번호'].unique().tolist()
                line_number = st.selectbox(
                    "라인번호",
                    options=all_line_numbers,
                    index=all_line_numbers.index(worker_data['라인번호']) if worker_data['라인번호'] in all_line_numbers else 0
                )
            else:
                worker_name = st.selectbox("작업자", options=[])
                worker_id = None
                line_number = st.text_input("라인번호")
            
            # 모델차수 선택 드롭다운
            if len(st.session_state.models) > 0:
                # MODEL과 PROCESS를 조합하여 모델차수 옵션 생성
                model_options = [f"{row['MODEL']}-{row['PROCESS']}" 
                               for _, row in st.session_state.models.iterrows()]
                model = st.selectbox("모델차수", options=sorted(set(model_options)))
            else:
                model = st.text_input("모델차수")
            
            target_qty = st.number_input("목표수량", min_value=0)
            produced_qty = st.number_input("생산수량", min_value=0)
            defect_qty = st.number_input("불량수량", min_value=0)
            notes = st.text_area("특이사항")
            
            submitted = st.form_submit_button("저장")
            
            if submitted:
                # 날짜를 문자열로 변환
                date_str = date.strftime('%Y-%m-%d')
                
                new_record = pd.DataFrame({
                    '날짜': [date_str],  # 문자열 형식으로 저장
                    '작업자': [worker_id],
                    '라인번호': [line_number],
                    '모델차수': [model],
                    '목표수량': [target_qty],
                    '생산수량': [produced_qty],
                    '불량수량': [defect_qty],
                    '특이사항': [notes]
                })
                st.session_state.daily_records = pd.concat([st.session_state.daily_records, new_record], ignore_index=True)
                
                # 구글 시트에 자동 백업
                if backup_production_to_sheets():
                    st.success("생산 실적이 저장되고 백업되었습니다.")
                else:
                    st.warning("생산 실적이 저장되었으나 백업 중 오류가 발생했습니다.")

    with tab2:
        st.subheader("기존 데이터 수정")
        
        if len(st.session_state.daily_records) > 0:
            # 날짜 선택
            edit_date = st.date_input("수정할 날짜 선택", datetime.now(), key="edit_date")
            
            # 선택된 날짜의 데이터 필터링
            daily_data = st.session_state.daily_records[
                pd.to_datetime(st.session_state.daily_records['날짜']).dt.date == edit_date
            ]
            
            if len(daily_data) > 0:
                # 수정할 데이터 선택
                worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
                daily_data['작업자명'] = daily_data['작업자'].map(worker_names)
                
                # 수정할 레코드 선택
                edit_records = st.dataframe(
                    daily_data[['작업자명', '라인번호', '모델차수', '목표수량', '생산수량', '불량수량', '특이사항']],
                    hide_index=True
                )
                
                # 수정할 작업자 선택
                selected_worker = st.selectbox(
                    "수정할 작업자 선택",
                    options=daily_data['작업자명'].unique()
                )
                
                # 선택된 작업자의 데이터
                selected_record = daily_data[daily_data['작업자명'] == selected_worker].iloc[0]
                
                with st.form("edit_production_form"):
                    # 라인번호 선택
                    all_line_numbers = st.session_state.workers['라인번호'].unique().tolist()
                    line_number = st.selectbox(
                        "라인번호",
                        options=all_line_numbers,
                        index=all_line_numbers.index(selected_record['라인번호']) if selected_record['라인번호'] in all_line_numbers else 0,
                        key="edit_line"
                    )
                    
                    # 모델차수 선택
                    if len(st.session_state.models) > 0:
                        model_options = [f"{row['MODEL']}-{row['PROCESS']}" 
                                       for _, row in st.session_state.models.iterrows()]
                        model = st.selectbox("모델차수", 
                                           options=sorted(set(model_options)),
                                           key="edit_model")
                    else:
                        model = st.text_input("모델차수")
                    
                    # 기존 데이터를 기본값으로 설정
                    target_qty = st.number_input("목표수량", min_value=0, value=int(selected_record['목표수량']))
                    produced_qty = st.number_input("생산수량", min_value=0, value=int(selected_record['생산수량']))
                    defect_qty = st.number_input("불량수량", min_value=0, value=int(selected_record['불량수량']))
                    notes = st.text_area("특이사항", value=selected_record['특이사항'] if pd.notna(selected_record['특이사항']) else "")
                    
                    update_submitted = st.form_submit_button("수정")
                    
                    if update_submitted:
                        # 데이터 수정
                        mask = (
                            (st.session_state.daily_records['날짜'].astype(str) == edit_date.strftime('%Y-%m-%d')) &
                            (st.session_state.daily_records['작업자'] == selected_record['작업자'])
                        )
                        
                        st.session_state.daily_records.loc[mask, '라인번호'] = line_number
                        st.session_state.daily_records.loc[mask, '모델차수'] = model
                        st.session_state.daily_records.loc[mask, '목표수량'] = target_qty
                        st.session_state.daily_records.loc[mask, '생산수량'] = produced_qty
                        st.session_state.daily_records.loc[mask, '불량수량'] = defect_qty
                        st.session_state.daily_records.loc[mask, '특이사항'] = notes
                        
                        # 구글 시트 백업
                        if backup_production_to_sheets():
                            st.success("데이터가 성공적으로 수정되었습니다.")
                        else:
                            st.warning("데이터가 수정되었으나 백업 중 오류가 발생했습니다.")
                        
                        # 화면 새로고침
                        st.rerun()
            else:
                st.info(f"{edit_date} 날짜의 생산 데이터가 없습니다.")
        else:
            st.info("수정할 생산 실적이 없습니다.")

    with tab3:
        st.subheader("중복 데이터 관리")
        
        if len(st.session_state.daily_records) > 0:
            # 날짜 선택
            check_date = st.date_input("확인할 날짜 선택", datetime.now(), key="check_date")
            
            # 선택된 날짜의 데이터 필터링
            daily_data = st.session_state.daily_records[
                pd.to_datetime(st.session_state.daily_records['날짜']).dt.date == check_date
            ]
            
            if len(daily_data) > 0:
                # 작업자 이름 매핑
                worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
                daily_data['작업자명'] = daily_data['작업자'].map(worker_names)
                
                # 중복 데이터 확인
                duplicates = daily_data[daily_data.duplicated(subset=['작업자'], keep=False)]
                
                if len(duplicates) > 0:
                    st.warning("다음 작업자의 데이터가 중복되어 있습니다:")
                    
                    # 중복 데이터 표시
                    st.dataframe(
                        duplicates[['작업자명', '라인번호', '모델차수', '목표수량', '생산수량', '불량수량', '특이사항']],
                        hide_index=True
                    )
                    
                    # 중복 데이터 처리
                    duplicate_workers = duplicates['작업자명'].unique()
                    selected_worker = st.selectbox(
                        "삭제할 중복 데이터의 작업자 선택",
                        options=duplicate_workers
                    )
                    
                    if st.button("선택한 작업자의 중복 데이터 삭제"):
                        # 작업자 ID 찾기
                        worker_id = [k for k, v in worker_names.items() if v == selected_worker][0]
                        
                        # 중복 데이터 중 마지막 항목을 제외한 나머지 삭제
                        mask = (
                            (st.session_state.daily_records['날짜'].astype(str) == check_date.strftime('%Y-%m-%d')) &
                            (st.session_state.daily_records['작업자'] == worker_id)
                        )
                        duplicate_indices = st.session_state.daily_records[mask].index[:-1]
                        
                        # 데이터 삭제
                        st.session_state.daily_records = st.session_state.daily_records.drop(duplicate_indices)
                        
                        # 구글 시트 백업
                        if backup_production_to_sheets():
                            st.success(f"{selected_worker}의 중복 데이터가 성공적으로 삭제되었습니다.")
                        else:
                            st.warning("데이터는 삭제되었으나 백업 중 오류가 발생했습니다.")
                        
                        # 화면 새로고침
                        st.rerun()
                else:
                    st.success("이 날짜에는 중복된 데이터가 없습니다.")
            else:
                st.info(f"{check_date} 날짜의 생산 데이터가 없습니다.")
        else:
            st.info("등록된 생산 실적이 없습니다.")

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
    st.title("📋 월간 리포트")
    
    if len(st.session_state.daily_records) > 0:
        # 날짜 선택
        current_date = datetime.now()
        year = st.selectbox("연도 선택", 
                           options=range(current_date.year-2, current_date.year+1),
                           index=2)
        month = st.selectbox("월 선택", 
                           options=range(1, 13),
                           index=current_date.month-1)
        
        # 작업자 선택 드롭다운 추가
        worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
        all_workers = ['전체'] + list(worker_names.values())
        selected_worker = st.selectbox("작업자 선택", options=all_workers)
        
        # 선택된 월의 데이터 필터링
        month_str = f"{year}-{month:02d}"
        monthly_data = st.session_state.daily_records[
            pd.to_datetime(st.session_state.daily_records['날짜']).dt.strftime('%Y-%m') == month_str
        ]
        
        # 선택된 작업자에 대한 필터링
        if selected_worker != '전체':
            worker_id = [k for k, v in worker_names.items() if v == selected_worker][0]
            monthly_data = monthly_data[monthly_data['작업자'] == worker_id]
        
        if len(monthly_data) > 0:
            # 이전 월 데이터 가져오기
            current_date = pd.to_datetime(month_str + '-01')
            previous_date = (current_date - pd.DateOffset(months=1))
            previous_month = previous_date.strftime('%Y-%m')
            
            previous_data = st.session_state.daily_records[
                pd.to_datetime(st.session_state.daily_records['날짜']).dt.strftime('%Y-%m') == previous_month
            ].copy()  # 복사본 생성
            
            # 최우수 KPI 대시보드 표시
            if len(previous_data) > 0:
                show_best_kpi_dashboard(monthly_data, previous_data, "월간")
            else:
                show_best_kpi_dashboard(monthly_data, None, "월간")
            
            st.divider()  # 구분선 추가
            
            st.subheader(f"기간: {month_str}")
            
            # KPI 계산
            achievement_rate, defect_rate, efficiency_rate = calculate_kpi(monthly_data)
            
            st.divider()  # 구분선 추가
            
            # KPI 지표 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("월간 생산목표달성률", f"{achievement_rate:.2f}%")
            with col2:
                st.metric("월간 불량률", f"{defect_rate:.2f}%")
            with col3:
                st.metric("월간 작업효율", f"{efficiency_rate:.2f}%")
            
            st.divider()  # 구분선 추가
            
            # 작업자별 실적 표시
            st.subheader("작업자별 실적")
            
            # 작업자 이름 매핑
            worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
            monthly_data['작업자명'] = monthly_data['작업자'].map(worker_names)
            
            # 작업자별 집계 데이터 계산
            worker_summary = monthly_data.groupby('작업자명').agg({
                '목표수량': 'sum',
                '생산수량': 'sum',
                '불량수량': 'sum'
            }).reset_index()
            
            # 작업자별 KPI 계산
            worker_summary = calculate_worker_kpi(worker_summary)
            
            # 데이터 표시
            st.dataframe(worker_summary, hide_index=True)
            
            st.divider()  # 구분선 추가
            
            # 작업자별 생산량 차트로 변경
            fig = create_production_chart(worker_summary, '작업자명', '작업자별 생산 현황')
            st.plotly_chart(fig)
            
        else:
            st.info(f"{month_str} 월의 생산 데이터가 없습니다.")
    else:
        st.info("등록된 생산 실적이 없습니다.")

def show_yearly_report():
    st.title("📈 연간 리포트")
    
    if len(st.session_state.daily_records) > 0:
        # 연도 선택
        year = st.selectbox(
            "연도 선택", 
            options=pd.to_datetime(st.session_state.daily_records['날짜']).dt.year.unique()
        )
        
        # 작업자 선택 드롭다운 추가
        worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
        all_workers = ['전체'] + list(worker_names.values())
        selected_worker = st.selectbox("작업자 선택", options=all_workers)
        
        # 연간 데이터 필터링
        yearly_data = st.session_state.daily_records[
            pd.to_datetime(st.session_state.daily_records['날짜']).dt.year == year
        ]
        
        # 선택된 작업자에 대한 필터링
        if selected_worker != '전체':
            worker_id = [k for k, v in worker_names.items() if v == selected_worker][0]
            yearly_data = yearly_data[yearly_data['작업자'] == worker_id]
        
        if len(yearly_data) > 0:
            # 이전 연도 데이터 가져오기 및 KPI 대시보드 표시
            previous_data = st.session_state.daily_records[
                pd.to_datetime(st.session_state.daily_records['날짜']).dt.year == year - 1
            ]
            show_best_kpi_dashboard(yearly_data, previous_data, "연간")
            
            st.divider()  # 구분선 추가
            
            st.subheader(f"기간: {year}년")
            
            # KPI 계산
            achievement_rate, defect_rate, efficiency_rate = calculate_kpi(yearly_data)
            
            st.divider()  # 구분선 추가
            
            # KPI 지표 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("연간 생산목표달성률", f"{achievement_rate:.2f}%")
            with col2:
                st.metric("연간 불량률", f"{defect_rate:.2f}%")
            with col3:
                st.metric("연간 작업효율", f"{efficiency_rate:.2f}%")
            
            st.divider()  # 구분선 추가
            
            # 작업자별 실적 표시
            st.subheader("작업자별 실적")
            
            # 작업자 이름 매핑
            worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
            yearly_data['작업자명'] = yearly_data['작업자'].map(worker_names)
            
            # 작업자별 집계 데이터 계산
            worker_summary = yearly_data.groupby('작업자명').agg({
                '목표수량': 'sum',
                '생산수량': 'sum',
                '불량수량': 'sum'
            }).reset_index()
            
            # 작업자별 KPI 계산
            worker_summary = calculate_worker_kpi(worker_summary)
            
            # 데이터 표시
            st.dataframe(worker_summary, hide_index=True)
            
            # 월별 추이 차트
            monthly_trend = yearly_data.groupby(
                pd.to_datetime(yearly_data['날짜']).dt.strftime('%Y-%m')
            ).agg({
                '생산수량': 'sum',
                '목표수량': 'sum',
                '불량수량': 'sum'
            }).reset_index()
            
            fig = create_production_chart(monthly_trend, '날짜', '월별 생산 현황')
            st.plotly_chart(fig)
            
        else:
            st.info(f"{year}년의 생산 데이터가 없습니다.")
    else:
        st.info("등록된 생산 실적이 없습니다.")

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
    st.title("📅 일간 리포트")
    
    if len(st.session_state.daily_records) > 0:
        # 날짜 선택
        report_date = st.date_input("조회할 날짜 선택", datetime.now())
        
        # 작업자 선택 드롭다운 추가
        worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
        all_workers = ['전체'] + list(worker_names.values())
        selected_worker = st.selectbox("작업자 선택", options=all_workers)
        
        # 선택된 날짜의 데이터 필터링
        daily_data = st.session_state.daily_records[
            pd.to_datetime(st.session_state.daily_records['날짜']).dt.date == report_date
        ]
        
        # 선택된 작업자에 대한 필터링
        if selected_worker != '전체':
            worker_id = [k for k, v in worker_names.items() if v == selected_worker][0]
            daily_data = daily_data[daily_data['작업자'] == worker_id]
        
        if len(daily_data) > 0:
            # 전일 데이터 가져오기
            previous_date = report_date - pd.Timedelta(days=1)
            previous_data = st.session_state.daily_records[
                pd.to_datetime(st.session_state.daily_records['날짜']).dt.date == previous_date
            ]
            
            # 최우수 KPI 대시보드 표시
            show_best_kpi_dashboard(daily_data, previous_data, "일간")
            
            st.divider()  # 구분선 추가
            
            # KPI 계산
            achievement_rate, defect_rate, efficiency_rate = calculate_kpi(daily_data)
            
            st.divider()  # 구분선 추가
            
            # KPI 지표 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("생산목표달성률", f"{achievement_rate:.2f}%")
            with col2:
                st.metric("불량률", f"{defect_rate:.2f}%")
            with col3:
                st.metric("작업효율", f"{efficiency_rate:.2f}%")
            
            st.divider()  # 구분선 추가
            
            # 작업자별 실적 표시
            st.subheader("작업자별 실적")
            
            # 작업자 이름 매핑
            worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
            daily_data['작업자명'] = daily_data['작업자'].map(worker_names)
            
            # 데이터 표시
            display_cols = ['작업자명', '라인번호', '모델차수', '목표수량', '생산수량', '불량수량', '특이사항']
            st.dataframe(daily_data[display_cols], hide_index=True)
            
            st.divider()  # 구분선 추가
            
            # 생산량 차트
            fig = create_production_chart(daily_data, '작업자명')
            st.plotly_chart(fig)
            
        else:
            st.info(f"{report_date} 날짜의 생산 데이터가 없습니다.")
    else:
        st.info("등록된 생산 실적이 없습니다.")

def show_weekly_report():
    st.title("📆 주간 리포트")
    
    if len(st.session_state.daily_records) > 0:
        # 날짜 선택
        report_date = st.date_input("조회할 주의 시작일 선택", datetime.now())
        
        # 작업자 선택 드롭다운 추가
        worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
        all_workers = ['전체'] + list(worker_names.values())
        selected_worker = st.selectbox("작업자 선택", options=all_workers)
        
        # 선택된 주의 시작일과 종료일 계산
        start_of_week = report_date - pd.Timedelta(days=report_date.weekday())
        end_of_week = start_of_week + pd.Timedelta(days=6)
        
        # 주간 데이터 필터링
        weekly_data = st.session_state.daily_records[
            (pd.to_datetime(st.session_state.daily_records['날짜']).dt.date >= start_of_week) &
            (pd.to_datetime(st.session_state.daily_records['날짜']).dt.date <= end_of_week)
        ]
        
        # 선택된 작업자에 대한 필터링
        if selected_worker != '전체':
            worker_id = [k for k, v in worker_names.items() if v == selected_worker][0]
            weekly_data = weekly_data[weekly_data['작업자'] == worker_id]
        
        if len(weekly_data) > 0:
            # 이전 주 데이터 가져오기
            previous_start = start_of_week - pd.Timedelta(days=7)
            previous_end = previous_start + pd.Timedelta(days=6)
            previous_data = st.session_state.daily_records[
                (pd.to_datetime(st.session_state.daily_records['날짜']).dt.date >= previous_start) &
                (pd.to_datetime(st.session_state.daily_records['날짜']).dt.date <= previous_end)
            ]
            
            # 최우수 KPI 대시보드 표시
            show_best_kpi_dashboard(weekly_data, previous_data, "주간")
            
            st.divider()  # 구분선 추가
            
            st.subheader(f"기간: {start_of_week.strftime('%Y-%m-%d')} ~ {end_of_week.strftime('%Y-%m-%d')}")
            
            # KPI 계산
            achievement_rate, defect_rate, efficiency_rate = calculate_kpi(weekly_data)
            
            # KPI 지표 표시
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("주간 생산목표달성률", f"{achievement_rate:.2f}%")
            with col2:
                st.metric("주간 불량률", f"{defect_rate:.2f}%")
            with col3:
                st.metric("주간 작업효율", f"{efficiency_rate:.2f}%")
            
            st.divider()  # 구분선 추가
            
            # 작업자별 실적 표시
            st.subheader("작업자별 실적")
            
            # 작업자 이름 매핑
            worker_names = st.session_state.workers.set_index('사번')['이름'].to_dict()
            weekly_data['작업자명'] = weekly_data['작업자'].map(worker_names)
            
            # 작업자별 집계 데이터 계산
            worker_summary = weekly_data.groupby('작업자명').agg({
                '목표수량': 'sum',
                '생산수량': 'sum',
                '불량수량': 'sum'
            }).reset_index()
            
            # 작업자별 KPI 계산
            worker_summary = calculate_worker_kpi(worker_summary)
            
            # 데이터 표시
            st.dataframe(worker_summary, hide_index=True)
            
            st.divider()  # 구분선 추가
            
            # 작업자별 생산량 차트로 변경
            fig = create_production_chart(worker_summary, '작업자명', '작업자별 생산 현황')
            st.plotly_chart(fig)
            
        else:
            st.info(f"{start_of_week.strftime('%Y-%m-%d')} ~ {end_of_week.strftime('%Y-%m-%d')} 기간의 생산 데이터가 없습니다.")
    else:
        st.info("등록된 생산 실적이 없습니다.")

def sync_models_with_sheets():
    """구글 시트에서 모델차수 데이터 동기화"""
    try:
        sheets = init_google_sheets()
        
        # 구글 시트에서 모델차수 데이터 읽기
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range='model!A2:D'  # A2부터 D열까지
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

if __name__ == "__main__":
    main()