"""Form builders — Python constructors an archetype's ``form.section`` name
binds to. The registry is the only coupling between catalog YAML and builder
code; an archetype whose section has no registered builder is honestly
unbuildable (capability gap), not a crash.
"""

from __future__ import annotations

from typing import Callable

from ..form.part import PartForm
from ..product.archetype import ArchetypeSpec
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams
from . import underdesk_cable_clip

FormBuilder = Callable[[ResolvedParams, ArchetypeSpec, ProductInstance], PartForm]

FORM_BUILDERS: dict[str, FormBuilder] = {
    underdesk_cable_clip.SECTION_NAME: underdesk_cable_clip.build_form,
}


def builder_for(archetype: ArchetypeSpec) -> FormBuilder | None:
    return FORM_BUILDERS.get(archetype.form.section)
