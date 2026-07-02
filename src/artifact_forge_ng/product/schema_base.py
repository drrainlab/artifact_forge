"""Base for every versioned YAML document schema.

Each document carries an explicit ``schema: <kind>/v<N>`` marker so a future
v2 migration is a discriminated load, not guesswork. Subclasses set
``SCHEMA_KIND``; the marker is validated on load.
"""

from __future__ import annotations

import re
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SCHEMA_RE = re.compile(r"^(?P<kind>[a-z_]+)/v(?P<version>\d+)$")


class VersionedModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    SCHEMA_KIND: ClassVar[str] = ""

    schema_marker: str = Field(alias="schema")

    @model_validator(mode="after")
    def _check_schema_marker(self) -> "VersionedModel":
        m = _SCHEMA_RE.match(self.schema_marker)
        if not m:
            raise ValueError(
                f"malformed schema marker {self.schema_marker!r}; expected '<kind>/v<N>'"
            )
        if self.SCHEMA_KIND and m.group("kind") != self.SCHEMA_KIND:
            raise ValueError(
                f"wrong document kind {self.schema_marker!r}: "
                f"this schema is {self.SCHEMA_KIND!r}"
            )
        return self

    @property
    def schema_version(self) -> int:
        m = _SCHEMA_RE.match(self.schema_marker)
        assert m is not None
        return int(m.group("version"))
