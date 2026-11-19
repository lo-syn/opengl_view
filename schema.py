from dataclasses import dataclass

@dataclass
class DefaultMenuItem:
    label: str
    name: str

@dataclass
class ShaderMenuItem(DefaultMenuItem):
    placeholder: str | None = None

@dataclass
class SettingsMenuItem(DefaultMenuItem):
    placeholder: bool


