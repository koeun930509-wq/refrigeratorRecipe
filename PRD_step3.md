# PRD - Step 3: 사용자 프로필 및 레시피 저장

## 개요
사용자별 프로필을 만들어, 2단계에서 생성된 레시피를 저장하고 나중에 다시 확인할 수 있도록 한다.

## 목표
- 간단한 사용자 식별(로그인 또는 프로필 생성)을 통해 "내 레시피 목록"을 관리할 수 있게 한다.
- 저장한 레시피를 언제든 다시 불러와 볼 수 있다.

## 범위
- 1, 2단계는 OpenRouter API 호출이 핵심이었다면, 3단계는 자체 데이터 저장(DB)이 핵심이다.
- 별도의 외부 인증 서비스(OAuth 등) 없이, 이메일 + 닉네임 정도의 간단한 프로필로 시작한다. (추후 확장 가능하도록 구조만 열어둠)

## 데이터 모델

### User
| 필드 | 타입 | 설명 |
|---|---|---|
| id | integer, PK | 사용자 고유 ID |
| email | string, unique | 로그인/식별용 이메일 |
| nickname | string | 표시 이름 |
| created_at | datetime | 가입일 |

### SavedRecipe
| 필드 | 타입 | 설명 |
|---|---|---|
| id | integer, PK | 저장 레시피 고유 ID |
| user_id | integer, FK -> User.id | 소유자 |
| title | string | 레시피 제목 |
| used_ingredients | JSON | 사용된 재료 목록 |
| additional_ingredients | JSON | 추가로 필요한 재료 |
| steps | JSON | 조리 순서 |
| estimated_time_minutes | integer | 예상 조리 시간 |
| created_at | datetime | 저장일 |

- 저장소: SQLite + Flask-SQLAlchemy (소규모 앱에 적합, 별도 DB 서버 불필요)

## 사용자 흐름
1. 최초 방문 시 이메일과 닉네임으로 간단히 프로필을 생성(또는 기존 이메일로 로그인).
2. 2단계에서 추천받은 레시피 카드에서 "저장" 버튼을 누르면 해당 레시피가 내 프로필에 저장된다.
3. "내 레시피" 페이지에서 저장된 레시피 목록을 최신순으로 확인한다.
4. 저장된 레시피를 클릭하면 상세 조리법을 다시 볼 수 있다.
5. 저장된 레시피를 삭제할 수 있다.

## API 명세

### `POST /api/profile`
프로필 생성 또는 조회(이메일 기준).

**Request**
```json
{ "email": "user@example.com", "nickname": "코은" }
```

**Response (200/201)**
```json
{ "user_id": 1, "email": "user@example.com", "nickname": "코은" }
```

### `POST /api/recipes/save`
레시피 저장. (2단계 응답 결과를 그대로 전달)

**Request**
```json
{
  "user_id": 1,
  "title": "대파 두부 계란찜",
  "used_ingredients": ["계란", "대파", "두부"],
  "additional_ingredients": ["소금", "참기름"],
  "steps": ["두부를 잘게 으깬다.", "계란과 대파를 섞는다.", "찜기에 넣고 15분간 찐다."],
  "estimated_time_minutes": 20
}
```

**Response (201)**
```json
{ "id": 10, "message": "저장되었습니다." }
```

### `GET /api/recipes/saved?user_id=1`
저장된 레시피 목록 조회 (최신순).

**Response (200)**
```json
{
  "recipes": [
    { "id": 10, "title": "대파 두부 계란찜", "created_at": "2026-07-28T10:00:00" }
  ]
}
```

### `GET /api/recipes/saved/<id>`
저장된 레시피 상세 조회.

### `DELETE /api/recipes/saved/<id>`
저장된 레시피 삭제.

## 비기능 요구사항
- 이메일 형식 검증 (서버 측)
- 동일 이메일 재요청 시 기존 프로필 반환 (중복 생성 방지)
- 삭제는 본인 소유(user_id 일치) 레시피만 가능

## 범위 제외 (Out of Scope)
- 비밀번호 기반 정식 인증/세션 관리 (추후 별도 단계로 확장 가능)
- 레시피 공유, 소셜 기능, 평점/리뷰
- 프로필 사진, 알레르기/식단 선호 설정 (필요 시 향후 확장)

## 성공 기준
- 동일 사용자가 여러 레시피를 저장/조회/삭제하는 흐름이 데이터 유실 없이 동작
- 서버 재시작 후에도 저장된 레시피가 유지됨


## 기술 스택
supabase 이용