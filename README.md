AI plays Slay the Spire

## 요구사항

### 모드 설치

아래 모드들을 설치합니다:

- [ModTheSpire](https://steamcommunity.com/sharedfiles/filedetails/?id=1605060445)
- [BaseMod](https://steamcommunity.com/sharedfiles/filedetails/?id=1605833019)
- [Communication Mod](https://steamcommunity.com/sharedfiles/filedetails/?id=2131373661)

### 설정 파일 작성

> macOS 환경 기준입니다.

설정 파일 경로는 `~/Library/Preferences/ModTheSpire/CommunicationMod/config.properties`입니다.

다음 예제와 같이 작성합니다:

```sh
command=/your/absolute/path/ai-plays-slay-the-spire/scripts/run.sh
runAtGameStart=true
```

`command`는 각 환경에 맞는 절대경로를 입력합니다.
