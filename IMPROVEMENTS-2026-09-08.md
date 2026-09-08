# MyBookshelf v1.2.81 개선 기록

## v1.2.82 추가 변경 — 모델 목록에서 선택

- 사용자 요청으로 모델 ID 직접 입력칸을 제거하고 선택 목록만 제공.
- Codex의 `models_cache.json`에서 표시 가능한 모델을 자동으로 읽어 선택 목록에 반영. 숨김 모델은 제외하며 기존 저장된 설정은 보존.
- Claude는 Sonnet·Opus·Haiku 및 CLI 기본 설정 선택. 모델명은 알아보기 쉬운 표시명으로 제공.
- 실제 계정 권한은 기존 ‘연결·모델 확인’ 버튼으로 확인 가능. 캐시가 없거나 깨져도 CLI 기본 설정 선택 가능.
- 전체 293개 테스트 통과. 화면 테스트도 직접 입력 대신 목록 선택·저장 동작으로 변경.
- v1.2.82 설치·재시작 완료, 설치된 소스 44개 일치와 HTTP 정상 응답 확인. 직전 v1.2.81 백업은 `~/Library/Application Support/MyBookshelf/backups/20260908-before-v1.2.82/MyBookshelf.app`에 보관.
- 아래 v1.2.81 기록의 ‘직접 입력’은 최초 구현 기록이며, 현재 화면에서는 제공하지 않음.

## 적용 내용

- HWPX: section XML의 본문·표·중첩 글상자를 순회. 동일 문자열을 임의로 중복 제거하지 않음.
- HWP 5: OLE BodyText 스트림의 중첩 PARA_TEXT 레코드 직접 추출. DOCX 변환 불필요.
- DOCX: 본문뿐 아니라 표·글상자·참조된 각주/미주 포함. Word의 Choice/Fallback 글상자 이중 추출 방지.
- 추출 결과에 구조별 개수와 그림·외부 개체 검토 안내 표시.
- 설정: 기본 AI 및 번역·요약·이미지 재판독·목차 판독·자간정리별 모델 선택, 모델 ID 직접 입력, 연결 확인 버튼.
- CLI `default`는 모델 옵션을 생략하여 CLI 설정을 따름. 명시한 모델을 임의의 다른 모델로 바꾸지 않음.
- 번역 실패 시 완료본으로 확정하지 않고 상태·진행 캐시 보존. 성공 문단 재사용, 실패 문단 재시도. 모델/로그인 오류 시 번역 대기열 중단.
- 화면 재실행 시 실행 중인 작업을 재사용. 작업 스레드에서 Streamlit 세션을 직접 갱신하지 않도록 분리. 현재 항목 저장 후 중단 지원.
- 대기열 파일 갱신 잠금 및 원자적 저장. 손상된 큐를 빈 큐로 덮어쓰지 않음.
- 실행 폴더를 교체되는 앱 번들 밖의 고정 runtime 폴더로 변경.
- 업데이트 네트워크 오류를 ‘최신 버전’과 구분. macOS 교체 권한 사전 검사.
- 더 이상 사용하지 않는 화면 너비 옵션 교체. 로그 저장 실패가 원래 오류를 가리지 않도록 처리.

## 검증

- 격리된 설정·문서 폴더에서 전체 unittest 292개 통과(기존 269개 + 신규 23개).
- 실제 Streamlit 화면 테스트: 여섯 화면 렌더링, 사용자 모델 ID 저장, 실행 중 재렌더링과 현재 항목 후 중단.
- `compileall`, `git diff --check`, 전용 Python 환경의 `pip check` 통과.
- python-hwpx로 만든 실제 글상자 문서 및 python-docx 표 문서 테스트 통과.
- 공개 HWP 바이너리 `sample-5017.hwp`, `textbox.hwp` 직접 추출 성공. 후자에서 글상자 본문 ‘글상자’ 확인.
- 공개 샘플 출처: https://github.com/mete0r/pyhwp/tree/master/tests/hwp5_tests/fixtures
- 사용자 문서는 외부 AI에 전송하지 않았으며, 연결·모델 실호출은 사용자가 설정 화면에서 실행하도록 둠.

재현 명령(설정 JSON의 base_dir도 반드시 임시 폴더로 지정):

```sh
MYBOOKSHELF_CONFIG_DIR=/path/to/disposable/config MYBOOKSHELF_LANG=ko PYTHONPATH=core python -m unittest discover -s core/tests -q
```

## 설치 상태

- `/Applications/MyBookshelf.app`에 v1.2.81 반영 및 재시작 완료.
- HTTP 상태 검사 정상, 재시작 이후 앱 오류 로그 없음.
- 실행 cwd: `~/Library/Application Support/MyBookshelf/runtime`.
- 이전 앱 백업: `~/Library/Application Support/MyBookshelf/backups/20260908-before-v1.2.81/MyBookshelf.app`.
- olefile 0.47을 전용 Python 환경에 추가. 기존 문서·키·모델 설정은 변경하지 않음.
- Git 커밋·푸시·공개 릴리스는 수행하지 않음.

## 한계와 후속 확인

- 사용자가 처음 문제를 겪은 HWP/HWPX 원본은 확보하지 못했으므로 해당 문서로 최종 대조가 필요함.
- 글자가 원래 이미지인 경우에는 이 텍스트 추출만으로 읽히지 않으며 별도 OCR이 필요함.
- 암호·배포용·보안 HWP, HWP 3 등은 편집 가능한 HWPX로 다시 저장하도록 명확히 안내함.
- 표·떠 있는 도형의 추출 순서는 화면 배치 순서와 다를 수 있음. 수식·외부 연결 개체 등 모든 객체의 완전한 재현을 보장하지 않음.
- 새 작업의 실패 상태를 추적하며, 기존에 만들어진 부분 번역 파일은 자동 재생성·삭제하지 않음.
- 모델 ID 입력 가능 여부와 계정의 실제 사용 권한은 별개. ‘연결·모델 확인’은 짧은 요청 1회로 사용량이 소모됨.
- 작업 재사용은 같은 앱 세션의 화면 갱신 대상이며, 앱 종료·재부팅을 넘는 자동 작업 재개 기능은 아님. 번역 문단 캐시는 디스크에 남음.
- Windows용 소스 및 설치 버전은 갱신했으나 Windows 실기 설치는 검증하지 않음.
