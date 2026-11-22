from dataclasses import dataclass, field
from typing import Optional
from collections.abc import Callable

#from lib_shader_send import 

@dataclass
class DefaultMenuItem:
    state: bool | None = False
    on_state_msg: str | None = ""
    off_state_msg: str | None = ""

@dataclass
class ShaderMenuItem(DefaultMenuItem):
    placeholder: str | None = None

@dataclass
class SettingsMenuItem(DefaultMenuItem):
    status_labels: list[str] | None = field(default_factory=list)
    linked_function: Callable[[bool], None] = field(kw_only=True)


