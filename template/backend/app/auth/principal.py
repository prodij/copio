from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str | None
    roles_by_org: dict[str, str] = field(default_factory=dict)
