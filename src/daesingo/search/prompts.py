from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files
from string import Formatter

from .scope import VisualEventType


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    version: str
    text: str
    fingerprint: str
    placeholders: frozenset[str]

    def render(self, **values: object) -> str:
        missing = self.placeholders - values.keys()
        if missing:
            raise ValueError(f"missing prompt values: {', '.join(sorted(missing))}")
        return self.text.format(**values)


def load_prompt(version: str) -> PromptTemplate:
    resource = files("daesingo.search").joinpath("prompt_resources", f"{version}.txt")
    text = resource.read_text(encoding="utf-8")
    placeholders = frozenset(
        field_name
        for _, field_name, _, _ in Formatter().parse(text)
        if field_name is not None
    )
    return PromptTemplate(
        version=version,
        text=text,
        fingerprint=sha256(text.encode("utf-8")).hexdigest(),
        placeholders=placeholders,
    )


COARSE_PROMPT = load_prompt("coarse-p3")
FINE_PROMPT = load_prompt("fine-p3")


def fine_prompt_for(event_type: VisualEventType) -> PromptTemplate:
    suffix = event_type.value.lower().replace("_", "-")
    delta = load_prompt(f"fine-p3-{suffix}")
    text = f"{FINE_PROMPT.text.rstrip()}\n\n{delta.text}"
    return PromptTemplate(
        version=FINE_PROMPT.version,
        text=text,
        fingerprint=sha256(text.encode("utf-8")).hexdigest(),
        placeholders=FINE_PROMPT.placeholders,
    )
