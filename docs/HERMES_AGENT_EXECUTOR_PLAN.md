# 실행 에이전트용 작업계획서 (Hermes Agent ONLY)

> **이 문서를 읽는 너(에이전트)에게:**  
> 너는 똑똑하지 않다고 가정한다. 추측하지 마라. 아래 빨간 규칙을 어기면 작업은 실패다.  
> 한 번에 한 스텝만 하고, 스텝마다 검증 명령을 실행하라. 검증이 실패하면 다음 스텝으로 가지 마라.

---

## 0. 너는 지금 무슨 일을 하는가 (왜)

### 문제

멀티 에이전트가 서로 메시지를 보낼 때, 상대가 **툴을 실행하는 도중** 메시지가 도착하면 작은 모델이 흐름을 잃는다. 이걸 Reasoning Drift라고 부른다.

대부분의 프레임워크는 메시지가 오면 **바로 LLM을 한 번 더 호출**한다. 그게 새 “턴”이다. 토큰을 낭비하고, 하던 툴 결과를 망친다.

### 우리가 원하는 것 (0-turn)

1. 다른 에이전트 라디오가 와도 **모델을 부르지 않는다.**
2. 메시지를 버퍼에 쌓는다.
3. **지금 하던 툴이 끝난 뒤**, 그 툴 결과 문자열 뒤에 메시지를 붙인다.
4. 그다음에 Hermes가 **원래 하려던** 다음 모델 호출을 한다.  
   라디오 때문에 생긴 추가 호출은 0회여야 한다. 그래서 0-turn이다.

Hermes에는 이미 비슷한 타이밍이 있다. `busy_input_mode: steer`는 **유저**가 바쁠 때 보낸 글을 다음 툴 뒤에 넣는다.  
우리가 하는 일은 그걸 **다른 에이전트 라디오**에도 열어 주는 것이다. 유저 `/steer`를 바꾸지 마라.

### 왜 hermes-agent 저장소인가

라이브러리 `agent-drift-guard`는 이미 버퍼/포맷터를 갖고 있다.  
**게이트웨이가 바쁜 세션인지 플러그인에게 알려 주지 않으면**, 플러그인이 라디오를 막을 수 없다. 지금은 `GatewayRunner._running_agents`라는 **private** 딕셔너리를 훔쳐봐야 한다.

이 작업의 업스트림 PR은 drift-guard를 Hermes 안에 넣는 것이 **아니다**.  
플러그인이 쓸 수 있는 **일반 API**를 여는 것이다.

- `GatewayRunner.session_is_busy(session_key) -> bool`
- `pre_gateway_dispatch` 훅에 `agent_busy: bool` 전달
- (가능하면) `transform_tool_result`에 안정적인 `session_key`

drift-guard 이름, import, 플러그인 디렉터리를 이 저장소에 만들지 마라.  
NousResearch CONTRIBUTING은 서드파티 플러그인을 `plugins/`에 넣는 PR을 닫는다.

---

## 1. 정체성 카드 (매 응답 전에 소리 내어 확인)

```
작업 저장소  : github.com/kdkrkwhr/hermes-agent
업스트림     : github.com/NousResearch/hermes-agent
베이스 브랜치: upstream/main   (origin/main을 fetch 후 동기화된 것)
새 브랜치    : feat/gateway-session-is-busy
새 PR 대상   : NousResearch/hermes-agent  (base = main)
건드리면 안 됨: feat/native-watch-tool
건드리면 안 됨: GitHub PR #87441
건드리면 안 됨: github.com/kdkrkwhr/agent-drift-guard  (코드 수정 금지)
```

### 잘못된 저장소에서 멈추는 법

터미널에서 **지금 당장** 실행:

```bash
git remote -v
git rev-parse --show-toplevel
git branch --show-current
```

다음 중 **하나라도** 해당하면 **모든 코드 수정을 멈춰라.**

| 보이면 | 의미 | 할 일 |
|---|---|---|
| URL에 `agent-drift-guard` | 라이브러리 레포. 여기가 아니다 | `cd` 해서 hermes-agent로 가라. 여기서 py/md를 고치지 마라 |
| 브랜치가 `feat/native-watch-tool` | 이미 열린 watch PR #87441 | 즉시 `upstream/main`에서 새 브랜치를 다시 따라 |
| 브랜치가 `cursor/...` 이고 루트에 `src/drift_guard` | agent-drift-guard Cloud 작업 트리 | 나가라 |
| `pwd` 끝에 `agent-drift-guard` | 잘못된 루트 | 나가라 |

올바른 루트에는 대략 이런 폴더가 **같이** 있다:

- `gateway/`
- `agent/`
- `hermes_cli/`
- `plugins/`  (이미 있는 공식 플러그인들. 여기에 agent-drift-guard 폴더를 추가하지 마라)
- `CONTRIBUTING.md`

`src/drift_guard/` 가 있으면 잘못된 레포다.

---

## 2. 절대 하지 말 것 (복붙 금지 목록)

1. `kdkrkwhr/agent-drift-guard` 에 커밋하지 마라. 그 레포는 이미 플러그인 실험이 들어가 있고, 이번 작업이 아니다.
2. `plugins/agent-drift-guard/` 를 hermes-agent 안에 만들지 마라. 업스트림이 닫는다.
3. `import drift_guard` 를 hermes-agent 코어에 넣지 마라.
4. `feat/native-watch-tool` 에 커밋/푸시하지 마라. PR #87441이 더러워진다.
5. #87441 을 닫거나, 그 PR에 이 커밋을 얹지 마라.
6. 새 PR의 `--base` 를 `feat/native-watch-tool` 로 두지 마라. `--base main` 이다.
7. 모든 busy 메시지를 skip 하도록 코어 기본 동작을 바꾸지 마라. 유저 `/steer` `/stop` 이 죽는다.
8. idle 멘션을 skip 하는 기본값을 넣지 마라. 봇이 침묵한다.
9. LICENSE, 포맷터 전체 재실행, 무관한 리팩터를 하지 마라.
10. “일단 플러그인을 여기 복사하고 나중에 지우면 되지” 하지 마라. 복사는 실패다.

---

## 3. 성공이 어떤 모습인가

Hermes **코어 테스트**가 다음을 증명하면 성공이다. LLM 키가 필요 없다. 라이브 게이트웨이 불필요.

1. 세션에 running agent가 없으면 `session_is_busy(key) is False`
2. `_running_agents[key] = dummy` 이면 `session_is_busy(key) is True`
3. `pre_gateway_dispatch` 콜백이 kwargs(또는 명시 인자)로 `agent_busy=True/False` 를 받는다
4. 플러그인을 안 심으면 메시지 처리 경로가 지금과 같다 (기본 동작 불변)
5. watch 툴 파일(`feat/native-watch-tool` 관련)이 `git diff` 에 안 나온다

그 다음에야 `gh pr create` 를 한다. 테스트 전에 PR 만들지 마라.

---

## 4. 환경 준비 (그대로 실행)

```bash
# 이미 clone 되어 있으면 그 디렉터리로 이동만
cd /path/to/hermes-agent

git remote -v
# origin 은 kdkrkwhr/hermes-agent 여야 함
# upstream 이 없으면:
git remote add upstream https://github.com/NousResearch/hermes-agent.git

git fetch upstream
git fetch origin

git checkout -b feat/gateway-session-is-busy upstream/main

git branch --show-current
# 반드시 feat/gateway-session-is-busy
# feat/native-watch-tool 이면 잘못됨. 여기서 멈춰라.
```

`kdkrkwhr/hermes-agent` 의 `main` 이 예전에 upstream과 같았더라도, fetch 시점엔 뒤처져 있을 수 있다.  
**항상 `upstream/main`에서 따라.** `origin/main`에서 따지 마라 (behind 일 수 있음).

확인:

```bash
git merge-base --is-ancestor upstream/main HEAD && echo "HEAD contains upstream/main: good"
git diff --stat upstream/main...HEAD
# 아직 커밋 전이면 출력 없음이 정상
```

---

## 5. 코드가 어디에 붙는가 (먼저 찾아라. 추측 금지)

파일을 새로 추측해서 만들지 마라. 검색해서 **기존 함수를 최소로** 고친다.

```bash
rg -n "pre_gateway_dispatch" --type py
rg -n "_running_agents" gateway/run.py | head
rg -n "def invoke_hook" hermes_cli/plugins.py
rg -n "transform_tool_result" --type py | head
```

예상 (라인 번호는 바뀔 수 있음. 이름으로 찾아라):

| 찾을 심볼 | 보통 있는 곳 | 하는 일 |
|---|---|---|
| `_running_agents` | `gateway/run.py` `GatewayRunner` | busy 세션 맵. private. 읽기만, 구조를 바꾸지 마라 |
| `_handle_message` 또는 메시지 디스패치 | `gateway/run.py` | 여기서 `pre_gateway_dispatch` 를 invoke |
| `VALID_HOOKS` | `hermes_cli/plugins.py` | 훅 이름 목록. 새 훅 이름을 만들지 마라. 있는 훅에 인자만 추가 |
| `transform_tool_result` invoke | `model_tools.py` 및/또는 `agent/tool_executor.py` | 툴 결과 치환. session_key가 없으면 추가 후보 |

`pre_gateway_dispatch` 가 **이미** 있으면 훅을 새로 발명하지 마라.  
없는 것은 “busy를 알려 주는 공개 메서드”와 “훅 호출부에 agent_busy 전달”이다.

---

## 6. 구현 명세 (이것만 만들어라)

### 6.1 `GatewayRunner.session_is_busy(self, session_key: str) -> bool`

의미: 이 세션에서 에이전트가 **지금 턴을 수행 중**이면 True.

구현 스케치 (이름은 기존 코드 스타일에 맞춰라. 로직은 이것):

```python
def session_is_busy(self, session_key: str) -> bool:
    if not session_key:
        return False
    running = getattr(self, "_running_agents", None) or {}
    return session_key in running
```

왜 공개 메서드인가: 플러그인이 `_running_agents` 를 직접 읽지 않게 하려고.  
private 맵을 삭제하거나 rename 하지 마라.

### 6.2 `pre_gateway_dispatch` 호출부에 `agent_busy` 전달

지금 훅은 `event, gateway, session_store` 를 받는다.  
**시그니처를 깨지 마라.** 기존 플러그인은 `**kwargs`로 흡수한다. 키워드 인자로 추가하라.

의사 코드:

```python
session_key = ...  # 이 함수가 이미 만드는 키를 재사용. 새로 발명하지 마라
agent_busy = self.session_is_busy(session_key)

results = invoke_hook(
    "pre_gateway_dispatch",
    event=event,
    gateway=self,
    session_store=session_store,
    agent_busy=agent_busy,
    session_key=session_key,
)
```

`invoke_hook` 의 실제 호출 모양을 보고 맞춰라. 인자 순서를 제멋대로 바꾸면 기존 플러그인이 죽는다.

`agent_busy` 기본 의미:

- True: 이 세션에 running agent 있음. 플러그인이 원하면 skip/buffer 가능
- False: idle. 플러그인이 라디오라도 **기본적으로 막지 않는 것이 안전**. 코어는 skip 하지 않음

**코어는 skip 결정을 하지 않는다.** skip은 플러그인 몫이다.  
코어 기본 경로는 오늘과 같아야 한다.

### 6.3 (2순위, 시간이 남고 테스트가 쉬울 때만) `transform_tool_result`에 `session_key`

이미 `session_id` 가 있으면 **중복 필드를 만들지 마라.**  
문서에 `session_id`가 세션 키와 같은지 코드로 확인하라.

```bash
rg -n "invoke_hook\(\s*\"transform_tool_result\"" --type py -A 30
```

`session_id`가 게이트웨이 `session_key`와 다르고, 플러그인이 둘을 못 맞추면  
같은 키워드를 **추가**하되 기존 `session_id`를 제거하지 마라.

확신이 없으면 이 항목은 **하지 마라.** 6.1+6.2만으로 PR이 된다.

---

## 7. 테스트 (TDD. 코드보다 테스트를 먼저 작성)

테스트 파일 위치: Hermes 기존 테스트 옆에.

후보 이름 (충돌하면 숫자만 바꿔라):

- `tests/gateway/test_session_is_busy.py`  (또는 `tests/test_session_is_busy.py`)

기존 테스트가 GatewayRunner를 어떻게 생성하는지 **복사**하라.

```bash
rg -n "GatewayRunner" tests/ | head
```

### 테스트 1: idle이면 False

```python
def test_session_is_busy_false_when_no_running_agent():
    runner = ...  # 기존 테스트와 동일한 생성 방법
    assert runner.session_is_busy("telegram:dm:123") is False
    assert runner.session_is_busy("") is False
```

### 테스트 2: 맵에 있으면 True

```python
def test_session_is_busy_true_when_running_agent_present():
    runner = ...
    key = "telegram:dm:123"
    runner._running_agents[key] = object()  # dummy agent
    assert runner.session_is_busy(key) is True
    assert runner.session_is_busy("other-key") is False
```

### 테스트 3: pre_gateway_dispatch 가 agent_busy 를 받는다

이 테스트가 가장 중요하다. 기존 훅 테스트 패턴을 찾아라.

```bash
rg -n "pre_gateway_dispatch" tests/ | head
```

패턴이 있으면 그걸 복제하고 `agent_busy` assertion만 추가.

없으면 최소 단위:

- 훅 콜백을 등록
- `_running_agents` 를 채운 뒤 디스패치 함수를 호출 (또는 invoke_hook를 직접 호출하는 테스트 더블)
- 콜백이 받은 `kwargs["agent_busy"] is True`

**라이브 Discord/Telegram 을 켜서 테스트하지 마라.** API 키 불필요.

테스트를 실행:

```bash
# 이 레포의 문서/Makefile/CONTRIBUTING이 시키는 테스트 러너를 써라.
# 예 (레포가 pytest면):
python -m pytest tests/gateway/test_session_is_busy.py -q
```

전체 스위트가 너무 길면, 방금 만든 파일 + 기존 `pre_gateway_dispatch` 관련 테스트만 돌려라.  
그다음 기존 steer/interrupt 테스트 파일이 있으면 그것도.

```bash
rg -n "steer|busy_input" tests/ -g '*.py' | head
```

steer 테스트를 깨면 네 변경이 잘못된 것이다. 기본 경로를 바꿨는지 봐라.

---

## 8. 커밋 (너 작업 유저 설정 그대로. 이메일 바꾸지 마라)

한 논리당 한 커밋.

```bash
git add -p   # 무관한 파일이 들어갔는지 눈으로 확인
git diff --cached --stat
# watch, drift_guard, plugins/agent-drift-guard 가 보이면 reset 하고 멈춰라
```

커밋 메시지 예:

```
feat(gateway): expose session_is_busy to plugins

Let pre_gateway_dispatch callbacks see whether the session already
has a running agent, without reading GatewayRunner._running_agents.
No default behavior change when no plugin is loaded.
```

`Co-authored-by: Cursor` 를 넣지 마라. 사용자가 직접 하는 작업이다.

---

## 9. PR (테스트 초록 후에만)

```bash
git push -u origin feat/gateway-session-is-busy

gh pr create --repo NousResearch/hermes-agent \
  --base main \
  --head kdkrkwhr:feat/gateway-session-is-busy \
  --title "feat(gateway): let plugins see whether a session is busy"
```

확인:

```bash
gh pr view --json baseRefName,headRefName,url,title
```

- `baseRefName` 이 `main` 이어야 함
- `headRefName` 이 `feat/gateway-session-is-busy` 이어야 함
- `feat/native-watch-tool` 이면 **즉시 PR을 닫고** 다시 만들어라. 수정하지 말고 새로.

PR 본문 (그대로 써도 됨):

```markdown
## Note

Separate from #87441 (native watch tool). This PR uses branch
`feat/gateway-session-is-busy` off upstream `main`. No overlapping files.

## Why

Plugins that implement observe-but-don't-invoke (buffer inbound radio
while a turn is in a tool call, inject at the next tool result) cannot
currently detect "agent is mid-turn" without reading
`GatewayRunner._running_agents`.

## What

- Add `GatewayRunner.session_is_busy(session_key) -> bool`.
- Pass `agent_busy: bool` (and existing session key) into
  `pre_gateway_dispatch`.

No behavior change when no plugin is loaded.
No third-party plugin is vendored.
No `import drift_guard`.

## Tests

- idle → False
- running agent present → True
- pre_gateway_dispatch callback receives agent_busy

## Out of scope

Installing agent-drift-guard.
Native watch tool (#87441).
Skipping messages in core (plugins decide).
```

Files changed 에 watch 툴, `plugins/agent-drift-guard`, `drift_guard` 가 있으면 PR을 올리지 마라.

---

## 10.  copilot/에이전트가 흔히 하는 실수와 대처

| 실수 | 왜 안 되나 | 대처 |
|---|---|---|
| agent-drift-guard에 플러그인 훅을 더 넣음 | 이번 작업 저장소가 아님 | 그 변경을 revert/커밋하지 말고 hermes-agent로 이동 |
| `plugins/hello-drift/` 를 Hermes에 추가 | CONTRIBUTING이 서드파티 in-tree 플러그인 거절 | 디렉터리 삭제 |
| busy일 때 코어가 무조건 skip | 유저 메시지도 삼킴 | skip 로직 제거. 플래그만 전달 |
| `_running_agents` 를 public 속성으로 rename | 대형 리팩터, 이 PR 범위 밖 | 메서드 래퍼만 |
| #87441 에 커멘트/커밋 | 다른 기능 | 무시 |
| LLM 호출 테스트 | 키 없고 불안정 | mock만 |
| `pre_gateway_dispatch` 훅을 새로 등록 | 이미 있음 | invoke 인자만 추가 |

---

## 11. agent-drift-guard 와의 관계 (읽기 전용)

그 레포는 **이미** `hermes_plugin/agent-drift-guard` 가 있다. 이번 작업에서 고치지 마라.

그 플러그인은 나중에 `session_is_busy` / `agent_busy` 를 쓰도록 바꿀 수 있다.  
그건 **이 PR이 머지된 다음** 별도 작업이다.

로컬에서 플러그인을 심볼릭 링크로 걸어서 수동 확인하는 것은 선택이다. **필수 아님.**  
필수 완료 조건은 섹션 3의 유닛 테스트다.

심볼릭 링크를 하고 싶다면 (선택, Hermes 레포 밖):

```bash
# 이 명령은 hermes-agent git 커밋에 넣지 마라
ln -s /path/to/agent-drift-guard/hermes_plugin/agent-drift-guard \
      ~/.hermes/plugins/agent-drift-guard
```

---

## 12. 체크리스트 (PR 직전 소리 내어 읽기)

- [ ] `git remote -v` 에 hermes-agent (kdkrkwhr) 가 origin
- [ ] 브랜치 이름이 `feat/gateway-session-is-busy`
- [ ] `git merge-base --is-ancestor upstream/main HEAD` 성공
- [ ] `git diff --stat upstream/main` 에 watch 파일 없음
- [ ] `plugins/agent-drift-guard` 없음
- [ ] `drift_guard` 문자열 없음 (`rg drift_guard` 결과 네가 추가한 줄 0)
- [ ] `session_is_busy` 테스트 통과
- [ ] 훅에 `agent_busy` 전달 테스트 통과
- [ ] 플러그인 없을 때 기본 디스패치 불변
- [ ] PR base = `main`, head = `kdkrkwhr:feat/gateway-session-is-busy`
- [ ] PR 본문에 “Separate from #87441” 문구 있음

하나라도 체크 못하면 `gh pr create` 하지 마라.

---

## 13. 한 줄로 다시

**Hermes 코어에 “이 세션 바빠?”를 물어보는 공개 구명을 달고, 그걸 `pre_gateway_dispatch`에 넘겨라. drift-guard를 넣지 마라. watch PR을 건드리지 마라. 테스트 없이 PR 하지 마라.**
