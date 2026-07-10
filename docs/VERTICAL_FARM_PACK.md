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

## Root chamber под кассетой (VF-5A) — param-gate `under_cassette`

`under_cassette: skeleton | root_chamber` — оба режима одного rail.
- **skeleton** (VF-4.1): сквозные окна, −45% пластика, но верхний перелив
  капает вниз (см. overflow_containment).
- **root_chamber** (VF-5A): под кассетой — СПЛОШНОЙ блок с **глухим дном**
  (z0..4 — контейнмент перелива) и открытыми сверху **корневыми желобками**
  (по 2 на сторону, level const-depth, глубина 12). Корни прорастают вниз
  в желобки; вода дренируется **вперёд монтажным уклоном ровно как главный
  канал** — никакой геометрии-уклона (`form.root_chamber_ok`: level,
  full-length, глухое дно ≥2, чист от spine). Желобки соседних модулей
  стыкуются через face_gap → непрерывный дренаж-путь вдоль ряда до
  коллектора (`passive_root_drainage_return` — легализованная отдельная
  подсистема, `no_secondary_water_channel` их исключает; НЕ второй
  пульс-канал).
- **Коллектор** для root_chamber — полноширинный лоток (`tray_w` до 180):
  ловит губу канала (центр) + все корневые желобки по ширине модуля
  (`assembly.collector_catches_root_drainage`; узкий коллектор проливает
  → FAIL). Arm над рельсом (не над ртом) — редизайна не потребовалось.
- **Магниты** в root_chamber — в сплошном периметре (x~84, offset до 90):
  на дефолтном x60 карман попадал в желобок (мокрая зона) — магнит-чеки
  честно падали.
- **Съёмность кассеты** (в water_report `cassette_removal`): чисто до
  прорастания / НЕ mid-cycle (корни в желобках) / end-cycle с урожаем.
  Для микрозелени/салата/трав норма.
- Golden: `vertical_farm_row_3x1_root_chamber` (rails root_chamber, магниты
  x84, полноширинный коллектор 160мм — стенки уходят под профиль x90) —
  overflow_containment: contained.
- **Хекс-соты (закрытые чашки с дренажными прорезями) — VF-5B**, отдельно:
  желобки (VF-5A) уже дают открытые дренируемые корневые зоны; соты добавят
  разделение корней по растениям ценой дренажных прорезей.

## Endcap magnetic docking (VF-6) — `endcap_dock` / `dock_magnets`

Торцевые доводчики (коллектор спереди, inlet-cap сзади) примагничиваются к
крайним модулям ряда. У терминального модуля торцевые межмодульные магниты
«висят вхолостую» — но переиспользовать их напрямую нельзя: они на x=±84,
z=8 у боковой кромки, где коллекторная щека всего ~6 мм (зажата ртом лотка
и профилем x90), а cap туда не дотягивается вовсе (±32). Развилка решена
**вертикальным доком на общем x=±22**:

- **rail** (`endcap_dock: none|front|back|both`, оп `endcap_dock_pockets`):
  пара Z-карманов, открытых **ВВЕРХ** в верх ТОРЦЕВОЙ стенки (z=body_h),
  на x=±`dock_x` (22), inset `dock_inset` (7) от грани — в сухом периметре,
  над желобками (z-разнос 11.6 мм), печать supportless.
- **коллектор/cap** (`dock_magnets: true`): встречные Z-карманы, открытые
  **ВНИЗ** в подошву arm / потолок седла — ровно на интерфейсной плоскости
  контакта (arm ↔ верх стенки, world z=8). Общий x=±22: коллектор берёт его
  полноширинным arm (щёки и профиль ни при чём), cap (±32) свободно.
- Магнит-к-магниту, alignment-only, press-fit, сухая грань — канон как у
  межмодульных.

Чеки:
- `form.dock_pockets_dry` — доковые карманы блайнд, вертикальные (axis Z),
  ≥1.2 до любой мокрой зоны, в press-band (rail + оба доводчика).
- `assembly.endcap_docks_to_rail` — **honesty-closer**: мировые позиции
  карманов доводчика и rail должны совпасть в позе (worst offset ≤1.0);
  магнит без встречного = FAIL («no dock pocket» / «does not mate»). В
  голдене offset = 0.00.

Golden: `vertical_farm_row_3x1_root_chamber` — rail_1 `endcap_dock: back`,
rail_3 `front`, rail_2 без дока; cap + collector `dock_magnets: true`.

## Print-feedback pass (VF-7) — сетка, слив, габариты

Три правки по осмотру напечатанных деталей в Bambu Studio:

- **Сетка кассеты = манифолдный STL.** Печатная кассета приходила с «16
  non-manifold edges» и отдельными сплошными/слипшимися ячейками. BRep
  ВАЛИДЕН — рвётся ТЕССЕЛЯЦИЯ: OCC BRepMesh на одной планарной грани пола с
  ~780 квадратными дырами роняет часть (мельче tolerance — ХУЖЕ: 16→157).
  Порог чистой тесселяции ~450 ячеек → дефолтная ячейка **6→8 мм** (784→~440;
  coco держится в 8 мм). Плюс новый **always-on `manufacturing.mesh_manifold`**:
  тесселирует экспортный меш field-детали, **варит вершины по позиции** (OCC
  отдаёт per-face, на общих рёбрах вершины дублируются — сырой индекс всегда
  «non-manifold»), считает рёбра ≠2 граней → FAIL, если слайсер отвергнет STL.
  Ловит именно тот дефект (cell=6 fail, cell=8 pass); гейт по `form.fields`
  (простые экструзии тривиально манифолдны). В `substrate_mesh_floor.verified_by`.
- **Коллектор сливается насухо.** Слив стоял ВПЕРЕДИ низшей точки пола → вода
  застаивалась сзади. Теперь конец наклонного канала = позиция слива (низшая
  точка совпадает со сливом, сзади ничего глубже), уклон 1.5→2.5° — лоток
  пустеет (`collector_tray_drains`: «empties out the bottom»).
- **Габариты под P1S.** Рельс печатался 251.6×252 при столе 256 → «too close
  to exclusion». Дефолтный модуль **248→205** (печать ~209, ~23 мм зазор до
  256 с каждой стороны), кассета 220→177, шаг 250→207, профиль 780→640.
  Резайз сжимает периметр: фиксированный 20-мм алюминиевый профиль + боковая
  стенка полноширинного коллектора съедают половину-ширины → желобки
  `trough_w` 26→18, модульные магниты уходят ЗА профиль (`magnet_x_offset`
  ~95, band до 106), коллектор `tray_w` 160→120. **~200 мм модуль — пол
  дизайна**: ниже коллектор не помещается между желобками и профилем без
  смены схемы. Root_chamber-golden перенастроен; базовые VF-голдены запинены
  на 248 (fixture'ы). Cassette Interface Standard: номинал сетки ~207.
- **Cap печатается без поддержки** (VF-7c). As-modeled седло открывается ВНИЗ
  — широкий мост, внешняя губа висит («floating cantilever» в Bambu; движковый
  `manufacturing.overhang` это НЕ ловит — слепая зона: IR-чек не моделирует
  мост-потолок седла). Новая print-ориентация **`saddle_up`** (`orient_for_print`,
  flip 180° вокруг X, запекается ТОЛЬКО в экспорт — парт-фрейм и все валидаторы
  не тронуты): седло становится рецессом ВВЕРХ (чистый карман, без моста),
  спаут — восходящим ребром, плоская вершина drip-tower ложится на стол.
  Оп `inlet_cap_body` ставит ориентацию сам; голдены-ряды объявляют её у cap.
  Support-free обоснован геометрией; финальное подтверждение — в слайсере
  (движок мост седла не верифицирует).

## Drain screen basket + слой обслуживания (VF-8)

Ряд рециркулирует: слив коллектора → (внешний резервуар + насос) → inlet
cap следующего ряда. Coco-крошка и обрывки корней в сливной воде забивают
насос/трубки и пачкают следующий ряд. Решение — **съёмная корзина-фильтр в
сампе коллектора над сливом** (вынул, сполоснул, вставил): одна печатная
деталь, никакой доп. обвязки, плюс машинно-выводимый отчёт обслуживания.

Честный итог (НЕ «чистая вода»): **вода с пониженным содержанием мусора** —
сетка снимает крупную coco-крошку и фрагменты корней, мелкая coco-пыль может
пройти; засор виден ОТКРЫТО (лоток коллектора наполняется на виду, без скрытого
back-up).

**Fail-safe семантика (три режима, разрешают конфликт no-bypass ↔ overflow):**
- `normal_no_bypass` — ОБЯЗАТЕЛЕН: вся вода к сливу идёт через сетку/прорези,
  фланец корзины садится в рецесс седла и перекрывает боковой аннулюс — обхода
  посадки нет.
- `emergency_visible_overflow` — ОБЯЗАТЕЛЕН: засор виден как подъём уровня в
  ОТКРЫТОМ лотке коллектора; скрытого объёма back-up нет.
- `emergency_unfiltered_bypass` — **ВЫКЛ по умолчанию**, только явный opt-in.
  По умолчанию обод корзины стоит ВЫШЕ пути перелива лотка → засор проливает
  открытый лоток на виду и НИКОГДА не перехлёстывает корзину к сливу (мусор не
  уходит дальше). Опустить обод ниже перелива можно ТОЛЬКО через
  `allow_emergency_bypass: true` у стыка — и тогда отчёт это флагует.

**Геометрия = LOWERED SUMP + RADIAL FUNNEL (VF-8.1, разворот по фидбеку
пользователя «не экран поперёк канала, а сливное ведёрко в колодце»).** Новый
примитив кернела **`FunnelCutFeature`** — первый пол, наклонный СРАЗУ по X И Y
(`ChannelCutFeature` умеет уклон только по Y): сходящийся книзу (при желании
скошенный — разные центры верх/низ) фрустум, вычитается ruled-лофтом
(cad/bores.py `cut_funnel`, тот же механизм, что у канала). Коллектор
(param-gated `screen_seat`): пол лотка сходится ВОРОНКОЙ к центральному колодцу
со ВСЕХ сторон, слив в АБСОЛЮТНО нижней точке колодца, компактная съёмная
корзина-ведёрко садится В колодец над сливом — **вода падает В корзину, а не
упирается в стену**. Слив сдвигается от задней стенки к центру лотка (`y_drain`
центрируется в arm-clear зоне, `drain_extension` добавляется), воронка скошена
(устье у слива, раструб раскрыт вперёд над лотком) — дренирует весь пол. Плюс
вертикальная **шахта** (устье→rim) открывает крышу над колодцем, чтобы корзина
опускалась и щётка доставала (дренируется воронкой+бором ниже). Off по умолчанию
→ существующие коллекторы байт-в-байт не тронуты.

**Корзина** — компактная sink-filter чашка (`substrate_tray_body`→`lift_tabs`→
`screen_wall_slots`): мелкая донная сетка 2 мм + широкие вертикальные прорези во
ВСЕХ 4 стенках (мелкий поддон в неглубоком лотке даёт мало донной сетки — стенки
несут основную фильтр-площадь). Инварианты: **открытая площадь ≥ ~300 мм²**
(≈4× сливного бора Ø9.4; факт ~334) — сетка не душит поток; **резервуар мусора
≥ 3 мл** (факт ~3.3). Собственный `screen_wall` (НЕ shared `wall`) — толстые
рельсовые стенки ряда не утолщают маленькую чашку.

**Оси проверок (VF-8.1):**
- form: `collector_sump_is_lowest_point` (колодец ниже пола лотка, бор из его
  дна), `tray_floor_slopes_to_sump` (воронка сходится к сливу со всех сторон),
  `basket_not_transverse_flow_barrier` (раструб шире устья + утоплен → вода
  падает внутрь, не перегорожен лоток), `no_standing_water_before_screen`
  (монотонный спуск к сливу), `screen_open_area_ratio_ok`, `screen_debris_capacity_ok`;
- assembly (IR-чек стыка `drop_in_screen`): `screen_normal_no_bypass`
  (корзина накрывает слив, mesh-only, anti-shift, tool-free, обод выше перелива
  иначе FAIL без `allow_emergency_bypass`), `drain_inside_screen_footprint`
  (слив в футпринте корзины в позе), `screen_removable_from_sump` (обод возвышен,
  прямой съём);
- реюз `manufacturing.mesh_manifold`, `topology.single_connected_solid`,
  `form.lift_access_ok`.

**Отчёт обслуживания.** `water_report._row_water(...)` получил блок
`maintenance` (drain_screen: «rinse», honest_note «DEBRIS-REDUCED water»;
collector/channel/tubes/cassette — по присутствующим деталям; `all_tool_free`,
`service_interval_hint: grow-test`). Строки появляются только для реально
присутствующих деталей.

**Pump topology (док-нота, не геометрия):** `слив коллектора --(gravity)-->
резервуар --(насос)--> inlet cap`. НЕ «насос сосёт напрямую сквозь корзину» —
прямое всасывание забивает сетку быстрее, тянет воздух и наносит мусор на меш.
Сетка стережёт gravity-путь до резервуара; насос берёт из отстоявшегося
резервуара.

**Mate = ДАТУМ, не порт.** Стык корзина↔колодец — по датумам `screen_seat`/
`seat` + `drop_in_screen` + честность через `assembly.screen_normal_no_bypass`
(прецедент `saddle_hang`/`hose_port`), без interface-порта: female-порт колодца
(+Z) под скошенной геометрией не имеет чистой наружной нормали, а реестр
INTERFACE_TYPES заморожен на 11 A1-типов. **CAD-acceptance** (strict `forge
build` ловит то, что pre-CAD validate пропускает — закрыто дешёвым
`test_root_chamber_row_builds_strict`): щётка достаёт весь пробег канала
(`brush_access` — шахта открывает крышу над задней половиной колодца);
`no_standing_water` не флагует колодец (сквозной вертикальный бор дренирует его,
exemption `_pocket_drained_by_through_bore`); `no_interference` pass (корзина
падает в открытый колодец, не врезается); mouth колодца = OUTER корзины +
2·clr (гэп 0.75 в band). Обоснованная эволюция первого VF-8 (слив в углу →
центральный воронка-колодец), которая заодно устранила класс проблем
«корзина в глухом углу».

Golden: `vertical_farm_row_3x1_root_chamber` — коллектор `screen_seat: true`,
деталь `screen` (`drain_screen_v1`), стык `drop_in_screen`. Честный остаток:
внешний пре-фильтр резервуара/насоса (обвязка); круглый юбочный slot-mesh
(нужен cylindrical «slots»); двухступенчатая крупно+мелко сетка (не выбрана);
точный размер ячейки vs скорость засора — grow-test (агрономия CAD'ом не
верифицируется).

## Universal rail — floored lip-seat receiver, без сквозных дыр под водой (VF-9)

VF-8 сделал `rail_1` особым (`inlet_mode: capped`) — костыль от двух симптомов
ОДНОЙ проблемы: сквозной, открытый снизу приёмник `lap_in_lap_receiver` под
жёлобом. Он (1) заставлял cap кормить особый capped-рейл и (2) на КАЖДОМ стыке
рейл↔рейл оставлял открытую вниз дыру прямо под водой — «будет вытекать», не
«контролируемая протечка». Корень — сама идея сквозного приёмника (чтобы
сплошное дно не давало дамбу при ΔZ=0).

Инверсия (VF-9): рейл снова **УНИВЕРСАЛЬНЫЙ**, а приёмник — top-open **FLOORED
lip-seat**: карман опущен ровно на `lip_t + clearance` ниже пола канала, со
**сплошным дном**. Губа соседа садится в него, `верх губы = пол канала` —
непрерывная водная поверхность (нет дамбы), при этом **нет дыры вниз**. Тот же
floored-карман ловит и каплю cap (не проваливается) — поэтому `rail_1` перестаёт
быть особым, а cap больше не обязан доставлять воду вовнутрь.

- `_lap_inlet_receiver`: `pocket_floor = channel_floor − (lip_t + lip_clearance)`
  (по умолчанию 1.4 + 0.3 = 1.7 мм), карман z от `pocket_floor` до `floor+0.2` —
  мелкий (глубина ≤ 2.2, exempt в `no_standing_water_ir`). Публикует
  `lap_pocket_floor_z`, `lap_pocket_depth`. Никакого `inlet_mode`/`inlet_capped`.
- `check_lap_joint_geometry_ok` / `lap_slot_leak_path_controlled` переписаны:
  приёмник ДОЛЖЕН быть floored (`z0 > 0.05`, floor = `lap_pocket_floor_z`); нет
  открытого пути вниз, открыт только верхний tip-slot на стыке.
- Новые form-чеки: **`lap_receiver_has_floor`** (сплошное дно),
  **`lap_receiver_residual_volume_ok`** (это lip-SEAT, глубина ≤ 2 мм, не
  резервуар — репортит `lap_receiver_residual_volume_mm3`),
  **`rail_universal_inlet_accepts_cap_and_lap`** (один floored-вход ловит и каплю,
  и губу).
- **Инвариант `manufacturing.no_through_holes_in_wet_lap_zone`** (always-on): ни
  один cutbox с открытым дном (`z0 ≤ 0.05`) не стоит под активным водным путём
  (регионы `water_channel`/`lap_receiver`/`lap_lip`), КРОМЕ санкционированного
  слива коллектора. PASS после floored-фикса; FAIL если вернуть сквозной приёмник.
- Assembly-чеки: **`assembly.lap_joint_no_external_downward_leak`** (стык lap_flow —
  приёмник закрыт снизу) и **`assembly.cap_drip_lands_in_channel_safe_floor`** (cap↔
  rail.feed — капля падает на channel-safe дно, не в сквозную дыру), оба в
  `row_water_chain.verified_by`.
- Голдены: у `rail_1` убран `inlet_mode: capped` — все рейлы одинаковы.

Архитектура ряда: `универсальный рейл (floored-приёмник + губа-выход, без мокрых
сквозных дыр) → lap-переток без внешней протечки вниз → collector = единственный
намеренный слив вниз`. CAD-проба (rail_2): под колонкой feed теперь solid (было
0.00 сквозное); мелкий seat-паз выше, сплошное дно ниже.

## Support-free Г-hook cap (VF-9 Part B)

Старый cap печатался только через `saddle_up` flip: as-modeled потолок седла —
плоский мост над ~14мм с висящей внешней губой («floating cantilever», Bambu
флагает; движковый `manufacturing.overhang` это НЕ ловил — слепая зона VF-7c).
Задача Part B — печать AS-MODELED без flip.

Геометрическое открытие: **двусторонний straddle через ~13мм стенку нельзя
напечатать support-free** — над проёмом стенки (в печати самой детали стенки
нет) внутренняя губа плеча всегда висит; gable над плоскостью z=8 не помогает
(потолок на z=8 всё равно над воздухом). Единственные support-free варианты —
односторонний hook или reorient/flip. Решение (утв. пользователем): **compact
one-sided Г-hook + face dock**:
- Короткая полка-опора (**hook_reach ~3.5мм**, `HOOK_LEDGE_BAND`) ложится на
  ВНЕШНИЙ край верха стенки; внешняя нога/foot держит +Y-грань и достаёт до
  стола. Полка = 4.4мм one-sided overhang (печатается), НЕ 14мм cantilever.
- **Nose column** над каналом (`|x|<nose/2`) достаёт до стола, несёт вертикальный
  бор (прямой слив, чистится сверху) и служит внутренним анкером крыши над
  каналом (bridge, не cantilever); тянется вглубь на ~10мм — сплошные стенки по
  бокам бора (иначе полый столбик не «ребро» для `topology.ribs_present`).
- Убрана выпирающая spout-пластина; `print_orientation: as_modeled`, flip удалён.
- **Магнитный док перенесён с верха стенки на вертикальную +Y-грань**
  (Y-оси карманы): док на верху стенки требует ~7мм inboard-полку (un-printable
  overhang), а вертикальная грань печатается чисто. Rail-амендмент VF-6:
  `endcap_dock_style: top|face` (top=Z-карманы верха, collector; face=Y-карманы
  торца, cap). `dock_drop` — общая просадка от верха стенки, чтобы cap и rail
  сошлись по мировому z. `_endcap_dock` (carrier) и `check_dock_pockets_dry`
  умеют обе оси.
- `saddle_hang_ir` получил hook-ветку (гейт `hang_mode`): проверяет ledge reach
  (`HOOK_LEDGE_BAND`, ≤ толщины стенки), leg gap у грани, посадку на верх стенки;
  collector остаётся straddle (без изменений). Hook **не зависит от толщины
  стенки** (цепляет внешний край) — mismatch толщины больше не failure mode.
- Новый always-on **`manufacturing.cap_supportless_verified`** (закрывает
  VF-7c): полка-overhang ≤ `CAP_ROOF_OVERHANG_MAX=5` И nose достаёт до стола;
  старый плоский 14мм cantilever → FAIL.

CAD-acceptance: flush_smoke (cap без дока) И root_chamber (cap с face-доком) —
оба strict PASS, no_interference/ribs_present/single_solid/overhang/
cap_supportless_verified зелёные. Corbelled L-hook (двусторонний capture+nose)
и gabled roof остаются возможной эволюцией после физической печати.

## Chute-cap (VF-9.2) — видимый водный путь, упор для трубки

Пользователь на собранном `out/` увидел, что бор cap читается как «сквозной
тоннель»: константный Ø9.4 на всю высоту — трубку можно продавить НАСКВОЗЬ
(упора нет), а форма не объясняет путь воды. Правило (закреплено валидатором):
**cap не должен содержать закрытый горизонтальный водный тоннель — путь воды
виден глазами**. Вариант B (утв. пользователем): **chute-cap**.

Путь воды: `трубка → вертикальный SOCKET с УПОРНЫМ БУРТИКОМ (глухое дно,
Ø tube+0.4, глубина 12) → узкий DRIP ORIFICE Ø5 сквозь упор → короткая крытая
КАМЕРА (шахта падения ≤10мм по Y) → ОТКРЫТЫЙ СВЕРХУ носик-жёлоб (U-корыто:
пол + 2 стенки-рёбра) → капля с кончика падает на floored lip-seat, DRIP_INSET
= 4.5мм ВНУТРИ канала` — дальше воду ведёт сам канал под уклоном ряда. Ровный
пол жёлоба дренируется уклоном монтажа (как канал рейла — канон).

- Сквозной Ø9.4 бор и монолитный нос УДАЛЕНЫ; крыша над жёлобом прорезана «в
  небо» (sky slot) — путь чистится щёткой сверху и виден.
- **Парный сдвиг датумов**: `feed` рейла и `spout` cap оба на −DRIP_INSET —
  поза ряда байт-в-байт, датумы честно отмечают реальную точку капли.
- Чеки: `hose_bore_ok` (socket ОБЯЗАН быть глухим — сквозной socket без упора
  = FAIL; orifice 4..tube−2, соосный, стыкуется с дном socket'а);
  `spout_drop_path_ok` (пол+обе стенки, кончик = spout-датум, ширина в бюджете
  канала); **новый `form.cap_water_path_visible`** (камера ≤10мм, sky-проём до
  верха, нет горизонтальных боров в мокрой зоне); `no_standing_water_ir` —
  экземпшен «глухой бор дренируется соосным orifice снизу» (заглушенный socket
  без orifice остаётся FAIL); **`topology.fluid_path_open` переписан** — cap
  пробится ОДНОЙ составной полилинией (socket→orifice→камера→вдоль жёлоба→за
  кромку), никогда не требуя void ниже упора; **новый assembly
  `cap_chute_drains_under_mount`** — виртуальные высоты обоих концов жёлоба В
  ПОЗЕ смонтированного ряда (уклон ведёт воду к носику; без mount_context —
  честный FAIL).
- Инвариант архетипа: `orifice_d <= tube_od - 2` (упор реален).
- Грабли: рёбра свариваются ПОСЛЕ вырезов и по порядку списка — пол жёлоба
  (z<0) обязан вариться ПОСЛЕ ног/стенок (иначе WeldError «2 solids»); U-ноги
  вокруг камеры (цельная ступня заполнила бы её обратно).

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
