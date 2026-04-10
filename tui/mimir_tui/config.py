import json
from dataclasses import dataclass, asdict
from pathlib import Path

from platformdirs import user_config_dir

CONFIG_DIR = Path(user_config_dir("mimir"))
CONFIG_FILE = CONFIG_DIR / "tui.json"


@dataclass
class TuiConfig:
    base_url: str = "http://localhost:3080"
    api_key: str | None = None


def load_config() -> TuiConfig:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            return TuiConfig(**{k: v for k, v in data.items() if k in TuiConfig.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            pass
    return TuiConfig()


def save_config(cfg: TuiConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(asdict(cfg), indent=2))
