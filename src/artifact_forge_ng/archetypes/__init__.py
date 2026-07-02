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
from . import (
    adapter_plate,
    cable_comb,
    j_hook,
    lamp_bracket,
    lamp_socket_cup,
    phone_stand,
    underdesk_cable_clip,
    zip_tie_anchor,
)

FormBuilder = Callable[[ResolvedParams, ArchetypeSpec, ProductInstance], PartForm]

FORM_BUILDERS: dict[str, FormBuilder] = {
    underdesk_cable_clip.SECTION_NAME: underdesk_cable_clip.build_form,
    adapter_plate.SECTION_NAME: adapter_plate.build_form,
    cable_comb.SECTION_NAME: cable_comb.build_form,
    zip_tie_anchor.SECTION_NAME: zip_tie_anchor.build_form,
    j_hook.SECTION_NAME: j_hook.build_form,
    lamp_socket_cup.SECTION_NAME: lamp_socket_cup.build_form,
    lamp_bracket.SECTION_NAME: lamp_bracket.build_form,
    phone_stand.SECTION_NAME: phone_stand.build_form,
}


def builder_for(archetype: ArchetypeSpec) -> FormBuilder | None:
    return FORM_BUILDERS.get(archetype.form.section)
