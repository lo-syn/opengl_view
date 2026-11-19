from dataclasses import dataclass, field
from collections.abc import Callable

@dataclass
class DefaultMenuItem:
    name: str
    state: bool | None = False
    on_state_msg: str | None = ""
    off_state_msg: str | None = ""

@dataclass
class ShaderMenuItem(DefaultMenuItem):
    placeholder: str | None = None

@dataclass
class SettingsMenuItem(DefaultMenuItem):
    linked_function: Callable[[bool], None] = field(kw_only=True)


