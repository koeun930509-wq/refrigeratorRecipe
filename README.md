# 냉장고 재료 인식 & 레시피 추천 앱

냉장고 사진을 올리면 재료를 인식하고, 그 재료로 만들 수 있는 레시피를 추천받아 저장할 수 있는 Flask 웹 애플리케이션입니다. OpenRouter의 무료 LLM 모델을 이용합니다.

## 기술 스택

- Python / Flask
- Flask-SQLAlchemy + Supabase(Postgres) — 사용자 프로필, 저장 레시피 저장소
- OpenRouter API — 이미지 인식(`google/gemma-4-26b-a4b-it:free`), 레시피 생성(`openai/gpt-oss-20b:free`)
- Vanilla HTML/JS (프레임워크 없음)

## 기능 (3단계)

### 1단계 — 냉장고 사진 재료 인식
- 이미지를 업로드하면 base64로 인코딩해 OpenRouter 비전 모델에 전달, 인식된 재료 목록을 JSON으로 반환
- 인식 결과는 화면에서 직접 추가/삭제 가능
- `POST /api/recognize-ingredients`

### 2단계 — 레시피 생성
- 재료 목록을 텍스트 모델에 전달해 레시피 3개 추천 (제목, 사용 재료, 추가 필요 재료, 조리 순서, 예상 시간)
- 모델 응답이 깨지거나 형식이 안 맞으면 1회 재시도, 그래도 유효한 레시피가 없으면 422 반환
- `POST /api/generate-recipes`

### 3단계 — 사용자 프로필 & 레시피 저장
- 이메일 + 닉네임으로 간단한 프로필 생성/로그인 (localStorage로 재방문 시 자동 로그인 유지, 로그아웃 가능)
- 레시피 카드에서 저장, "내 레시피" 목록에서 조회/삭제
- `POST /api/profile`, `POST /api/recipes/save`, `GET /api/recipes/saved`, `GET /api/recipes/saved/<id>`, `DELETE /api/recipes/saved/<id>`

## 프로젝트 구조

```
app.py                  Flask 앱, API 엔드포인트, DB 모델
templates/index.html    프론트엔드 (업로드/인식/레시피/프로필/저장 UI)
requirements.txt        의존성 목록
.env / .env.example     환경 변수 (API 키, DB 연결 문자열)
PRD_step1~3.md          단계별 요구사항 정의서
```

## 환경 변수 (`.env`)

```
OPENROUTER_API_KEY=       # OpenRouter API 키
SUPABASE_DB_URL=          # Supabase Postgres 연결 문자열 (비어있으면 로컬 SQLite로 자동 폴백)
```

`SUPABASE_DB_URL`은 Supabase 대시보드의 **Connect → Direct → Session pooler → URI** 값을 사용합니다. Direct connection(IPv6 전용) 주소는 IPv4 전용 네트워크에서 연결이 안 될 수 있어 Session pooler를 권장합니다.

## 실행 방법

```
pip install -r requirements.txt
python app.py
```

브라우저에서 `http://127.0.0.1:5000` 접속.

## 알려진 제한사항

- 이미지 업로드는 5MB 이하만 허용 (초과 시 클라이언트에서 리사이즈 필요)
- 무료 모델 특성상 응답 속도가 느리고(수십 초~2분), 가끔 형식이 깨지거나 텍스트에 오탈자/이상 문자가 섞일 수 있음 — 레시피 필드 유효성 검증 및 재시도 로직으로 최소화
- AVIF 등 일부 이미지 포맷은 서버에서 별도 변환 없이 그대로 모델에 전달되므로 인식이 안 될 수 있음
