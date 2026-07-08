# Vertical Farm Pack — канон раздела (tilted flush row)

> **DESIGN CORRECTION (2026-07-08).** Каскадная архитектура VF-1..VF-4
> (уклон внутри желоба, ступеньки ~7.9 мм между модулями, drip-handover
> между модулями) признана **design mistake** для целевого продукта и
> заменена каноном **tilted_flush_row**, описанным этим документом.
> Каскадные goldens удалены; история — в git (коммиты VF-3/VF-4).

Модульные элементы вертикальной фермы для микрозелени на кокосовом субстрате.
Golden artifacts: `water_rail_cell_2020_petg` (ячейка из трёх печатаемых
частей) и `vertical_farm_row_3x1` (полный ряд: cap → 3 flush-модуля →
collector на двух прямых профилях 2020, магниты включены).

```
Base Water Rail        — транспортирует и ограничивает воду (никогда не хранит)
Coco Cassette          — определяет контакт субстрата с водой
Snap Retainer Frame    — легко прижимает кокос, не сдавливая его
Inlet Cap / Collector  — вода входит каплей, выходит в дренажную трубку
Straight 2020/3030     — НЕСЁТ ряд (reference hardware, cut to length)
```

## Законы раздела

1. **Transient pulse, storage forbidden.** Вода подаётся импульсом, проходит
   по желобу и уходит. Стоячая вода где угодно — контрактный FAIL
   (`closed_water_reservoir`, `dead_water_pocket` в `must_not_have`).
2. **Уклон — у МОНТАЖА, не у геометрии.** Желоб — ПОСТОЯННОЙ глубины
   (`form.water_channel_constant_depth_ok`); rail и профили моделируются
   горизонтальными; весь ряд монтируется под 1.0–2.0° (default 1.5°) —
   это машинно объявляется в `mount_context` сборки и проверяется
   `assembly.row_drains_under_mount` (виртуальные высоты v = z + y·tan(slope);
   нет mount_context / полоса нарушена / ряд реверснут → FAIL).
   Одиночная ячейка buildable горизонтально, но operational только в
   монтаже — на детали это честная INFO-нота `form.drainage_requires_mount`
   (grade не трогает).
3. **Модули flush, стыки lap-flow.** Соседние модули в ОДНОЙ плоскости
   (ΔZ = 0), торцы на контролируемом зазоре `face_gap` 0.3–0.6; шаг ряда =
   `module_w + face_gap`. Передача воды — lap-стык: губа, продолжающая
   ПЛОСКОСТЬ ПОЛА желоба (верх губы = уровень пола: выше — дамба, ниже —
   ступенька), ложится в СКВОЗНОЙ, открытый снизу проём в полу приёмника;
   у кончика губы остаётся осознанный слот 0.5–2.5 мм.
4. **Шов — не водяной путь и не герметик.** Основной поток пересекает стык
   ПО ВЕРХУ губы. Случайные капли в слот падают сквозь открытый воздух —
   видимо, чистимо, мимо алюминия/магнитов/сухих зон
   (`form.lap_slot_leak_path_controlled`). Герметичные межмодульные стыки —
   **никогда** (anti-goal), в том числе случайно (слот < 0.5 — FAIL).
5. **Rail owns water; cassette owns agronomy.** Новые культуры = новые
   кассеты, rail не трогается (Cassette Interface Standard ниже).
6. **Профиль несёт, пластик позиционирует.** Rail — не плита, а сухой
   каркас вокруг защищённого водяного ядра (lightweight dry shell,
   −40% пластика): крупные гладкие окна, открытые снизу, НЕ honeycomb;
   несущая функция — у стандартного ПРЯМОГО профиля, посадка полная
   (span gap 0 — чек, не нота).
7. **Магниты — только выравнивание.** Запечатанные сухие карманы d6.4×2.4
   в обеих ±Y гранях (default off): не герметик, не опора; ни одна грань
   магнита не видит воду (≥1.2 мм пластика до любой мокрой зоны).
8. **Всё моется щёткой.** Желоб открыт в небо, lap-проём сквозной,
   snap-окна сквозные, окна облегчения открыты вниз — скрытых мокрых
   полостей нет (always-on manufacturing-чеки).
9. **Красивый, но инженерно неправильный лоток — FAIL.** Каждая фича
   верифицируется чеками; strict-режим останавливает билд.

## Геометрия воды (как построено)

```
       cap (drip tower)                 lap-стык (ΔZ = 0)                collector
        │ FALL_ENTRY 2.5        губа 4×1.4, верх = пол желоба            ловит губу
        ▼                       ▼   слот 0.5–2.5 (открыт вниз)           последнего
   ┌────────────┐  face_gap ┌────────────┐            ┌────────────┐     модуля
   │ желоб 16×5 │◄──0.4────►│ желоб 16×5 │──── ... ──►│ желоб 16×5 │──► лоток→дренаж
   └────────────┘           └────────────┘            └────────────┘
   ══════════════════ прямой профиль 2020, полная посадка ══════════════
                весь ряд смонтирован под 1.5° (mount_context)
```

- Желоб режется с пола seat-кармана, глубина `channel_d = 5` ПОСТОЯННА;
  под полом ≥ 2 мм материала (`channel_floor_margin`).
- Датумы rail: `inlet`/`outlet` — на плоскости пола, в `face_gap/2` СНАРУЖИ
  граней (мейт outlet-on-inlet даёт ΔZ=0 и шаг `module_w + face_gap` by
  construction); `feed` — пол + FALL_ENTRY 2.5 (ЕДИНСТВЕННОЕ падение ряда —
  сюда капает cap); `drain_edge` — низ кончика губы (сюда мейтится
  collector; протрузия губы 4 мм = воздушный зазор капельной кромки).
- Lap-физика при ΔZ=0: любая толщина губы НА водяном пути — либо дамба
  (1.4 мм подпора при 1.5° = лужа ~53 мм), либо скрытый карман. Поэтому
  губа продолжает пол, а проём приёмника — сквозной (samp непредставим);
  разъединение модулей — вертикальным подъёмом (проём без потолка).

## Cassette Interface Standard (MVP-1.5)

Любая будущая кассета (`sprout_mesh_cassette_v1`, `rockwool_cube_cassette_v1`,
`netpot_cassette_v1`, …) обязана:

1. **Разделять shared-параметры** (имена — контракт):
   `cassette_l`, `cassette_w`, `cassette_h`, `seat_clearance` (0.5–1.0),
   `module_pitch`. В assembly-примере они объявлены один раз — рассинхрон
   непредставим (`_inject_shared`).
2. **Публиковать frame-ключи** (машинная половина интерфейса):
   `cassette_u0/v0/u1/v1`, `cassette_h`, `floor_bottom_z`,
   `window_cx/window_w/window_floor_z` + shell-ключи для snap
   (`shell_wall`, `inner_u0/u1`). Rail публикует `seat_*` и `channel_*`.
3. **Проходить joint `removable_insert`** в позе: зазор в полосе, tool-free
   rim, окно ВНУТРИ желоба, reach 1–2 мм, дренажный зазор ≥ 1 мм под окном.
   Съём под монтажным уклоном — прежний вертикальный подъём (cos 2° ≈
   0.9994): `assembly.cassettes_removable_under_mount` — rollup-нота.
4. **Проходить кассетные чеки**: `form.cassette_no_reservoir`,
   `form.no_secondary_water_channel`, `form.snap_pockets_cleanable`;
   `form.substrate_retained_under_mount` — INFO-нота (кокос при 1.0–2.0°
   статичен; для будущих mat-кассет станет реальным чеком с governor-липом).

⚠️ Контактное окно **уже желоба** (default 12 мм при желобе 16): окно шире
желоба физически не может в него опуститься. Площадь контакта набирается
длиной окна вдоль потока (`window_l`). Пол желоба ровный — reach окна
равномерен по всей длине.

## Реестр (recipe ops — form/recipe_ops_water.py)

| op | kind | что делает |
|---|---|---|
| `water_rail_body` | base | корпус + seat + желоб ПОСТОЯННОЙ глубины + коридоры + 4 водяных датума + lightweight-окна (param-gated, обратимо) |
| `lap_outlet_lip` | feature | губа-продолжение пола за фронт (−Y); датум drain_edge |
| `lap_inlet_receiver` | feature | сквозной открытый снизу проём в полу входа (+Y) |
| `edge_magnet_pockets` | feature | запечатанные сухие карманы d6x2 в ±Y гранях (default off) |
| `profile_seat_slot` | feature | 2 нижних паза под 2020/3030 вдоль потока, сухие |
| `tongue_groove_edges` | feature | tongue (+X) / groove (−X), только позиционирование |
| `substrate_tray_body` | base | shell кассеты (wall default 2.2 — lightweight touch) |
| `contact_window` | feature | слэб под дном (drop 1–2 мм); ДО mesh_floor |
| `mesh_floor` | feature | плоская ортогональная сквозная сетка |
| `lift_tabs` | feature | 2 пальцевых паза в бортике |
| `retainer_frame_body` / `frame_snap_hooks` | base/feature | рамка + 4 крюка |
| `inlet_cap_body` | base | drip tower; мейтит `rail.feed` |
| `collector_endcap_body` | base | Γ-лоток; catch-датум НА КОНЧИКЕ ГУБЫ, мейтит `rail.drain_edge`; derived `hang_drop = seat_depth + channel_d + lip_t` |
| `profile_ref_body` | base | ПРЯМОЙ профиль cut-to-length (slope 0 — модель буквально правдива), станции на flush-шаге |

Joints (`assembly/joints.py`): `removable_insert`, `tongue_groove`,
`snap_joint`, **`lap_flow_joint`** (flush-передача: ΔZ=0 ±0.05, face_gap
0.3–0.6, губа 3–6 в проёме, слот 0.5–2.5, приёмник ≥ отдающего по ширине),
`fluid_joint` (drip — ТОЛЬКО у адаптеров: cap→feed, drain_edge→collector),
`saddle_hang` (auxiliary verification), `profile_perch` (локальная посадка
паза на профиль).

## mount_context (product/assembly.py)

```yaml
mount_context:
  type: tilted_flush_row
  slope_deg: 1.5          # схема 0–3; операционная полоса 1.0–2.0 — чеком
  slope_source: "whole row mounted on straight 2020 profiles at 1.5 deg"
```
`slope_axis: Y` / `slope_direction: inlet_to_outlet` фиксированы литералами.
CAD остаётся горизонтальным; не-90° поз не существует. Row-чеки
(`assembly/carrier.py`) считают виртуальные высоты и порядок цепочки берут
из lap-joints (a→b), не из поз — реверснутый ряд ловится.

## Row-чеки в глобальных позах (assembly/carrier.py)

- `assembly.row_flush_aligned` — все модули в одной плоскости (ΔZ ≤ 0.1),
  шаг `module_w + face_gap` (±0.3);
- `assembly.row_drains_under_mount` — монотонный виртуальный спуск полов
  от первого входа до последнего выхода под объявленным mount;
- `assembly.profile_support_full_length` — каждый rail на КАЖДОМ прямом
  профиле, посадка полная, span gap 0 (модельный уклон профиля ≠ 0 — FAIL);
- `assembly.magnet_alignment_ok` — карманы смежных граней соосны ±0.5
  (n/a-PASS без магнитов);
- `assembly.cassettes_removable_under_mount` — rollup insert-вердиктов.

## Regions / роли

- `transient_water_path` — желоб, lap_lip, lap_receiver, контактное окно,
  spout_path, catch_tray.
- `substrate_support_mesh` — канва сетки.
- lap-вырезы, лежащие внутри объявленных водяных регионов, НЕ нарушают
  interface-keepout (keepout защищает порт от СУХИХ фич и модификаторов,
  не от собственных пустот водяной системы).
- Остальное: seat/tongue/groove/profile/magnet-карманы → `interface_keepout`;
  snap-корни → `high_stress_region`; сухая задняя зона → `mounting_surface`.

## Отчёты

- `water_report.yaml`: канал (slope 0, drop 0), lap_handover
  (lip/receiver/face_gap + «seam is not primary water path»), блок `row:` —
  kind `tilted_flush_row`, slope из mount_context, modules_flush /
  stair_step:false, total_virtual_drop_mm, handovers (lap_flow ×N−1 +
  drip ×2), standing_water_under_mount, lap_seam_leak: controlled +
  drips_clear_of, orphan_fluid_ports.
- `frame_report.yaml`: carrier (прямые профили cut-to-length, slope_deg 0
  у МОДЕЛИ), slope_source: physical_mount + slope_deg из mount_context,
  full_profile_seating: true, span_gap_mm: 0, stair_step: false.
- BOM (`assembly/bom.py`, derived-only): профиль — «standard straight, cut
  to length; mount the WHOLE row at {slope} deg»; магниты — «d6x2 …
  module alignment only … preferably coated/epoxy-protected»; silicone
  tube из hose_port; никаких HardwareSpec (зарезервировано за A2).

## Lightweight open skeleton (VF-4.1; generic-модификатор — следующая волна)

- Окна режутся НАСКВОЗЬ через подседельный слэб (открыты снизу И сверху —
  мостов нет by construction): остаются периметрическая рама, хребет
  канала, band'ы профиля и рёбра 2.0 — открытый скелет. Кассета 220×220
  накрывает каждый проём и опирается на кольцо+рёбра:
  `form.cassette_support_span_ok` (окна ≥4 внутри seat-футпринта, сетка
  цела, worst span ≤ 45). Запретные зоны — `form.lightweight_windows_dry_ok`.
- НЕ honeycomb: грязь/биоплёнка/соль — только крупные гладкие чистимые окна.
- Обратимо: `lightweight: false` → сплошная плита (smoke-тест держит оба
  варианта). Экономия на дефолтной ячейке: 1068 → 588 см³ (−45%).
- `lightweight_dry_shell_v1` как переиспользуемый модификатор — отдельная
  волна (ROADMAP).

## Printability-контракт (VF-4.1)

- **Ориентация — часть контракта**: печатные инстансы декларируют
  `manufacturing.print_orientation: as_modeled` (= дном вниз для VF);
  рассинхрон с решением билдера — FAIL
  (`manufacturing.print_orientation_declared`).
- **Always-on**: `manufacturing.supportless_lightweight_windows_ok` —
  slab-проба НА СОЛИДЕ над потолком каждого нижнего глухого кармана
  (сквозной → pass; мост ≤25 → pass-нота; ≤35 → WARN; больше → FAIL);
  `manufacturing.horizontal_bore_supportless` — горизонтальный круглый бор
  > Ø8 без teardrop-крыши → WARN.
- **Teardrop-бор** (`BoreFeature.roof="teardrop"`): 45°-хорды к пику
  d/2·√2 над центром — самонесущий потолок горизонтального бора; объём ⊃
  цилиндра, все пробы валидны. Дренаж коллектора — teardrop.
- **Магниты устанавливаются**: press-fit 0.1–0.3 диаметрально из СУХОЙ
  стыковой грани (только ±Y грани — правило чека), капля CA в BOM-ноте;
  frame_report печатает `magnet_installation: {method: press_fit_dry_face,
  water_exposed: false, role: alignment_only}`.

## Collector = концевой receiver, U-рама, вертикальный слив (VF-4.1 + VF-4.2)

Коллектор не «стоит рядом» — он ПРИНИМАЕТ финальную губу: capture 6–8 мм
от грани (кончик губы ≥2 до apron-бортика), щёки lip_w/2+1.5 охватывают
мокрую зону, mouth ≥ lip + 2×1.4, apron — низкий бортик 2.4–3.5 над
handover-плоскостью (НЕ стена: глухая щель под кокос непредставима —
`form.receiver_open_top_cleanable`: открытый верх, непрерывность с лотком,
путь капли = путь щётки). В позе: `assembly.collector_captures_drain_edge`
(кончик внутри объёма), `collector_mouth_envelopes_outlet_lip`,
`collector_removable_by_hand` (над захваченной губой нет потолка в
15-мм окне подъёма). Стык по-прежнему НЕгерметичен: cleanable, tool-free.

**VF-4.2 robustness**: лоток висит консолью — несут его ДВЕ полные боковые
стенки U-рамы (толщина ≥3.5, от дна лотка до arm, полная длина), а не
тонкие столбики; `form.collector_structure_sturdy` закрывает слепую зону
`min_wall` (он мерил параметр `wall`, не фактические сечения рёбер). Слив
**вертикальный вниз**: бор сверлится сквозь сплошной сумп (расширение
`drain_extension`, зацеп трубки `drain_grip` ≥12 мм), push-in трубка
входит СНИЗУ и уходит под ряд (порт `drain_out` normal −Z);
`form.collector_tray_drains` переписан под вертикаль (пол→сумп, устье у
низшей точки, сквозной вниз). Горизонтального бора и teardrop на коллекторе
больше нет — `BoreFeature.roof="teardrop"` остаётся кернел-примитивом и
always-on `horizontal_bore_supportless` сторожат будущие горизонтальные боры.

## Overflow honesty (VF-4.2, до VF-5 Root Chamber)

В номинале вода уходит через контактное окно в канал. Но при верхнем
поливе ИЗБЫТОК под уклоном капает сквозь сквозной скелет вниз — контейнмента
нет. Это ЯВНО в water_report: `overflow_containment {status: absent, path:
drains_through_skeleton, user_action: keep a tray under the row,
planned_fix: VF-5 root_chamber}`. Полное решение — корневая камера VF-5
(глухое дно + соты + пассивный возврат слива в коллектор).

## Печать (PETG prototype notes)

- Все печатаемые части — плоско, без поддержек; мокрый путь сверху.
- Потолки lightweight-окон — мосты ~37–43 мм: слайсер строит, провисание
  в сухой невидимой зоне приемлемо; чек репортит span > 45 нотой.
- Bed 250×250 для модуля 248 (`manufacturing.bed_fit`).
- PETG для прототипа; пищевой PP — MVP-5. Магниты предпочтительно
  с покрытием/эпоксидированные (BOM-нота).

## CAD acceptance (двухуровневый)

- В suite: `vertical_farm_flush_smoke` (cap + 2 rails с ОДНИМ настоящим
  lap-швом + кассета + collector + 1 профиль) — lap-геометрия реальна на
  солидах (no_interference, сквозной проём), отчёты пишутся; плюс
  однодетальный смок rail (масса lightweight on/off, губа/проём/карманы
  пробами).
- Полный ряд: `uv run forge build
  catalog/examples/vertical_farm/vertical_farm_row_3x1.yaml`.

## Честный остаток

- **VF-4.2**: anti-slide удержание ряда на СМОНТИРОВАННОМ под уклоном
  профиле (клипсы/упоры) — посадка полная, но продольного замка нет;
- `lightweight_dry_shell_v1` — generic-модификатор облегчения;
- `dry_endcap_v1`; `vertical_farm_shelf_row_v1` (MVP-4); VF-5 Cassette Family;
- герметичные межмодульные стыки — **никогда** (anti-goal);
- CFD — никогда в v1; проверки — sampled centerline + probe-геометрия;
- рендер сечений/exploded — общий output-слой, не пакетная забота.

## История: superseded каскад (VF-3/VF-4)

Каскад (уклон 1.25° в желобе, inlet-датум с FALL_ENTRY, ступеньки 7.91 мм,
скошенный профиль-суррогат 1.827°, span_gap 7.91 upstream-edge контакта)
реализован и верифицирован в коммитах VF-3/VF-4 — если понадобится
археология, она в git. Из каскада выжили: механизм `fluid_joint` (drip у
адаптеров), FALL_ENTRY (только датум `feed`), process:reference,
saddle_hang, profile_perch и вся Cassette Interface Standard.
