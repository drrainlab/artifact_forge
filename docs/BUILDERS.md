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
| `revolve_band` | ✅ | recipe-op: кольцо/втулка/шайба/браслет + цилиндрическая канва полей (finger_ring_v1, catalog/local) |
| `rounded_plate` | ✅ | profiles_plate.rounded_rect_loop + PlateFeature (adapter_plate) |
| `molded_side_hook_profile` | ✅ | flagship; + teardrop roof; + `tongue_side_hook` (sideprint) |
| `j_hook_profile` | ✅ | wall_hook / headphone_hook |
| `cable_comb_profile` | ✅ | cable_comb |
| `omega_anchor_profile` | ✅ | zip_tie_anchor |
| `device_slot_profile` | ✅ | phone_stand (slot = f(tilt), COM-гейт) |
| `open_c_channel_profile` | ✅ | cable_raceway_v1 (raceway_200): U-канал, constant section, wall меряется |
| `snap_c_clip_profile` | ✅ | snap_c_tongue (pipe_clip_v1_sideprint): арк-ретенция + балка в профиле, sideprint |
| `cylindrical_cradle` | ✅ | первый клиент: payload snap-C манжеты (рот вверх, arc 210–268) внутри `forearm_cuff_body` |
| `forearm_cuff_body` | ✅ | wearable P2: body_fit C-ring c хордовым ртом + строп-табы + TPU-ланды + payload snap-C, sideprint (profiles_wearable.py) |
| `device_cradle` | 🔶 | покрыт device_slot_profile (phone_stand параметрический) |
| `rounded_box_shell` | ✅ | recipe-op: outer body + interior cut, form.shell_walls_ok |
| `sweep_profile_along_path` | ✅ | kind section_sweep: дуга по 3 точкам + topology.bar_follows_arc (grab_handle_v1) |
| `loft_between_sections` | 🔶 | rect→rect есть (LoftFeature/tapered_beam); rect→circle при первом клиенте |
| `tapered_beam` | ✅ | LoftFeature (конус по построению) + topology.arm_reaches_tip (shelf_bracket_v1) |
| `truss_beam` | ✅ | truss_web_cutouts op: warren-треугольники, лигамент = strut by construction (truss_beam_180) |
| `water_rail_body` | ✅ | vertical farm (docs/VERTICAL_FARM_PACK.md): корпус + seat + наклонный ChannelCutFeature + коридоры (water_rail_v1) |
| `substrate_tray_body` | ✅ | vertical farm: shell кассеты + frame-ключи Cassette Interface Standard (coco_cassette_v1) |
| `retainer_frame_body` | ✅ | vertical farm: кольцевая рамка-прижим (substrate_retainer_frame_v1) |
| `inlet_cap_body` | ✅ | VF-3: drip tower — вертикальный hose-бор сквозь спаут в inlet-коридор; saddle-hang на заднюю стенку (inlet_cap_v1) |
| `collector_endcap_body` | ✅ | VF-3: Γ catch tray под overflow-кромкой, наклонный пол в закрытый дренажный бор; saddle-hang на переднюю стенку (collector_endcap_v1) |
| `profile_ref_body` | ✅ | VF-4: reference-суррогат стандартного 2020/3030 под глобальным уклоном ряда (скос = широкий ChannelCutFeature; process: reference — без FDM-чеков) |

### feature — крепёж, карманы, вырезы

| builder | статус | где / волна |
|---|---|---|
| `hole_pattern` (line/grid/bolt-circle) | ✅ | form/patterns.py + min_web/outline-чеки |
| `countersunk_hole_pattern` | ✅ | HoleFeature.countersink_face (урок печати: зенковка снизу) |
| `counterbore_hole_pattern` | ✅ | HoleFeature.head_style=cylinder + recipe-op (fastener_plate_v1) |
| `rounded_rect_cutout` | ✅ | recipe-op (углы прямые v1) |
| `port_cutout` (usb_c/audio/…) | ✅ | recipe-op, типизированная таблица PORT_SIZES |
| `wire_exit` | ✅ | recipe-op: drop-in U-нотч в кромке шелла (cable_junction_box_v1) |
| `nut_trap` | ✅ | recipe-op: hex-карман (flat-to-flat!) над clearance-бором |
| `heatset_insert_pocket` | ✅ | recipe-op из heatset-таблицы fasteners |
| `boss_pattern` | ✅ | recipe-op: 4 бобышки + глухие pilot-боры, keepout в слое пола |
| `standoff_pattern` | ✅ | recipe-op: PCB-стойки на плите + глухие pilot'ы |
| `lid_seat` | ✅ | inset_plug op + lid_seat joint: размерная цепочка + pose-проба (esp32_box_with_lid) |
| `overflow_lip` | ✅ | vertical farm: relief-подрез = air gap под кромкой перелива + drip receiver |
| `profile_seat_slot` | ✅ | vertical farm: пазы под 2020/3030, сухая зона верифицирована |
| `tongue_groove_edges` | ✅ | vertical farm: tongue/groove кромки линии модулей |
| `contact_window` | ✅ | vertical farm: слэб контактного окна под дном кассеты (topology.contact_window_present: есть И прошит сеткой) |
| `mesh_floor` | ✅ | vertical farm: плоская ортогональная сквозная сетка (slots-FieldFeature) |
| `lift_tabs` | ✅ | vertical farm: пальцевые пазы tool-free съёма |
| `frame_snap_hooks` | ✅ | vertical farm: 4 крюка рамки (2 на сторону, snap_joint-совместимые) |

### field — модификаторы (уже region-bound, композиция через keepouts)

Маппинги окон: planar, tilted (наклонные грани), **cylindrical_z_mapping_v1**
(боковая стенка revolve-тел: ось Z, полный 360°, один явный seam_keepout;
ячейки строятся в касательной плоскости и режутся радиально; support-free —
это измеряемый `manufacturing.max_opening_span`, не обещание).

| builder | статус |
|---|---|
| `honeycomb_field` | ✅ add_hex_perforation (flat-to-flat 30°, min_ligament меряется) |
| `grid_slot_field` | ✅ add_grid_slot_field |
| `voronoi_field` | ✅ add_voronoi_field (stable seed, Lloyd, Chaikin, лигамент гарантирован) |
| `magnet_pocket_pattern` | ✅ add_magnet_pockets (глухие, кожа проверяется) |
| `strap_slot_pair` | ✅ add_zip_tie_slots (стяжки ≤10мм) + add_strap_slots (стропы 15–40мм, skin-guard; wearable P2) |
| `rib_field` | ✅ add_ribs (аддитивные, topology.ribs_present) |
| `phyllotaxis_field` | ✅ add_phyllotaxis_field (Vogel-спираль, лигамент by construction + измерен) |
| `vein_rib_field` | ✅ | add_vein_ribs (standalone, seeded rhythm, additive) + вены biomorphic в style |
| `space_colonization_branching` | ⬜ R5 |

### style — не builders, отдельный слой (закреплено)

`biomorphic_surface_deform` = SurfaceStyle biomorphic_utility_part (слайдеры →
controlled passes, preserve by construction). Не смешивать с recipe.

### assembly joints (реестр assembly/joints.py — verified в позе)

| joint | статус |
|---|---|
| `screw_joint` | ✅ R1: болт-круги совпадают в позе, clear↔tap, оси void, интерференс |
| `lid_seat` | ✅ R2: цепочка plug↔interior−2·clearance до CAD + assembly.lid_seats в позе |
| `press_fit_pin_pair` | ✅ R2: PinFeature + interference-контракт (пин ТОЛЩЕ гнезда, overlap измерен и ограничен) |
| `split_plane_with_alignment` | ✅ суть: butt_pin_joint (секции идентичны + торцевые пины; PinFeature.axis) — raceway_400_split. Авто-генератор из ОДНОГО инстанса = edit-intent следующей итерации |
| `snap_joint` | ✅ compliant: undercut + insertion strain 1.5·δ·t/L² ≤ 5% (esp32_box_snap_lid) |
| `fluid_joint` | ✅ A1.5: handover ТОЛЬКО вниз (gravity is the pump) + совместимые ширины каналов; первый клиент — VF-3 адаптеры |
| `removable_insert` | ✅ vertical farm: drop-in кассета в seat (clearance band, tool-free rim, окно ВНУТРИ желоба, reach 1–2мм, drain gap ≥ 1мм) |
| `tongue_groove` | ✅ vertical farm: линия модулей — groove глотает tongue в полосе 0.3–0.5, не доставая дна; каналы параллельны и на одной высоте |
| `fluid_joint` | ✅ VF-3 (первый клиент): передача воды outlet→inlet СТРОГО вниз (gravity is the pump), приёмник ≥ отдающего по ширине; a: = отдающая сторона (говорящий FAIL при путанице) |
| `saddle_hang` | ✅ VF-3: auxiliary VERIFICATION joint — седло адаптера страддлит стенку rail в позе, заданной fluid_joint; никогда не реализует fluid-порты (no_orphan_ports не считает) |
| `profile_perch` | ✅ VF-4: паз rail на алюминиевом носителе (тип profile_seat); row-truth в assembly.row_supported/row_pitch_aligned/profile_slope_feeds_downhill (глобальные позы) |
| `dovetail_joint` | ✅ A1: undercut-ретенция + clearance-band + угол фланков + полное зацепление; friction-only осевое удержание (заявлено) |

### interface / joint / механика

| builder | статус / волна |
|---|---|
| `gusset_pair` | ✅ shelf_bracket_v1 (web-косынки как рёбра) |
| `snap_hook` / `snap_receiver` | ✅ | ops snap_hook_pair / snap_window_pair + snap_joint (strain-физика поймала первый дизайн: 9мм балка ломалась) |
| `press_fit_pin_pair` | ✅ (см. assembly joints) |
| `dovetail_joint` | ✅ A1: сокет-корона манжеты + male-нога адаптеров (forearm_cuff_body payload_mount=dovetail_socket / dovetail_adapter_body) |
| `tongue_groove_joint` | ✅ vertical farm: tongue_groove_edges op + tongue_groove joint (выравнивание линии, non-bearing/non-sealing, соосность желобов в позе) |
| `split_plane_with_alignment` | ✅ (см. assembly joints: butt_pin_joint) |
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
- **R2 — Enclosure core** ✅ ПОЛНОСТЬЮ (2026-07-03): shell/boss/port +
  lid_seat/standoff/nut_trap/heatset/wire_exit/counterbore; примеры
  esp32_box_base, esp32_box_with_lid (сборка!), fastener_plate_demo,
  junction_box_60.
- **R3 — Maker profiles** ✅: snap_c_tongue (broom_clip_25mm) +
  open_c_channel (raceway_200). Остаток: cradles (обобщение).
- **R4 — Strength & assembly** ✅ ядро: LoftFeature/tapered_beam +
  gusset-webs (shelf_bracket_150). Остаток: sweep, joints/split_plane —
  ждут multi-part пайплайна.
- **R5 — Wow & механика** ✅ ядро: bearing_seat + phyllotaxis_field
  (bearing_turntable_base). Остаток: резьбы, ratchet, branching,
  friction hinge.

## Честный остаток (глубокая механика — по итерации на штуку)

Остатки волн сведены в мастер-план [ROADMAP.md](ROADMAP.md): dovetail →
волна A1 (ports/interfaces), rail_slider → A4 (Workshop Wall System),
петли/резьбы/ratchet → E-этап.

`dovetail`/`tongue_groove` и `rail_slider` — скользящие посадки (трение,
допуски по направлению хода); `pin_hinge` и `friction_hinge` — подвижные
сборки (зазор оси, момент); `living_hinge` — усталость материала;
`thread_external/internal` — helix-sweep в OCC + профиль резьбы;
`shaft_coupler`, `ratchet_teeth` — передачи момента;
`space_colonization_branching` — нужен ориентированный аддитив (диагональные
ветви, Box3-рёбер недостаточно). У каждого — собственная физика и
валидаторы; фича без них была бы галлюцинацией, поэтому они не
«добиваются», а планируются как отдельные итерации на готовом фундаменте
(recipe + joints + позные пробы).

## Ориентация печати — сквозная забота

Любой base-builder обязан объявлять `print_orientation` (или честно
`as_modeled`), а overhang-валидатор — знать его. Урок sideprint-клипсы:
константная экструзия профилем на стол = ноль нависаний by construction;
это свойство ПРОВЕРЯЕТСЯ (`form.constant_section`), а не постулируется.

## Интерфейсы (wave A1 — docs/ROADMAP.md)

Соединение = ДЕКЛАРИРОВАННЫЙ порт: `interfaces:` на архетипе (id, type,
gender, datum, clearance, region, keepouts, accepts, assembly_role) из
реестра 11 типов (`product/interfaces.py`). Joint реализует тип порта;
mate легален только при совпадении типа + комплементарном гендере +
взаимном accepts (`assembly/mates.py`); `forge compat` выводит матрицу
совместимости каталога; `assembly/swap.py` верифицирует замену детали
(interface.swap_part_builds). Билдер, публикующий порт, обязан издать его
датум и frame-ключи типа — `interface.frame_exists` меряет.
