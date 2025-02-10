# CNC 작업자 KPI 관리 시스템

## 프로젝트 개요
CNC 작업자들의 생산성과 품질을 관리하기 위한 웹 기반 KPI 관리 시스템입니다. 
Streamlit을 사용하여 개발되었으며, Google Sheets API를 통해 데이터를 저장하고 관리합니다.

## 주요 기능

### 1. 사용자 관리
- 관리자/일반 사용자 권한 구분
- 로그인 시스템
- 사용자 등록/삭제 기능
- 비밀번호 암호화 저장

### 2. 생산 실적 관리
- 일일 생산 실적 입력
- 작업자별 실적 조회
- 모델차수 선택 (구글 시트 연동)
- 실적 데이터 수정
- 중복 데이터 관리

### 3. KPI 대시보드
- 종합 대시보드
  - 전체 생산목표달성률
  - 평균 불량률
  - 평균 작업효율
  - 월별 생산 현황 차트

### 4. 리포트 기능
- 일간 리포트
  - 일별 KPI 지표
  - 작업자별 실적
  - 생산량 차트
- 주간 리포트
  - 주간 KPI 지표
  - 작업자별 실적 집계
  - 생산량 추이
- 월간 리포트
  - 월간 KPI 지표
  - 작업자별 월간 실적
  - 월간 생산 추이
- 연간 리포트
  - 연간 KPI 지표
  - 작업자별 연간 실적
  - 월별 생산 추이

### 5. 데이터 백업 및 동기화
- 구글 시트 연동
- 데이터 자동 백업
- 데이터 동기화

## 기술 스택
- Python
- Streamlit
- Google Sheets API
- Plotly
- Pandas
- bcrypt (비밀번호 암호화)

## 데이터 구조

### 1. 작업자 정보
- STT (순번)
- 사번
- 이름
- 부서
- 라인번호

### 2. 생산 실적
- 날짜
- 작업자
- 라인번호
- 모델차수
- 목표수량
- 생산수량
- 불량수량
- 특이사항

### 3. 모델 정보
- STT
- MODEL
- PROCESS

### 4. 사용자 정보
- 이메일
- 비밀번호 (암호화)
- 이름
- 역할 (admin/user)

## 설치 및 실행 방법
1. 필요한 패키지 설치:
```bash
pip install streamlit pandas plotly google-oauth2-tool bcrypt
```

2. Google Sheets API 설정:
- 서비스 계정 생성
- JSON 키 파일 다운로드
- 스프레드시트 공유 설정

3. 애플리케이션 실행:
```bash
streamlit run app.py
```

## 보안 기능
- 비밀번호 bcrypt 암호화
- 관리자/사용자 권한 구분
- 구글 서비스 계정 인증

## 데이터 백업
- 구글 시트 자동 동기화
- 데이터 변경 시 자동 백업
- 수동 백업 기능

## 사용자 인터페이스
- 반응형 웹 디자인
- 직관적인 네비게이션
- 실시간 데이터 시각화
- 사용자 친화적 입력 폼

## GitHub 업로드 방법

1. Git 초기화 및 .gitignore 설정:
```bash
# 프로젝트 디렉토리에서
git init

# .gitignore 파일 생성
echo "# 보안 파일
cnc-op-kpi-management-d552546430e8.json

# 작업공간 설정
CNC OP KPI.code-workspace

# 가상환경
.venv/
__pycache__/

# Python
*.py[cod]
*$py.class
.env
env/
venv/
.streamlit/" > .gitignore
```

2. GitHub 저장소 생성:
- GitHub.com에서 새 저장소 생성
- 저장소 이름: `ALMUSCNCOP`
- 설명 추가 (선택사항)
- Public/Private 선택

3. 로컬 저장소와 GitHub 연결:
```bash
# 원격 저장소 추가
git remote add origin https://github.com/batman3101/ALMUSCNCOP.git



# 파일 스테이징
git add .

# 커밋
git commit -m "Initial commit"

# main 브랜치로 푸시
git branch -M main
git push -u origin main
```

4. 보안 주의사항:
- `cnc-op-kpi-management-d552546430e8.json` 파일은 절대 GitHub에 업로드하지 않음
- 환경 변수나 비밀키는 별도 관리
- .gitignore 파일에 중요 파일 포함 확인

5. 업데이트 및 변경사항 푸시:
```bash
git add .
git commit -m "업데이트 내용 설명"
git push
```

6. 협업 시 브랜치 관리:
```bash
# 새 기능 개발 시 브랜치 생성
git checkout -b feature/new-feature

# 작업 완료 후 main 브랜치로 병합
git checkout main
git merge feature/new-feature
```