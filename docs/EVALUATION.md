# 실행 시연 및 주요 질문 대응

프로젝트를 설명할 때는 **명령 → Git 정보 → AI 입력 → 응답 검증 → 출력** 순서를 먼저 말합니다. 아래 답변은 암기문이 아니라 `main.py`의 함수와 연결된 설명입니다.

## 1. 60초 설명

> `python main.py commit` 또는 `pr`로 시작합니다. `main()`이 옵션을 확인하고 `collect_changes()`가 Git 상태와 staged/unstaged diff를 수집합니다. 변경 내용이 없으면 API 호출 없이 끝납니다. `make_prompt()`는 Git 데이터를 JSON 출력 규칙과 함께 구성하고 `call_ai()`가 환경변수의 Key로 OpenAI REST API에 POST를 1회 보냅니다. 응답을 JSON 객체로 읽은 뒤 `print_result()`가 제목 길이와 PR의 Why/What/How to Test 불릿을 확인해 터미널에 보여줍니다. 이 도구는 커밋이나 PR을 직접 만들지 않고 검토용 초안만 생성합니다.

## 2. 질문과 답변 핵심

| 질문 | 답변의 핵심 논리 | 코드 위치 |
|---|---|---|
| 왜 CLI인가? | 웹 UI 없이 프로젝트 루트에서 바로 실행할 수 있고 명령별 기능을 명확히 구분 | `main`, `argparse` |
| status와 diff는 어떻게 다른가? | status는 파일 상태·목록, diff는 실제 줄 단위 변경 내용 | `collect_changes` |
| 왜 `git diff`가 두 번인가? | 일반 diff는 unstaged, `--cached`는 staged를 다루기 때문 | `collect_changes` |
| 변경이 없으면 어떻게 되나? | status가 비면 안내 후 0으로 종료, API 과금 없음 | `main` |
| 새 파일만 있을 때 왜 생성하지 않나? | Git이 아직 추적하지 않는 파일은 diff 본문이 없어 사실 기반 요약 불가 | `main` |
| API Key를 소스에 두면 안 되는 이유는? | Git에 노출될 수 있어 환경변수에서 실행 시 읽고 키 자체는 출력하지 않음 | `main`, `call_ai` |
| REST API 요청은 어떻게 구성되나? | JSON body, Bearer 인증 헤더, POST, 타임아웃 설정 | `call_ai` |
| 응답은 어떻게 처리하나? | HTTP JSON에서 choices의 content를 꺼내 JSON 객체로 추가 파싱 | `call_ai` |
| temperature 의미는? | 낮으면 표현 다양성 감소 경향, 높으면 다양성 증가; 사실성 보장은 아님 | CLI 옵션 → `call_ai` |
| max_tokens는 글자 수인가? | 토큰 상한이며 글자 수와 다름; API에는 `max_completion_tokens`로 전송 | CLI 옵션 → `call_ai` |
| 프롬프트가 품질을 어떻게 제어하나? | Git 사실만 사용, 명령별 JSON 구조, 길이/테스트 표현 규칙을 명시 | `make_prompt` |
| 커밋 출력 조건은? | 유효한 제목이 반드시 필요, 한 줄·최대 72자, 본문은 선택이라 생략 | `one_line_title`, `print_result` |
| PR 필수 형식은? | 최대 80자 제목과 Why/What/How to Test, 각 섹션 불릿 1개 이상 | `print_result`, `bullets` |
| AI가 조건을 어기면? | 제목은 길이 후처리, 빠진 불릿은 수동 보완 안내, 잘못된 JSON/빈 제목은 오류 | `call_ai`, `one_line_title`, `bullets` |
| API가 실패하면? | HTTP 오류와 연결 오류를 구분하고 원인을 알리는 메시지로 종료 | `call_ai`, `main` |
| 요청이 과도해지지 않나? | 하나의 CLI 실행에서 1회만 요청, 자동 재시도 없음 | `main`, `call_ai` |
| Safe Mode의 한계는? | 일부 비밀값 치환 및 10블록/200줄 제한이지만 모든 민감정보 제거는 불가능 | `safe_diff` |
| 실제 커밋/PR을 자동 생성하나? | 아니요. 터미널에 초안만 출력하고 검토·적용은 사용자 수행 | `print_result`, `main` |
| 검증 증거는? | 임시 Git 저장소 실제 실행 + 모의 API 호출 테스트; 실 API 성공과는 구분 | `tests/test_main.py` |

## 3. 시연용 명령

```bash
# 1. 학습/검증 (API Key·과금 불필요)
python -m unittest discover -s tests -v

# 2. 대상 Git 프로젝트 루트에서 변경 사항 확인
git status --short
git diff
git diff --cached

# 3. API Key가 준비된 경우 실제 초안 생성
python /path/to/codyssey_B3-2/main.py commit --safe-mode
python /path/to/codyssey_B3-2/main.py pr --safe-mode
```

처음에 보여줄 것은 `README.md`의 실행법, 다음은 `main.py` 함수 호출 흐름, 마지막은 테스트 코드입니다. 실제 API Key가 없다면 **API 호출 성공 시연으로 표현하지 말고 모의 응답 테스트임을 분명히 구분**합니다.

## 4. 예외 질문에 대응하기

- **Git 저장소 밖**: `git status`가 실패하므로 `[ERROR] Git 실행 실패`로 종료합니다.
- **파일이 하나도 변하지 않음**: `[INFO] 변경 사항이 없습니다.` 출력 후 종료합니다.
- **Key 미설정**: 변경 diff가 있는 상태에서 `[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다.`를 표시합니다.
- **401 인증 실패**: `[ERROR] AI API HTTP 401: Unauthorized`처럼 오류 상태를 출력합니다.
- **AI가 한 섹션을 빠뜨림**: 해당 헤더와 `수동 보완 필요` 불릿을 유지합니다. 완성된 의미 내용으로 오해하면 안 됩니다.
- **AI 출력이 잘림**: `finish_reason`이 `stop`이 아니면 안전하게 오류로 종료합니다.

## 5. 검증 범위 표시

| 확인 항목 | 근거 | 범위 |
|---|---|---|
| Git staged/unstaged/untracked | 임시 저장소의 실제 Git 명령 | 실 Git 동작 |
| API 요청 헤더·파라미터·횟수 | `unittest.mock`로 Request 검사 | 모의 통신 |
| 응답 형식·예외·Safe Mode | 정상·비정상 데이터 테스트 | 오프라인 검증 |
| 실 OpenAI 통신·실 생성 품질 | 개인 API Key와 실제 과금 환경 필요 | 별도 실사용 검증 필요 |
