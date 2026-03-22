# AI plays Slay the Spire

## Development

> This repository is an experimental project exploring the use of AI.
> Broad compatibility across different runtime environments is not currently a first-class requirement.

### Environment

- macOS: 26.3.1
- [Slay the Spire - Steam](https://store.steampowered.com/app/646570/Slay_the_Spire/)
- [ModTheSpire - Steam](https://steamcommunity.com/sharedfiles/filedetails/?id=1605060445)
- [BaseMod - Steam](https://steamcommunity.com/sharedfiles/filedetails/?id=1605833019)
- [uv](https://docs.astral.sh/uv/): 0.10.9
  - Python: 3.11
- [SDKMAN!](https://sdkman.io/)
  - [Maven](https://maven.apache.org/)
  - JDK: `8.0.482-zulu`

### Setup

```sh
uv sync --all-packages --locked
uv run bootstrap
uv run build-mod
```

- `bootstrap` initializes CommunicationMod git submodules.
- `build-mod` builds CommunicationMod and installs it into the Slay the Spire mods directory.

### Configuration

CommunicationMod config file location: `~/Library/Preferences/ModTheSpire/CommunicationMod/config.properties`.

Configure it as follows:

```properties
command=/absolute/project/.venv/bin/python -m bridge
runAtGameStart=true
```

`command` must be an absolute path appropriate for your local environment.
