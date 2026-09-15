# Models and Construction

## Classes

- In Python modules, prefer `Enum -> model/class -> function` ordering when those concepts coexist
- Use `__slots__` to restrict variables when not using `dataclasses` or `pydantic`

```python
class Foo:
    __slots__ = ("name", "age")

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age
```

- Value Objects:
    - **When `pydantic` is a project dependency**: use `pydantic.BaseModel` (see [Pydantic](#pydantic) section)
    - **When `pydantic` is not a dependency**: use `dataclasses.dataclass(frozen=True, slots=True)` — `slots=True` (3.10+) auto-generates `__slots__`, no need to write it manually
    - Resolve routine representation choices from existing dependencies and nearby code. Ask only
      when a material dependency or compatibility decision is not covered by the user's request.
    - Use `__post_init__` to enforce invariants:

```python
@dataclass(frozen=True, slots=True)
class Age:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"Age must be non-negative, got {self.value}")
```

- Basically don't use `@staticmethod` — needing it indicates a design error
- **Use classmethods as alternative constructors for pure construction** (no I/O). `from_X`, `parse_X`, `create_X`, `make_X` → classmethod. **If construction involves I/O (network, file system), separate into a module-level function** to keep the Value Object pure and testable.

```python
from typing import Self


@dataclass(frozen=True, slots=True)
class SWEInstance:
    instance_id: str
    repo: str

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Self:  # pure → classmethod
        return cls(instance_id=data["id"], repo=data["repo"])


def load_instance(instance_id: str) -> SWEInstance:  # I/O → module-level function
    row = fetch_from_dataset(instance_id)
    return SWEInstance.from_dict(row)


# WRONG — module-level factory for pure construction:
def swe_instance_from_dict(data: dict) -> SWEInstance: ...  # move inside as classmethod
```

## Pydantic

Frozen model config: `pydantic.ConfigDict(extra="forbid", frozen=True, strict=True, validate_default=True)`

When multiple frozen models exist, extract a shared base class to `base.py`:

```python
import pydantic


class FrozenModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True, validate_default=True)
```

## Enums

- Use `Enum`/`StrEnum` for fixed choices instead of raw string literals or dict maps
- Convert user input strings to Enum early, then map through Enum values
- Prefer `StrEnum` when values are serialized or user-facing
