# 데이터베이스 설계서

# 1. 개요
* 목적: AskHR AI 챗봇 서비스를 위한 데이터베이스 구조 설계
* DBMS 정보: Supabase (PostgreSQL)

# 2. ERD
**논리 ERD**

```
사용자 ||──o< 대화 ||──o< 메시지

사용자          대화            메시지
  사용자이름          제목            역할
                                    내용
```
* 이메일은 Supabase 인증 기능이 처리하여 포함되지 않는다.

**물리 ERD**

```
profiles ||──o< conversations ||──o< messages

profiles                   conversations              messages
  id          uuid   PK      id         uuid    PK      id               uuid   PK
  username    vc(30)         user_id    uuid    FK      conversation_id  uuid   FK
  created_at  tstz           title      vc(100)         role             vc(20)
                             created_at tstz            content          text
                             updated_at tstz            created_at       tstz
```

# 3. 상세 테이블 명세서

## 3.1 `profiles` (사용자 프로필)
시스템 사용자의 기본 프로필 정보를 저장하는 테이블입니다.

| 컬럼명 (Column Name) | 데이터 타입 (Data Type) | PK/FK | Null 허용 | 기본값 (Default) | 제약조건 / 설명 |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **`id`** | `UUID` | **PK** | NOT NULL | `gen_random_uuid()` | 사용자 고유 식별자 |
| **`username`** | `VARCHAR(30)` | - | NOT NULL | - | 사용자 이름 (닉네임) |
| **`created_at`** | `TIMESTAMPTZ` | - | NOT NULL | `CURRENT_TIMESTAMP` | 계정/프로필 생성 일시 |

<br>

## 3.2 `conversations` (대화)
사용자가 진행하는 개별 대화 세션(채팅방) 정보를 저장하는 테이블입니다.

| 컬럼명 (Column Name) | 데이터 타입 (Data Type) | PK/FK | Null 허용 | 기본값 (Default) | 제약조건 / 설명 |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **`id`** | `UUID` | **PK** | NOT NULL | `gen_random_uuid()` | 대화 방 고유 식별자 |
| **`user_id`** | `UUID` | **FK** | NOT NULL | - | 작성자 ID (`profiles.id` 참조, ON DELETE CASCADE) |
| **`title`** | `VARCHAR(100)` | - | NULL | `'새로운 대화'` | 대화 제목 |
| **`created_at`** | `TIMESTAMPTZ` | - | NOT NULL | `CURRENT_TIMESTAMP` | 대화 생성 일시 |
| **`updated_at`** | `TIMESTAMPTZ` | - | NOT NULL | `CURRENT_TIMESTAMP` | 최근 메시지 발송/수정 일시 |

<br>

## 3.3 `messages` (대화 메시지)
특정 대화 세션 내에서 주고받은 개별 메시지 데이터를 저장하는 테이블입니다.

| 컬럼명 (Column Name) | 데이터 타입 (Data Type) | PK/FK | Null 허용 | 기본값 (Default) | 제약조건 / 설명 |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **`id`** | `UUID` | **PK** | NOT NULL | `gen_random_uuid()` | 메시지 고유 식별자 |
| **`conversation_id`** | `UUID` | **FK** | NOT NULL | - | 소속 대화 ID (`conversations.id` 참조, ON DELETE CASCADE) |
| **`role`** | `VARCHAR(20)` | - | NOT NULL | - | 작성 주체 구분 (`'user'`, `'assistant'`, `'system'`) |
| **`content`** | `TEXT` | - | NOT NULL | - | 메시지 본문 내용 |
| **`created_at`** | `TIMESTAMPTZ` | - | NOT NULL | `CURRENT_TIMESTAMP` | 메시지 전송/생성 일시 |

<br>

# 4. 외래키 삭제 정책 (Foreign Key Cascading)
- `conversations.user_id` → `profiles.id` (`ON DELETE CASCADE`)
  - 사용자 탈퇴 시 해당 사용자의 대화 세션도 함께 자동 삭제됩니다.
- `messages.conversation_id` → `conversations.id` (`ON DELETE CASCADE`)
  - 대화 삭제 시 해당 대화에 포함된 메시지들도 함께 자동 삭제됩니다.