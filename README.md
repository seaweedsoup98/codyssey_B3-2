# B3-2 | AI 기반 Git 커밋/PR 초안 생성기

로컬 Git 변경 사항(`git status`, `git diff`)을 읽어 **커밋 메시지 1줄** 또는 **Pull Request 제목·본문**을 만드는 Python CLI입니다. OpenAI Chat Completions REST API를 사용하며, 결과는 터미널에만 출력합니다. 실제 `git commit`, `git push`, PR 생성은 수행하지 않습니다.

## 요구 환경 및 파일

- Python **3.10 이상**, Git, OpenAI API Key, API 이용 가능한 네트워크
- 외부 Python 패키지 설치 **불필요**(표준 라이브러리만 사용)
- `main.py`: CLI / Git 수집 / API 호출 / 출력 검증 및 후처리
- `tests/test_main.py`: Git 및 API 모의 응답 자동 테스트
- `docs/IMPLEMENTATION.md`: 코드 실행 흐름 / 함수별 역할
- `docs/CONCEPTS.md`: 처음 배우는 핵심 개념
- `docs/EVALUATION.md`: 발표·질문 대응 자료

## 설정 및 실행

1. 저장소를 내려받습니다.

   ```bash
   git clone https://github.com/seaweedsoup98/codyssey_B3-2.git
   ```

2. **API Key를 환경변수로 설정**합니다. 소스 코드 또는 Git 파일에 입력하지 않습니다.

   ```bash
   # macOS / Linux (현재 셸에만 적용)
   export AI_API_KEY="발급받은_API_KEY"
   ```

   ```powershell
   # Windows PowerShell (현재 터미널에만 적용)
   $env:AI_API_KEY = "발급받은_API_KEY"
   ```

3. **변경 사항이 있는 Git 프로젝트의 루트 디렉터리**로 이동하여 실행합니다. 아래 `/path/to/`는 실제 경로로 교체합니다. B3-2 저장소 자체를 테스트할 경우, 해당 저장소의 추적 중인 파일을 변경한 다음 `python main.py ...`를 실행해도 됩니다.

   ```bash
   cd /path/to/my-git-project
   python /path/to/codyssey_B3-2/main.py commit --safe-mode
   python /path/to/codyssey_B3-2/main.py pr --safe-mode
   ```

   새 파일만 만든 경우 Git의 diff에 내용이 없으므로 `git add <파일명>`으로 스테이징한 다음 실행합니다. **이 프로그램은 `git add`를 대신 수행하지 않습니다.**

### 옵션

```bash
python /path/to/codyssey_B3-2/main.py commit --model gpt-4o-mini --temperature 0.2 --max-tokens 800 --safe-mode
python /path/to/codyssey_B3-2/main.py pr --model gpt-4o-mini --temperature 0.2 --max-tokens 800 --safe-mode
```

| 옵션 | 기본값 | 역할 |
|---|---|---|
| `commit` / `pr` | 필수 선택 | 커밋 제목 / PR 제목·본문 생성 |
| `--model` | `gpt-4o-mini` | 사용할 AI 모델 |
| `--temperature` | `0.2` | 다양성 조절(0~2); 낮을수록 보수적인 출력 |
| `--max-tokens` | `800` | 생성 토큰 상한(양의 정수); API에 `max_completion_tokens`로 전달 |
| `--safe-mode` | 꺼짐 | 정규식으로 일부 민감 패턴 마스킹 및 전송 diff 제한 |

모델에 따라 `temperature`나 JSON 응답 형식의 지원 여부가 다를 수 있습니다. 기본 모델은 이를 지원하는 모델로 정했습니다. API 호출은 **명령당 1회**이며, 응답 형식 문제에도 유료 재시도를 자동 수행하지 않습니다.

## 출력 예시

아래는 **형식 예시**이며 실제 API 출력 또는 테스트 수행 증빙이 아닙니다.

```text
$ python main.py commit --safe-mode
[INFO] 변경 파일: 1개, diff: 9줄
[INFO] Safe Mode: 민감 패턴 마스킹, 최대 10개 diff 블록/200줄
[INFO] AI API 요청 중... (최대 1회)

--- Commit Message ---
fix: 파일 읽기 예외 처리 보완
[DONE] 초안 생성 완료 (API 호출: 1회, 검토 후 사용)
```

```text
$ python main.py pr --safe-mode
[INFO] 변경 파일: 1개, diff: 9줄
[INFO] Safe Mode: 민감 패턴 마스킹, 최대 10개 diff 블록/200줄
[INFO] AI API 요청 중... (최대 1회)

--- PR Title ---
파일 읽기 예외 처리 보완

--- PR Body ---
## Why
- 파일 처리 중 예외 상황에 대한 대응을 정리합니다.

## What
- 파일 읽기 오류 처리 코드를 수정합니다.

## How to Test
- 존재하지 않는 파일로 실행해 오류 메시지를 확인합니다.

[DONE] 초안 생성 완료 (API 호출: 1회, 검토 후 사용)
```

변경 사항이 없다면 `[INFO] 변경 사항이 없습니다.`를 출력하고 API를 호출하지 않습니다. API Key 누락, 인증·네트워크 실패, JSON 형식 불량은 `[ERROR] ...`를 출력하고 종료 코드 1로 끝납니다. 유효하지 않은 CLI 옵션은 종료 코드 2입니다.

## 보안·비용·제약

- **전송 전에 diff를 직접 확인**하세요. 기본 모드는 diff 전체를 외부 API로 보냅니다.
- `--safe-mode`는 **diff의 처음 10개 파일 블록/200줄**만 보내며 `API_KEY=...` 같은 일부 비밀값, `sk-...` 형태의 키, 이메일 주소를 마스킹합니다. **모든 비밀정보가 차단된다는 보장은 없습니다.** 파일명과 다른 형식의 개인정보 등은 남을 수 있습니다. 민감한 변경은 전송하지 마세요.
- Git에서 추적하는 파일의 **staged 및 unstaged diff**를 포함합니다. 아직 `git add` 하지 않은 새 파일은 상태에는 보이지만 내용이 diff에 포함되지 않습니다. 바이너리 파일도 내용 요약에는 한계가 있습니다.
- 생성된 문구는 AI 초안입니다. 제목을 자동으로 자를 수 있으며, 빈 PR 섹션에는 `(수동 보완 필요)` 표시가 붙습니다. **사실관계와 테스트 방법을 사람이 최종 확인**해야 합니다.
- 호출은 1회씩 과금될 수 있습니다. 잦은 실행을 피하고 `--safe-mode`, 적정 `--max-tokens`를 사용하세요. 실 API 호출 검증에는 본인의 API Key와 과금 가능한 계정이 필요합니다.

## 테스트 및 학습 순서

```bash
cd codyssey_B3-2
python -m unittest discover -s tests -v
python main.py --help
python main.py commit --help
```

테스트는 임시 Git 저장소를 만들고 API 응답을 가짜로 대체하여 실행합니다. **실제 API 과금은 발생하지 않습니다.** 실 API 성공 여부는 별도 연결 테스트가 필요합니다.

학습 순서: [구현 흐름](docs/IMPLEMENTATION.md) → [핵심 개념](docs/CONCEPTS.md) → [질문 대응](docs/EVALUATION.md) → `main.py`와 테스트 코드 대조.

API 문서: [OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat/create)
