# Vertical Farm Pack v1 — канон раздела

Модульные элементы вертикальной фермы для микрозелени на кокосовом субстрате.
Golden artifact: `water_rail_cell_2020_petg` — ячейка ~248×248 мм на
номинальной сетке 250 мм из трёх печатаемых частей.

```
Base Water Rail        — транспортирует и ограничивает воду (никогда не хранит)
Coco Cassette          — определяет контакт субстрата с водой
Snap Retainer Frame    — легко прижимает кокос, не сдавливая его
```

## Законы раздела

1. **Transient pulse, storage forbidden.** Вода подаётся импульсом, проходит
   по желобу с монотонным уклоном 1.0–1.5°, срывается каплями с overflow-кромки
   и уходит. Стоячая вода где угодно — контрактный FAIL
   (`closed_water_reservoir`, `dead_water_pocket` в `must_not_have`).
2. **Rail owns water; cassette owns agronomy.** Rail — водяная инфраструктура,
   кассета — агротехнический адаптер. Новые культуры = новые кассеты, rail не
   трогается (см. Cassette Interface Standard ниже).
3. **Корпус горизонтален, падает только вода.** Уклон реализован геометрией
   желоба (`ChannelCutFeature`: глубина растёт от входа к выходу), каркас и
   полка считаются горизонтальными.
4. **Всё моется щёткой.** Желоб открыт в небо по всей длине (коридорные
   вырезы сквозь бортики seat), snap-окна сквозные, скрытых мокрых щелей нет —
   `manufacturing.brush_access_to_water_channel` / `no_hidden_wet_crevices` /
   `no_unwashable_snap_pockets` (always-on, с n/a fast-path для сухих частей).
5. **Красивый, но инженерно неправильный лоток — FAIL.** Каждая фича верифицируется
   чеками; в strict-режиме отсутствие уклона, кромки, окна, слива — стоп билда.

## Геометрия воды (как построено)

```
                 seat (кассета, зазор 0.75/сторону)
   +──────────────────────────────────────────+  ← верх rail (body_h)
   │   ┌──────────────────────────────────┐   │
   │   │  seat floor = channel entry plane│   │  ← seat_floor_z
   │   │   ╲______ желоб 16×(5→10.4) ____╱ │   │  ← уклон 1.25° к фронту
   +───┴──────────────────────────────┬───┴───+
      профиль 2020 (сухая зона)       │ lip 2мм → air gap 1.5 → капля вниз
```

- Желоб режется с **пола seat-кармана** (не с верха корпуса) — кассета висит
  над водой, а не в ней.
- `channel_d = 5mm` — глубина у **входа** (тыл, +Y); к выходу глубина растёт
  на `module_w · tan(slope)` ≈ 5.4 мм. Под самой глубокой точкой остаётся
  ≥ 2 мм материала (`channel_floor_margin`).
- Overflow lip = язык пола толщиной `lip_h`, оставленный над relief-вырезом
  глубиной `air_gap ≥ 1.2` — вода отрывается каплей, не стекает по стенке.
  Кромка **никогда не скругляется** (чек ловит blend-зону на кромке);
  `lip_r_assumed = 0.4` — печатный радиус.
- Drip receiver = объём relief-выреза: открыт, инспектируем, не второй желоб.

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
   rim (≥ lift_margin над верхом rail), окно ВНУТРИ желоба, reach 1–2 мм,
   дренажный зазор ≥ 1 мм под окном (затопление непредставимо).
4. **Проходить кассетные чеки**: `form.cassette_no_reservoir`,
   `form.no_secondary_water_channel`, `form.snap_pockets_cleanable`.

Compliance-тест новой кассеты = тот же golden-пример со свапнутой частью.

⚠️ Контактное окно **уже желоба** (default 12 мм при желобе 16 мм): окно шире
желоба физически не может в него опуститься — его края стояли бы в воде на
полу seat. Площадь контакта набирается длиной окна вдоль потока (`window_l`).

## Реестр (recipe ops — form/recipe_ops_water.py)

| op | kind | что делает |
|---|---|---|
| `water_rail_body` | base | корпус + seat + наклонный желоб + коридоры + датумы |
| `overflow_lip` | feature | relief-подрез под кромкой = air gap + drip receiver |
| `profile_seat_slot` | feature | 2 нижних паза под 2020/3030 вдоль потока, сухие |
| `tongue_groove_edges` | feature | tongue (+X) / groove (−X), только позиционирование |
| `substrate_tray_body` | base | shell кассеты + ключи Cassette Interface Standard |
| `contact_window` | feature | слэб под дном (drop 1–2 мм); ДО mesh_floor |
| `mesh_floor` | feature | плоская ортогональная сквозная сетка (cell 4–8, rib ≥ 1.2) |
| `lift_tabs` | feature | 2 пальцевых паза в бортике — съём без инструмента |
| `retainer_frame_body` | base | кольцевая пластина рамки |
| `frame_snap_hooks` | feature | 4 крюка (по 2 на ±X), strain-формула в joint |

Joints (`assembly/joints.py`): `removable_insert`, `tongue_groove` (новые),
`snap_joint` (реюз: кассета публикует shell-ключи + `snap_window_*`).
`aluminum_profile_mount` — НЕ joint (внешнее железо): оп + регион +
`form.profile_seat_dry_ok`.

## Regions / роли

Новые роли (обе в PROTECTED_ROLES модификаторов и EXO_PROTECTED_ROLES):
- `transient_water_path` — желоб, кромка, receiver, контактное окно.
- `substrate_support_mesh` — канва сетки (полностью задаётся опом).

Остальное — существующие роли: seat/tongue/groove/profile →
`interface_keepout`; snap-корни → `high_stress_region`; сухая зона магнитов →
`mounting_surface` (editable; единственное место для `add_magnet_pockets`).

## Отчёты

`forge build` сборки пишет `water_report.yaml` (mode, slope, drop, lip,
air_gap, dead_pockets, permanent_substrate_contact, contact_window.reach) и
блок `views:` в `assembly_report.yaml` — плоскости сечений (flow/cross) и
explode-векторы, выведенные из типов joints. Метаданные, не рендер (v1).

## Печать (PETG prototype notes)

- Все три части печатаются плоско, без поддержек (`support_policy: none`);
  мокрый путь сверху — поддержек в нём не бывает по построению.
- Bed 250×250 обязателен для модуля 248 мм: объявляется в
  `manufacturing.bed` инстанса (проверяет `manufacturing.bed_fit`).
- PETG для прототипа; пищевой PP, draft angles, mold-friendly warnings — MVP-5.
- Snap strain 0.041 — территория PETG/ABS; хрупкий PLA может треснуть
  (joint предупреждает).

## Мойка и обслуживание

- Кассета вынимается пальцами (lift-пазы), рамка снимается флексом двух крюков.
- Желоб чистится щёткой ≥ Ø8 по всей длине сверху.
- После импульса вода полностью уходит: монотонный уклон + гарантированный
  выход через передний торец + отсутствие карманов (верифицировано).

## VF-3 Fluid Row (реализовано)

**Golden artifact**: `vertical_farm_row_3x1_petg` — inlet cap → 3 rail-ячейки
(с кассетами) → collector endcap. Первый реальный клиент `fluid_joint`.

⚠️ **Row = fluid cascade assembly proof, НЕ финальная стойка.** Fluid-датумы
= точки передачи воды: outlet-датум на кромке, inlet-датум = пол входа +
FALL_ENTRY (2.5). Совмещение датумов опускает каждый следующий модуль на
~7.9 мм — «gravity is the pump» получается by construction и верифицируется
(`assembly.fluid_joint_ir`: downhill, приёмник ≥ отдающего по ширине).
Горизонтальный каркас (stepped supports / spacer feet / row carrier) —
VF-4/VF-5; сборка честно объявляет это: `meta: {row_kind: fluid_cascade,
mounting_policy: not_final_rack}`, в water_report — `row.rack_mounting:
deferred`.

**fluid_joint направление**: `a:` — отдающая сторона (несёт `channel_floor_
z_outlet`), `b:` — принимающая. Перепутал — получишь говорящий FAIL.
Joints перечисляются в порядке цепочки (pipeline-guard отказывает joint'у,
чей `a:` ещё не позирован).

**inlet_cap_v1 — drip tower, не мини-rail**: пологий канал в 40-мм теле дал
бы уклон ~31° — честная форма = вертикальный push-in бор (Ø tube_od+0.4)
сквозь спаут-язычок, ныряющий в inlet-коридор rail (ширина ≤ channel_w − 2:
спаут опускается НИЖЕ пола seat в сам желоб). Один прямой путь — карманов
нет by construction, чистится ёршиком сверху.

**collector_endcap_v1 — Γ catch tray**: лоток под overflow-кромкой
(catch_fall 8.5 — глубже rail-to-rail шага, чтобы круглый дренажный бор
влез ЗАКРЫТЫМ под кромкой лотка), пол наклонён к дренажу
(`form.collector_tray_drains`: монотонность + бор в нижней точке +
сквозной), tuck-полоска пола заходит под relief-нишу rail — вся полоса
капели накрыта.

**saddle_hang — auxiliary verification joint.** Не реализует fluid-порты
(нет в `joints` fluid-типов → `no_orphan_ports` его не считает — закреплено
тестом). fluid_joint задаёт позу; saddle_hang доказывает, что в этой позе
седло реально страддлит стенку (люфт 0.2–2.0/сторону), лежит на её верхе
(±0.3) и язычок влезает в коридор.

**hose_port** — новый interface type: neutral, без realizing joint
(прецедент cable_pass) — мейтит внешнее железо; трубка попадает в BOM,
не в printed mates.

**BOM-lite (A2-lite)** — `assembly/bom.py`, derived-only: printed_parts из
частей сборки, silicone tube из hose_port-портов, aluminum profile из
profile-пазов, screws из screw_joints (в row их нет — и в BOM их нет).
Никаких HardwareSpec / catalog/data/hardware/ — эти имена зарезервированы
за A2; BOM-lite станет её первым клиентом.

**Row water report** (`water_report.yaml`): к прежним полям добавлен блок
`row:` — kind/z_step_policy/rack_mounting, cells + per-cell drops +
cassette_contact, handovers (from/to/status/drop_mm), total_drop_mm
(глобально через позы), saddle_mounts, orphan_fluid_ports. Одноячеечные
сборки сохраняют прежнюю форму отчёта (обратная совместимость).

**CAD acceptance двухуровневый**: в suite — 4-частная
`vertical_farm_row_smoke` (обе передачи + оба седла + отчёты); полный
8-частный row — `uv run forge build
catalog/examples/vertical_farm/vertical_farm_row_3x1_petg.yaml`.

## VF-4 Profile-Carried Row Reference (реализовано)

**Golden artifact**: `vertical_farm_row_3x1_carried` — VF-3 каскад,
механически несомый двумя алюминиевыми профилями 2020.

> **Important honesty note.** `aluminum_profile_ref_v1` НЕ представляет
> физически фрезерованный/скошенный профиль. Скошенная верхняя грань —
> **reference-суррогат** СТАНДАРТНОГО ПРЯМОГО 2020/3030, смонтированного
> с глобальным уклоном ряда (позы AF — только 90°). BOM всегда описывает
> железку как standard rectangular profile CUT TO LENGTH, mounted at the
> global slope — никогда как wedge-cut деталь.

- **Уклон носителя ВЫВОДИТСЯ из физики воды** (derived, не declared):
  `row_slope_deg = deg(atan2(module_w·tan(rad(slope_deg)) + FALL_ENTRY,
  module_w))` ≈ 1.827° — «каркас, воюющий с водой» непредставим. Урок
  VF-4: shared-имя `slope_deg` чуть не подсунуло профилю уклон желоба —
  деривация закрыла класс ошибки.
- **process: reference** (новая инфра): внешнее железо в сборке — без
  FDM-чеков (одна честная WARN-нота), STL/STEP экспортируются как
  визуальный референс (`exports.role: reference`), в BOM уходит в
  hardware, никогда в printed_parts.
- **profile_perch** (realizing joint, тип `profile_seat`): паз rail ↔
  верх профиля — локальная посадка (fit 0.1–0.5/сторону). Порты паза
  **optional** — одиночная ячейка и VF-3 каскад легальны; обязательность
  опоры = assembly-фича `row_carried_by_profile` в must_have конкретной
  сборки.
- **Row-чеки в глобальных позах** (`assembly/carrier.py`):
  `row_supported` (каждый rail на КАЖДОМ профиле в своей станции, контакт
  ±0.4 — «не висит на fluid_joint»), `row_pitch_aligned`,
  `profile_slope_feeds_downhill`.
- **Модель контакта (честно)**: плоский паз на наклонной линии — контакт
  по upstream-кромке; зазор к нижней кромке ≈ 7.91 мм РЕПОРТИТСЯ
  (frame_report.span_gap_mm), не фейлится. **VF-4 — verification proof
  привязки к носителю, не финальная эксплуатационная опора: anti-slide
  locking / вибрация / full-surface seating → VF-4.1.**
- **frame_report.yaml**: carrier (size/slope/length/geometry-нота),
  per-rail perched_on + contact, вердикты support/pitch/slope, scope-нота.

## Честный остаток (не в VF-3/VF-4)

- **VF-4.1**: anti-slide клипсы / point pads / end stops — замыкание
  upstream-edge контакта в полноценную посадку;
- `dry_endcap_v1` (механическая заглушка незанятых торцов);
- `vertical_farm_shelf_row_v1` (3–6 ячеек, collector_side) (MVP-4);
- герметичные межмодульные стыки — **никогда** (anti-goal);
- CFD — никогда в v1; проверки — sampled centerline + probe-геометрия;
- рендер сечений/exploded — общий output-слой, не пакетная забота.
