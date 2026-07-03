# Geometry Builders — канонический реестр

Сердце системы. Хорошо выбранные builders позволяют собирать большинство
новых архетипов из YAML/Recipe без нового Python-кода.

```text
archetype = "что делаем"        (семантика изделия, контракт, инварианты)
builder   = "каким приёмом строим"   (геометрия + регионы + frame + валидаторы)
modifier  = "как локально адаптируем" (region-bound поля/интерфейсы поверх)
style     = "какая кожа"         (controlled form passes, инженерия нетронута)
```

## Контракт builder'а (не обсуждается)

Builder, который просто строит геометрию, бесполезен. Каждый builder обязан
отдавать все четыре:

1. **Геометрию** — вклад в PartForm (профиль/плиту/фичу), никаких прямых CAD-вызовов.
2. **Semantic regions** — чтобы модификаторы знали, куда можно, а keepouts выводились автоматически.
3. **Frame-ключи** — единый источник правды: пробы меряют ровно те числа, из которых строилось.
4. **Валидаторы** — имена form/topology-проверок, которые он подписывает.
   Именованная фича без validator-backed геометрии = галлюцинация → missing/engine_gap.

Recipe-op без реализации в движке = честный engine-gap WARN и unbuildable —
тот же механизм, что для валидаторов и аппликаторов. Новые builders рождаются
как draft/coding-agent task, никогда как произвольный Python в runtime.

## Четыре рода builders

- **base** — создают первичное тело (одно на деталь): профильные секции,
  плиты, revolve, sweep, loft.
- **feature** — присоединяются к телу: отверстия, карманы, боссы, вырезы.
- **field** — region-bound массивы = МОДИФИКАТОРЫ (уже так и устроено;
  не переносить в recipe-слой, композиция через keepouts уже решена).
- **interface/joint** — посадки, защёлки, петли, соединения.

---

## Реестр (статус на 2026-07-03)

✅ = реализовано · 🔶 = реализовано частично / в другом слое · ⬜ = запланировано

### base — первичные тела

| builder | статус | где / волна |
|---|---|---|
| `section_extrude` | ✅ | ядро (PartForm.kind) |
| `profile_revolve` | ✅ | ядро; lamp_socket_cup — чашки, втулки, шайбы, ручки |
| `rounded_plate` | ✅ | profiles_plate.rounded_rect_loop + PlateFeature (adapter_plate) |
| `molded_side_hook_profile` | ✅ | flagship; + teardrop roof; + `tongue_side_hook` (sideprint) |
| `j_hook_profile` | ✅ | wall_hook / headphone_hook |
| `cable_comb_profile` | ✅ | cable_comb |
| `omega_anchor_profile` | ✅ | zip_tie_anchor |
| `device_slot_profile` | ✅ | phone_stand (slot = f(tilt), COM-гейт) |
| `open_c_channel_profile` | ⬜ | кабель-каналы, направляющие |
| `snap_c_clip_profile` | ✅ | snap_c_tongue (pipe_clip_v1_sideprint): арк-ретенция + балка в профиле, sideprint |
| `cylindrical_cradle` | ⬜ R3 | микрофоны, фонарики (частично покрыт revolve) |
| `device_cradle` | ⬜ R3 | обобщение phone_stand люльки |
| `rounded_box_shell` | ✅ | recipe-op: outer body + interior cut, form.shell_walls_ok |
| `sweep_profile_along_path` | ⬜ R4 | ручки, дуги; швы — отдельная работа |
| `loft_between_sections` | ⬜ R4 | molded-переходы |
| `tapered_beam` | ✅ | LoftFeature (конус по построению) + topology.arm_reaches_tip (shelf_bracket_v1) |
| `truss_beam` | ⬜ R5 | фермы |

### feature — крепёж, карманы, вырезы

| builder | статус | где / волна |
|---|---|---|
| `hole_pattern` (line/grid/bolt-circle) | ✅ | form/patterns.py + min_web/outline-чеки |
| `countersunk_hole_pattern` | ✅ | HoleFeature.countersink_face (урок печати: зенковка снизу) |
| `counterbore_hole_pattern` | ⬜ | тривиальное расширение cad/holes.py |
| `rounded_rect_cutout` | ✅ | recipe-op (углы прямые v1) |
| `port_cutout` (usb_c/audio/…) | ✅ | recipe-op, типизированная таблица PORT_SIZES |
| `wire_exit` | 🔶 R2 | BoreFeature покрывает круглый; rounded_slot + strain relief — R2 |
| `nut_trap` | ⬜ R2 | шестигранник уже умеем резать (hex-урок про 30°!) |
| `heatset_insert_pocket` | ⬜ R2 | словарь вставок |
| `boss_pattern` | ✅ | recipe-op: 4 бобышки + глухие pilot-боры, keepout в слое пола |
| `standoff_pattern` | ⬜ R2 | как boss, выше |
| `lid_seat` | ⬜ R2 | overlap/recess + clearance; нужны fit-пробы |

### field — модификаторы (уже region-bound, композиция через keepouts)

| builder | статус |
|---|---|
| `honeycomb_field` | ✅ add_hex_perforation (flat-to-flat 30°, min_ligament меряется) |
| `grid_slot_field` | ✅ add_grid_slot_field |
| `voronoi_field` | ✅ add_voronoi_field (stable seed, Lloyd, Chaikin, лигамент гарантирован) |
| `magnet_pocket_pattern` | ✅ add_magnet_pockets (глухие, кожа проверяется) |
| `strap_slot_pair` | ✅ add_zip_tie_slots |
| `rib_field` | ✅ add_ribs (аддитивные, topology.ribs_present) |
| `phyllotaxis_field` | ✅ add_phyllotaxis_field (Vogel-спираль, лигамент by construction + измерен) |
| `vein_rib_field` | 🔶 style-слой: вены biomorphic уже есть; как отдельный field — R5 |
| `space_colonization_branching` | ⬜ R5 |

### style — не builders, отдельный слой (закреплено)

`biomorphic_surface_deform` = SurfaceStyle biomorphic_utility_part (слайдеры →
controlled passes, preserve by construction). Не смешивать с recipe.

### interface / joint / механика

| builder | статус / волна |
|---|---|
| `gusset_pair` | ✅ shelf_bracket_v1 (web-косынки как рёбра) |
| `snap_hook` / `snap_receiver` | ⬜ R4 (пара, clearance-контракт общий) |
| `press_fit_pin_pair` | ⬜ R4 |
| `dovetail_joint` / `tongue_groove_joint` | ⬜ R4 |
| `split_plane_with_alignment` | ⬜ R4 (+ multi-part пайплайн) |
| `pin_hinge` | ⬜ R4 |
| `rail_slider` | ⬜ R5 |
| `living_hinge` | ⬜ R5 (материал/усталость — свои валидаторы) |
| `thread_external` / `thread_internal_clearance` | ⬜ R5 |
| `bearing_seat` | ✅ recipe-op (таблица 608/625/6001, губа проверяется probe) |
| `shaft_coupler`, `ratchet_teeth`, `friction_hinge` | ⬜ |

---

## Волны реализации

- **R1 — Recipe kernel**: `form: {type: recipe}` в схеме архетипа; реестр
  recipe-ops с fail-fast именами при загрузке каталога; промоушен уже
  существующих в композируемые ops (`rounded_plate`, `hole_pattern`,
  `countersunk_hole_pattern`, `counterbore_hole_pattern`,
  `rounded_rect_cutout`); демо-архетип ЦЕЛИКОМ из YAML без Python.
  Критерий: новый полезный архетип (панель/грометка) собирается рецептом и
  проходит полный honesty-пайплайн.
- **R2 — Enclosure core** ✅ ядро (2026-07-03): rounded_box_shell +
  boss_pattern + port_cutout; пример esp32_box_base (+вентиляция полей).
  Остаток: lid_seat (нужны multi-part fit-пробы), standoff, nut_trap,
  heatset-словарь, wire_exit со strain relief.
- **R3 — Maker profiles** ✅ ядро: snap_c_tongue (broom_clip_25mm,
  support-free). Остаток: open_c_channel, cradles.
- **R4 — Strength & assembly** ✅ ядро: LoftFeature/tapered_beam +
  gusset-webs (shelf_bracket_150). Остаток: sweep, joints/split_plane —
  ждут multi-part пайплайна.
- **R5 — Wow & механика** ✅ ядро: bearing_seat + phyllotaxis_field
  (bearing_turntable_base). Остаток: резьбы, ratchet, branching,
  friction hinge.

## Ориентация печати — сквозная забота

Любой base-builder обязан объявлять `print_orientation` (или честно
`as_modeled`), а overhang-валидатор — знать его. Урок sideprint-клипсы:
константная экструзия профилем на стол = ноль нависаний by construction;
это свойство ПРОВЕРЯЕТСЯ (`form.constant_section`), а не постулируется.
