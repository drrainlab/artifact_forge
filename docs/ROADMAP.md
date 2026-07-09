# Artifact Forge — мастер-план: инженерная грамматика сборки

Позиционирование: **Artifact Forge — платформа параметрического создания
функциональных артефактов**: инженерных изделий, крепежей, оснастки,
кино-реквизита, носимых конструкций и биоморфных объектов. Не «AI CAD
generator», а parametric artifact atelier: одно ядро, несколько режимов
(см. «Режимы поверх одного ядра»).

Цель: AF — не каталог отдельных изделий, а **система сборки конструкций из
проверенных функциональных «органов»**. Архетипы и модификаторы — только
словарь. Сложность изделий рождается не из количества деталей, а из
способности системы понимать, как детали соединяются, какие силы через них
проходят, как это печатать, собирать, обслуживать и как это сломается.

```text
Catalog
+ Interfaces (ports/mates)
+ Assembly Graph
+ Constraint Solver
+ Physics-lite
+ Manufacturing Planner
+ Failure Critic
+ Workshop Memory
+ Modes (Engineering | Workshop | Cinema | Fashion | Creature)
= генератор функциональных артефактов
```

Принцип развития: **меньше архетипов — больше интерфейсов, solver-ов и
валидаторов**. Каждая волна подчиняется канону honesty: фича без
validator-backed геометрии = галлюцинация; волна закрыта только когда есть
golden-пример + тесты + измеряемые проверки.

Этот документ — главный роудмап. [BUILDERS.md](BUILDERS.md) остаётся каноном
слоя билдеров, [BIOMORPHIC.md](BIOMORPHIC.md) — каноном био-раздела; их
«честные остатки» поглощены волнами ниже (см. «Поглощённые дорожки»).
Коммерческая, лицензионная и pack-модель (open-core, пять осей
Modes/Packs/Environments/Styles/Tiers, Free/Certified/Pro, линия PK) —
канон [ECOSYSTEM.md](ECOSYSTEM.md).

---

## Режимы поверх одного ядра

Четыре аудитории — инженеры, мейкеры, киношники, фэшн-дизайнеры — это НЕ
четыре платформы. Ядро одно (archetypes + modifiers + ports/assembly +
materials/manufacturing + validation + export); **режим = профиль
приоритетов** поверх него: дефолтные requirements (волна A3), состав
production package (волна A2), набор гейт-валидаторов и стиль-пресеты.
Режим не имеет права ослаблять honesty — он меняет, ЧТО важно, а не ЧТО
проверяется.

| Режим | Главные приоритеты | Специфичные сущности (словарь режима) |
|---|---|---|
| Engineering | прочность, крепёж, допуски, нагрузки, BOM, STEP | — (сегодняшний дефолт) |
| Workshop | системность крепления, совместимость, экономия пластика | rail/dovetail-интерфейсы, единый шаг (волна A4) |
| Cinema / Props | силуэт, стиль, скорость печати, разборность, покраска, вес | hero/stunt/background_prop, paintable_surface, LED_channel, rigging_point, hidden_mount, quick_repair_joint |
| Fashion / Wearable | тело, движение, комфорт, вес, безопасность краёв, размерная сетка | body_anchor, strap_slot, fabric_stitch_hole, skin_clearance, flex_zone, quick_release, size_grading |
| Biomorphic / Creature | выращенность формы, органика поверх честного ядра | канон BIOMORPHIC.md + implicit skin Bio-4M — мост между всеми режимами |

Архитектурное следствие **уже сейчас** (чтобы не ломать схемы под
кино/фэшн потом): язык ядра нейтрален — «artifact», не «mechanical_part»;
новые region-роли (body_contact_region, fabric_interface, paint_surface)
добавляются строго по закону «роль приходит со своим потребителем»
(BIOMORPHIC.md) — enum не раздувается заранее, но и не зашивается
инженерная семантика туда, где хватает нейтральной.

---

## Где мы сейчас (статус на 2026-07-05)

✅ = реализовано · 🔶 = частично / в другом слое · ⬜ = не начато

| Слой концепции | Статус | Где сейчас |
|---|---|---|
| Полезные одиночные изделия (AF v1) | ✅ | 26 архетипов, 14 модификаторов, recipe kernel R1, honesty-пайплайн, 487 тестов |
| Assembly Graph | 🔶 | `assembly/v1`: typed-сборки, root+joints, позы quarter-turn, fit-пробы в позе, wiring-проверка (`product/assembly.py`, `assembly/joints.py`, `assembly/pipeline.py`). Плоский список joints, не иерархический граф |
| Ports / Interfaces / Mates | ✅ | A1+A1.5: реестр 11 типов, InterfaceSpec c frame (normal/up/axis), mate+frames-валидация, fluid_joint, `forge compat` v2, swap-харнес, легаси ретрофичены |
| Functional Grammar (verbs) | ⬜ | intents `forge edit` — зачаток; функционального плана (clamp_around → support_payload → route_cable) нет |
| Constraint / Param Solver | ⬜ | `product/resolve.py` — линейный однопроходный resolve (units/expr/clamp), обратных задач и компромиссов нет |
| Load Path Analyzer | 🔶 | точечно: snap strain 1.5·δ·t/L², `form.stability_footprint` (COM), min_web; `load_paths:` на био-архетипах (Dijkstra по rib-графу). Цепочки момент → крепёж → стенка → запас нет |
| Hardware / Fastener Ontology | 🔶 | `core/fasteners.py` (M2–M5, heatset, гайки, E27/GU10), PORT_SIZES, подшипники 608/625/6001 — разрозненные таблицы без единой схемы |
| Assembly Planner / BOM | ⬜ | `assembly_report.yaml` есть (позы/joints/grade), но BOM, шаги сборки и build package не генерируются |
| Manufacturing Planner | 🔶 | bed_fit, min_wall, overhang (знает `print_orientation`), max_opening_span, sideprint «ноль нависаний by construction». Нет split-стратегии и материальных профилей |
| Failure Mode Critic | ⬜ | findings-механика готова, критика отказов как слоя нет |
| Design Memory / Workshop Feedback | ⬜ | repair-ledger есть; `build_observation` из мастерской не существует |
| Product System Templates | ⬜ | пара кронштейн+чашка стыкуется datum-ами — прецедент, не система |
| Design Intent / Requirements Model | 🔶 | `requested_features` + capability report (built ⊆ supported) — плоский список фич, не структурированные требования |
| Region Editor + Visual Grounding | 🔶 | Cockpit: Region-линза, patch-preview; NL-edit по выбранному региону не закреплён |
| Compatibility Matrix | ✅ | `forge compat` — выводится из деклараций портов, рукописной не существует |
| Multi-Resolution Design (L0–L5) | ⬜ | сегодня вход сразу на уровне product YAML (L2) |
| Режимы поверх ядра | 🔶 | mode scaffold P2: `mode:` + MODE_PROFILES (product/modes.py), wearable требует body_fit; приоритеты/пакеты — впереди |
| Body / Human Fit Layer | 🔶 | P2 ядро: body_fit (forearm) + forearm_cuff_v1 grade A; wrist/thigh и size grading впереди |
| Soft–Hard интерфейсы | 🔶 | zip-tie слоты, TPU-рекессы, магнитные карманы + **add_strap_slots** (стропы 15–40мм, P2); нет sew/velcro/elastic/foam/LED |
| Style Grammar | 🔶 | biomorphic_utility_part + BIOMECHANICAL_EXOSKELETON + **Bio-4M implicit SDF skin** (STL-first, honesty экспорта); один стиль-род, не грамматика стилей |
| Production Package per mode | ⬜ | базовый пакет — волна A2; cinema/fashion-варианты — волна P4 |

Итог: **AF v1 закрыт, assembly/v1 — уже половина AF v2.** Дальше три
макро-этапа: A-волны (composable system), E-волны (engineering reasoner),
M-волны (self-extending platform) — плюс параллельные линии Bio
(BIOMORPHIC.md), P (Props & Wearables, ниже) и VF (Vertical Farm,
docs/VERTICAL_FARM_PACK.md).

### Линия VF — Vertical Farm Pack (статус на 2026-07-07)

**VF-1 (MVP-1 + MVP-1.5 + MVP-2) ✅**: transient water contract
(`ChannelCutFeature` — первая не-осевая вырезка кернела), water_rail_v1 /
coco_cassette_v1 / substrate_retainer_frame_v1, Cassette Interface Standard
(shared-параметры + frame-ключи + joint `removable_insert`), joints
`removable_insert`/`tongue_groove`, water_report.yaml + views-метаданные,
golden-примеры water_rail_cell_2020_petg (3 части) и two_cell_line_petg.
Assembly pipeline научился композировать цепочки joints через
не-повёрнутого родителя (rail → cassette → frame).

**VF-3 Fluid Row ✅ (2026-07-07)**: первое настоящее assembly-system
доказательство — 3-cell fluid cascade row (`vertical_farm_row_3x1_petg`):
inlet cap (drip tower) → 3 rail-ячейки с кассетами → collector endcap
(catch tray), все передачи — реальные `fluid_joint` (первый клиент;
downhill by datum-construction, verified), адаптеры на `saddle_hang`
(auxiliary verification joint), required fluid-порты без сирот, row-level
water_report (cells/handovers/total_drop) и **BOM-lite** (derived-only —
семя A2: printed parts, silicone tube из hose_port, aluminum profile;
никаких HardwareSpec до A2). VF-3.0 попутно закалил интерфейсное ядро:
fluid-датумы = точки передачи воды, axis = направление потока, ordering
guard цепочек joints, композиция поз через непрокрученного родителя,
width-rule «приёмник ≥ отдающего», тип `hose_port`, `AssemblyInstance.meta`.
⚠️ row — каскад (каждая ячейка ~7.9 мм ниже), НЕ финальная стойка.

**VF-4 Profile-Carried Row Reference ✅ (2026-07-08)**: каскад
механически привязан к РЕАЛЬНОМУ алюминиевому носителю —
`vertical_farm_row_3x1_carried`: 2 стандартных прямых 2020-профиля под
глобальным уклоном ряда (reference-суррогат со скошенным верхом — позы
только 90°; honesty note везде), `process: reference` (внешнее железо без
FDM-чеков — профили, трубы, стекло, насосы в будущем), joint
`profile_perch` + row-чеки в глобальных позах (row_supported /
pitch_aligned / slope_feeds_downhill), **уклон носителя ВЫВОДИТСЯ из
физики воды** (derived row_slope_deg — «каркас против воды» непредставим),
frame_report.yaml, профиль в BOM как cut-to-length. Порты паза optional —
старые goldens не тронуты; обязательность опоры = фича
row_carried_by_profile в must_have carried-сборки. Контакт по
upstream-кромке (span gap 7.91 репортится честно) — verification proof,
не финальная опора.

**VF-Correction: Tilted Flush Water Rail ✅ (2026-07-08)**: каскад признан
design mistake и заменён каноном **tilted_flush_row** —
`water_rail_v1` переписан IN PLACE (v2): желоб ПОСТОЯННОЙ глубины (уклон
целиком у монтажа: `mount_context` 1.0–2.0°, чек
`assembly.row_drains_under_mount` по виртуальным высотам, порядок цепи из
lap-joints — реверс ловится), flush-модули (ΔZ=0, face_gap 0.3–0.6, шаг =
module_w + face_gap), **lap_flow_joint** (губа-продолжение пола в сквозной
открытый снизу проём; слот 0.5–2.5 = осознанная негерметичность с
контролируемым leak-path — `form.lap_slot_leak_path_controlled`),
запечатанные магнитные карманы (alignment only), **lightweight dry shell**
в опе (−40% пластика, param-gated, обратимо; generic-модификатор
`lightweight_dry_shell_v1` — следующая волна), профиль-референс стал
БУКВАЛЬНО прямым (slope 0, полная посадка, span gap 0 — чек), адаптеры
перемейчены (cap→`feed` — единственное падение ряда; collector→`drain_edge`
— кончик губы, hang_drop derived без каскадного члена). Каскадные goldens
удалены (история в git); новые: `vertical_farm_row_3x1` (магниты on) +
`vertical_farm_flush_smoke`. Отчёты: water (tilted_flush_row, virtual
drop, lap_seam_leak: controlled), frame (full seating, span_gap 0), BOM
(«mount the WHOLE row at 1.5 deg», магнитная строка).

**VF-4.1 Printability & Collector Hardening ✅ (2026-07-08)**: коллектор
стал КОНЦЕВЫМ receiver'ом финальной lap-губы (capture 6–8, щёки вокруг
мокрой зоны, низкий apron-бортик 2.4–3.5 — не стена: открытый верх +
непрерывность с лотком = промываемость чеком `receiver_open_top_cleanable`;
в позе — captures/envelopes/removable_by_hand); окна облегчения → СКВОЗНОЙ
скелет (мостов нет by construction, −45%; `cassette_support_span_ok` —
кассета накрывает всё, worst span ≤45); `BoreFeature.roof=teardrop`
(45°-хорды, дренаж коллектора supportless); always-on
`supportless_lightweight_windows_ok` (slab-проба на солиде — до этой волны
мосты плоских потолков НЕ мерялись никем) + `horizontal_bore_supportless`;
`manufacturing.print_orientation` в контракте инстанса; магниты press-fit
0.1–0.3 из сухой стыковой ±Y грани (правило чеком) + magnet_installation
в frame_report.

**VF-4.2 Collector Robustness + Overflow Honesty ✅ (2026-07-08)**:
коллектор из «висящих столбиков» → жёсткая U-рама (две полные боковые
стенки ≥3.5 от дна до arm несут консольный лоток; `collector_structure_
sturdy` закрывает слепую зону min_wall) + слив стал ВЕРТИКАЛЬНЫМ вниз
(трубка входит снизу, уходит под ряд; teardrop с коллектора снят,
кернел-примитив жив для будущих гориз. боров); честная нота
`overflow_containment` в water_report (сквозной скелет пропускает верхний
перелив — до VF-5 корневой камеры).

**VF-5A Root Chamber ✅ (2026-07-09)**: подкассетный объём param-gate
`under_cassette: skeleton|root_chamber`. root_chamber = глухое дно
(контейнмент перелива) + открытые корневые желобки (level const-depth,
дренируются монтажом вперёд как главный канал — БЕЗ геометрии-уклона; ключ:
широкий поддон дренируется без нового X-примитива, крен ряда делает всё);
канон-amendment `passive_root_drainage_return` (no_secondary_water_channel
исключает root-желобки); полноширинный коллектор ловит губу + желобки
(collector_catches_root_drainage); магниты в периметр (x84); overflow
contained; 3 режима съёмности; golden vertical_farm_row_3x1_root_chamber.
**VF-5B** (хекс-соты с дренажными прорезями) — отдельно: желобки уже
функциональны, соты = разделение корней ценой прорезей.

Впереди: **VF-4.3** anti-slide удержание ряда на смонтированном под
уклоном профиле (посадка полная, продольного замка нет);
**lightweight_dry_shell_v1** generic-модификатор; **VF-5 Cassette Family**
(sprout mesh / microgreen mat / rockwool cube / soil seedling / netpot
кассеты на Cassette Interface Standard; mat-кассеты сделают
`form.substrate_retained_under_mount` реальным чеком); **VF-6** production
readiness (PP food-grade, draft angles, no-undercut report);
`dry_endcap_v1`.

---

## AF v2 — Composable Workshop System (волны A1–A4)

Цель: изделия начинают стыковаться друг с другом. Самый важный скачок.

### A1 — Ports & Interfaces v1 ✅ ядро (реализовано 2026-07-07)

Порты превращают каталог в LEGO Technic: соединение — ДЕКЛАРИРОВАННАЯ,
типизированная, гендерная сущность, а не соглашение между YAML-ами.

Реализовано:

1. **Реестр типов** (`product/interfaces.py`, ровно словарь A1):
   screw_pattern, heatset_insert_pattern, strap_slot_pair,
   cylindrical_payload_socket, dovetail_rail, snap_joint, tongue_groove,
   removable_insert, fluid_inlet, fluid_outlet, cable_pass. Тип знает:
   реализующие joints, frame-ключи каждой стороны, clearance-band,
   fastened-флаг. Типы без joint (fluid_*) — честно «declared ahead».
2. **Общий контракт порта** — `interfaces:` на архетипе: id, type,
   gender (male/female/neutral), datum-якорь, clearance, target region,
   protected keepouts, accepts-фильтр, assembly_role (required/optional).
   Loader биндит fail-fast (регионы/типы/гендер/band); датум — runtime-
   правда, его меряет `interface.frame_exists` на построенной форме.
3. **Валидаторы** (все 7 из ТЗ): interface.frame_exists,
   interface.mate_compatible, interface.clearance_ok,
   interface.fastener_access_ok, interface.keepouts_preserved,
   interface.swap_part_builds (харнес `assembly/swap.py`),
   assembly.no_orphan_ports. Mate-резолюция в `assembly/mates.py`;
   глубина размеров остаётся в joint-IR (без дублирования измерений).
4. **Port-id анкеровка**: `a: cuff.payload_socket` — джоинт целится в
   ПОРТ, не в голый датум (легаси-датумы легальны, полу-декларированное
   соединение — честный WARN).
5. **`forge compat`** — выводимая матрица (7 mates на текущем каталоге,
   включая self-mate рельсы line_east↔line_west); рукописной матрицы не
   существует by design.
6. **`dovetail_joint`** (остаток R4 закрыт): скользящая посадка с
   undercut-ретенцией, clearance-band на сторону, угол фланков, полное
   зацепление, датумная цепочка в позе; осевое удержание friction-only —
   заявлено в отчёте, не спрятано.

**Драйверы-доказательства** (оба golden + swap-тесты):

- *Wearable adapter swap*: `forearm_cuff_socket_v1` (dovetail-корона
  вместо встроенного snap-C) + `flashlight_adapter_25_v1` ↔
  `rail_plate_adapter_v1` — тело манжеты не меняется ни байтом
  (закреплено тестом); сборка `wearables/cuff_flashlight_25.yaml`
  билдится в grade A, фича `swappable_payload_interface` built.
- *Vertical farm cassette swap*: `sprout_cassette_v1` — ВТОРОЙ
  имплементор Cassette Interface Standard: coco ↔ sprout на нетронутой
  рельсе. Swap-харнес по пути поймал реальную несовместимость (окно
  20мм в канале 16мм) — измерено джоинтом в позе, не задекларировано.
- Рассинхрон стандарта непредставим: `shared:` перезаписывает кривые
  параметры свопнутой детали (закреплено тестом).

Остаток A1 (следующие итерации): frame порта с normal/up-векторами
(сейчас только датум), осевой end-stop dovetail, fluid-joints (VF-3),
ретрофит screw/heatset-портов на легаси-архетипы (кронштейн+чашка),
cable_pass-инстансы, интеграция матрицы в Cockpit.

### A1.5 — Interface Hardening ✅ (реализовано 2026-07-07)

Интерфейсный слой доведён из «работает на golden-сценариях» до несущего
стандарта платформы:

1. **Port frames**: `frame: {normal, up, axis?}` на каждом порту —
   осевые токены (±X/±Y/±Z) в духе quarter-turn поз; origin = датум.
   Ортонормальность fail-fast при загрузке; ВСЕ 20 портов builtin-каталога
   оснащены фреймами (окно deprecation для builtin закрыто тестом).
2. **Валидаторы фреймов** (все 4 из ТЗ): `interface.frame_orthonormal`,
   `interface.normal_points_outward` (ray-march по IR-материалу: контур
   минус cutboxes/bores/каналы; male-порты имеют право на протрузию в
   бюджете 20мм; flow-through порты (fluid/cable) законно смотрят в
   пустоту канала; «нет материала сзади» = WARN, инвертированная нормаль
   = FAIL), `interface.up_consistent` (осевая семантика по типам: slide в
   плоскости порта, flow по нормали), `interface.mate_frames_opposed`
   (нормали противонаправлены В ПОЗЕ; orientation-sensitive типы требуют
   согласия up и непрерывности оси — перевёрнутый модуль линии ловится
   на уровне фреймов, не только каналов).
3. **fluid_joint** + кросс-типовой mate (`COMPLEMENT_TYPES`:
   outlet(male) ↔ inlet(female)): handover обязан течь ВНИЗ (gravity is
   the pump) с совместимыми ширинами каналов; первый реальный клиент —
   адаптеры VF-3, физика готова и оттестирована.
4. **Ретрофит легаси**: порты на lamp_bracket↔lamp_socket_cup
   (screw_pattern, frame-ключи mount_bc/mount_bc_n добавлены в билдеры)
   и branch_clamp паре (heatset_insert_pattern); desk_lamp_e27 и
   branch_lamp_clamp_60 проходят mate/frames/fastener-проверки.
   Урок: **auxiliary joints** — compression_gap поверх heatset-датумов
   НЕ реализует порт (едет по нему); реализующий джоинт обязан
   существовать отдельно, no_orphan_ports считает только их.
5. **compat report v2**: фреймы в таблице портов, секция причин
   несовместимости, `stranded required ports` (required-порт без единого
   кандидата в каталоге = осиротевший стандарт).

Остаток: normal/up на wearable strap/cable-портах при их появлении,
per-type протрузионные бюджеты вместо общего 20мм, fluid_d ключ при VF-3.

### A2 — Hardware Ontology + Build Package (BOM) ⬜

Из разрозненных таблиц — единая онтология покупных компонентов; из
одиночного STL — комплект.

1. **`catalog/data/hardware/*.yaml`** — typed HardwareSpec: винты, heatset,
   дюбели (incl. butterfly), подшипники, патроны E27/GU10, магниты,
   стяжки, TPU-пады:

   ```yaml
   id: heat_insert_M4_standard
   hole_diameter: 5.6mm
   boss_min_outer_d: 9.5mm
   boss_min_height: 7mm
   clearance_required: true
   install_direction: Z
   ```

   `core/fasteners.py` становится загрузчиком этой онтологии (существующие
   константы — первые записи, API сохраняется).
2. **BOM выводится**, не декларируется: винты — из screw_joints, вставки —
   из heatset-ops, дюбели — из hardware-ссылок анкерных отверстий.
3. **Build Package Generator**: `parts/*.stl` (каждая в своей ориентации) +
   `bom.yaml`/`bom.md` + `assembly_steps` (порядок из joints: inserts →
   pads → cable → close → bolts) + risk report (существующие findings) +
   рекомендация материала.

Критерий: `esp32_box_with_lid` и `desk_lamp_e27` выдают build package;
тест сверяет количество крепежа в BOM с joints (рассинхрон непредставим).

### A3 — Requirements Model ⬜

Не терять смысл запроса. Блок `requirements:` в product YAML:

```yaml
requirements:
  functional:      [hold cylindrical handle Ø65mm, wall mounted, removable by hand]
  structural:      [support 2kg static load, two fasteners only]
  manufacturing:   [FDM printable, minimal supports, low plastic use]
  aesthetic:       [biomorphic, not boxy]
  safety:          [no sharp contact edges]
```

Каждое требование маппится на features/validators/params; capability report
расширяется до вердикта по требованию: **выполнено / частично / не
выполнено / невозможно**. Прямое развитие `requested_features` и
инварианта built ⊆ supported — та же honesty, уровнем выше.

Критерий: golden-инстанс с требованиями получает пер-requirement вердикты;
невыполнимое требование даёт честный engine_gap, не молчаливый pass.

### A4 — Product Systems v1: Workshop Wall System ⬜

Выше уровня архетипов — совместимая экосистема: рейки, крючки, держатели,
адаптеры с единым шагом крепления и единым rail/dovetail-интерфейсом из A1.

- Спецификация системы: общий interface_profile, единый шаг крепления,
  family/extends/preset (механизм Bio-4A из BIOMORPHIC.md), maturity на
  пресетах.
- Сюда же поглощается `rail_slider` (остаток R5) — рельс системы и есть
  его первый клиент.

Критерий: рейка + 2–3 съёмных держателя; каждая пара подтверждена
`forge compat` и mate-пробами в позе; био-пресеты держателей — поверх тех
же ядер (закон «Bio package не владеет generic mounting logic»).

---

## AF v3 — Engineering Reasoner (волны E1–E4)

Цель: система думает про нагрузки, риски и компромиссы, а не только про
форму. Детализация волн уточняется по завершении A-этапа.

### E1 — Param Solver v1 ⬜

Requirements → derived dimensions → constraints → conflicts → suggested
compromises. НЕ общий CSP: библиотека детерминированных правил вывода
поверх `product/resolve.py` (порядок фиксирован, детерминизм и
воспроизводимость сохраняются). Конфликты — typed findings с предлагаемыми
компромиссами («2 винта + ребро снизу + шире плита»), в духе repair-правил.

Критерий-пример: «держатель для ручки 65 мм, 2 дюбель-бабочки, экономно, но
крепко» → saddle_d, mouth_gap, wall, screw_spacing, rib_count выведены и
каждое значение обосновано ссылкой на правило.

### E2 — Load Path Analyzer (physics-lite) ⬜

Цепочка: нагрузка → рычаг → момент → крепёж → стенка → материал → запас.
Без FEA: `cantilever_moment_check`, `screw_edge_distance_check` (обобщение
min_web), `boss_strength_check`, `heat_zone_material_check`; материальные
профили (PLA/PETG/ASA/PETG-CF) с температурными ограничениями. `load_paths:`
обобщаются с био-архетипов на все силовые архетипы; на уровне сборки force
chain идёт через joints (момент лампы → dovetail → плита → дюбели).

Критерий: golden-кейс «фитолампа 1.2 кг, вынос 180 мм» получает
estimated_moment, risk-грейд и рекомендации, подтверждённые измеряемыми
пробами.

### E3 — Failure Mode Critic ⬜

Отдельный слой «как это сломается»: детерминированное правило-ядро над
IR+assembly (тонкий корень dovetail у босса, канал через силовое ребро,
доступ отвёртки/гайки, острый внутренний угол в TPU-нише, флекс плиты) +
LLM-критик строго как генератор гипотез — каждая гипотеза обязана
подтвердиться измеряемой пробой, иначе она WARN-note, не finding. Выход:
top risks + suggested patches (типизированные, как repair).

### E4 — Manufacturing Planner ⬜

AF думает как 3D-печатник: `split_if: max_dimension_gt` (разрез через
butt_pin/dovetail из A1), ориентация per part, tolerance/nozzle/material
profiles, `avoid_supports_in` (каналы, бобышки, dovetail-пазы),
strength_direction vs направление слоёв (связь с E2). Отдельная забота —
держать биоморфные поверхности в рамках реальной печати.

Клиенты глубокой механики по итерации на штуку (как в BUILDERS.md):
`pin_hinge`, `friction_hinge`, `living_hinge` (усталость), резьбы,
`ratchet_teeth` — каждый приходит со своей физикой и валидаторами внутри
E-этапа.

---

## AF v4 — Self-Extending Platform (волны M1–M3)

Цель: система расширяет себя и учится у мастерской. Крупные мазки —
детализация после E-этапа.

### M1 — Functional Grammar & Multi-Resolution ⬜

Глаголы инженерного действия как внутренний язык: `attach_to_wall`,
`clamp_around`, `support_payload`, `route_cable`, `snap_fit`,
`split_for_printing`, … Запрос раскладывается в функциональный план, потом
в геометрию:

```text
L0 functional block diagram → L1 layout volumes → L2 Form IR
  → L3 CAD solids → L4 manufacturing split → L5 print package
```

Здесь же слот LLM-фазы 4: LLM — переводчик intent → функциональный план /
requirements (A3); подбор архетипов и портов делает движок. Поглощает
«R5 assembly-intents» из README.

### M2 — Design Memory / Workshop Feedback Loop ⬜

Каждое напечатанное изделие возвращается в систему:

```yaml
build_observation:
  artifact_id: wall_tool_mount_65mm_v1
  print_success: true
  assembly_success: partial
  field_test: failed_after_2_days
  notes: "wall plate flexes"
  recommended_catalog_patch: [increase_backplate_ribs, add_triangular_buttress]
```

Observations → ledger → рекомендованные catalog-патчи (через существующий
repair-механизм). Главный moat проекта: накопление реального опыта печати
и эксплуатации, не абстрактное «обучение».

### M3 — Catalog Authoring Pipeline ⬜

Саморасширение каталога: анализ запроса → YAML-вариант / composite / recipe
на существующих ops / новый builder через sandbox → golden-тесты →
benchmark suite → промоушен по maturity-лестнице (`draft → … →
production_buildable`, уже введена в BIOMORPHIC.md). Новые builders
рождаются как draft/coding-agent task, никогда как произвольный Python в
runtime (закон из BUILDERS.md).

---

## Параллельная линия P — Props & Wearables (волны P1–P4)

Расширение аудиторий: кино (production design + functional fabrication) и
фэшн (parametric atelier). Линия параллельна A/E-волнам, как Bio-линия;
опирается на A1 (порты), A2 (пакеты), A3 (requirements). Биоморфная линия —
её мост: инженерному AF она даёт стиль, киношному — biomech props и creature
parts, фэшн — wearable armor и органические аксессуары.

### P1 — Neutral Core & Mode Scaffolding ⬜

- Аудит языка ядра: терминология «artifact» в схемах/доках, нейтральные
  имена там, где инженерная семантика не обязательна.
- `mode:` как профиль поверх A3/A2: дефолтные requirements, состав пакета,
  weights гейтов; переключатель режима в Cockpit. Никакой новой геометрии —
  только приоритеты и словари.
- Критерий: один и тот же артефакт, прогнанный в Engineering и Cinema
  режимах, даёт разные requirements-дефолты и разные пакеты при идентичной
  геометрии и идентичных honesty-вердиктах.

### P2 — Body / Human Fit Layer v1 🔶 (ядро реализовано 2026-07-07)

Реализовано (первый wearable-артефакт AF): `forearm_cuff_v1` +
`catalog/examples/forearm_flashlight_cuff.yaml` — grade A, side_profile,
S/M/L из одного YAML сменой body_fit (закреплено тестом). Вошло:

- `body_fit:` блок на ProductInstance (`BodyFitSpec`, человеческие
  диапазоны, `env_context()` → body_* имена в resolve);
- микро-P1: `mode:` + реестр `MODE_PROFILES` (product/modes.py;
  wearable требует body_fit ПОВЕДЕНЧЕСКИ, mode/mode_tags в summary);
- honesty-фикс resolve: нерезолвящийся formula-default = именованный
  FAIL (это и есть require-механизм body_fit);
- роль `BODY_CONTACT_SURFACE` (абсолютная защита кожи во всех
  PROTECTED-наборах) + 7 измеряющих проверок (donning-горло, skin
  clearance, comfort edges, pad recesses, payload not-on-skin,
  snap-ретенция, strap access) + `topology.payload_void_open`;
- op `forearm_cuff_body` (хордовый рот + строп-табы + snap-C фонаря =
  первый клиент `cylindrical_cradle`), модификатор `add_strap_slots`
  (превью P3, 15–40мм стропы, skin-guard по кругу руки).

Остаток P2: другие регионы тела (wrist/thigh/…), size grading через
families (A4), био-скин на манжету (Bio-4M stage B канвас).

Тело как first-class вход — без сканера, параметрически:

```yaml
body_fit:
  region: forearm        # head | neck | shoulder | forearm | wrist | chest | waist | thigh | foot
  circumference: 270mm
  length: 240mm
  clearance: 6mm
  strap_width: 25mm
```

- Таблица антропометрических регионов с дефолтными диапазонами; size
  grading = параметрические families (механизм extends/preset из A4).
- Роль `body_contact_region` приходит вместе со своим потребителем:
  валидаторы skin_clearance (зазор к телу измерен), edge safety (контактные
  кромки скруглены — обобщение contact_r), вес (масса из объёма × материал).
- Драйвер-клиент: **держатель фонаря на предплечье** («биомеханический
  держатель на руку актёра») — body-cradle ядро + strap-интерфейсы (P3) +
  био-скин Bio-4M. Один артефакт закрывает cinema и wearable сразу.
- Критерий: golden-пример собирается под два разных `body_fit` (перчаточный
  размер S и L) без правки геометрии руками; clearance и края измерены.

### P3 — Soft–Hard Interfaces ⬜

Стык жёсткой печати с мягким миром — как interface-профили/порты (механизм
A1) и модификаторы (кернел уже умеет):

- `strap_slot` (обобщение zip_tie слотов на ремни 20/25/38 мм),
  `sew_hole_row` (пришивание к ткани), `velcro_patch_zone`,
  `elastic_band_anchor`, `foam_pad_recess` (родня TPU-рекессов клампа),
  `fabric_clamp`; для кино — `LED_channel` (родня cable_channel +
  диффузорное окно), `rigging_point` (провереная точка подвеса с
  load_rating), `hidden_mount`, `quick_release`/`quick_repair_joint`
  (быстрая замена сломанной части на площадке).
- Каждый интерфейс — типизированный, с валидатором (слот меряется, ряд
  отверстий не рвёт кромку, LED-канал непрерывен — реюз
  channel_continuous).
- Критерий: артефакт P2 получает ремни + пришивные точки; BOM (A2)
  автоматически включает ремень/липучку как hardware-позиции.

### P4 — Style Grammar + Mode Production Packages ⬜

- **Грамматика стилей**: реестр стиль-паков поверх SurfaceStyle/Bio-4M —
  `giger_exoskeleton` (движок уже есть: implicit SDF skin),
  `retro_sci_fi`, `alien_organic`, `brutalist_utility`, `ritual_object`,
  `soft_biomorphic`, … Закон неизменен: стиль применяется только через
  regions/keepouts и НЕ имеет права ломать функцию (канон BIOMORPHIC.md);
  каждый пак — слайдеры → контролируемые form/SDF-проходы, не «сделай
  красиво».
- **Пакеты по режимам** (расширение A2): cinema — split для покраски,
  места под магниты, LED-разводка, схема сборки, варианты
  hero/stunt/background одного артефакта (разный вес/детализация/материал
  из одного YAML); fashion — размеры, вес, схема пришивания/ремней,
  контактные зоны, рекомендации материала, отчёт безопасности краёв.
- Критерий: один артефакт выдаёт hero (implicit skin, высокая детализация)
  и stunt (лёгкий, TPU, упрощённый) варианты одной командой; отчёты честно
  различают, что проверено в каждом.

---

## Линия PK — Pack Economy (канон: [ECOSYSTEM.md](ECOSYSTEM.md))

Все волны ⬜ (декларация; реализация отдельными итерациями):

- **PK-1 Pack Mechanism v1** ⬜ — `packs/` третий источник loader-а,
  `pack.yaml`, origin=`pack:<id>`, license/author-метаданные + notices в
  отчётах, выделение VF в `packs/grow/`; желательно после/вместе с A2.
- **PK-2 Free Starters + Certified Criteria** ⬜ — Utility/Workshop/
  Wearable Starter, Bioform Demo; критерии Certified; repo boundaries.
- **PK-3 Commercial Layer** ⬜ — personal/commercial маркировка, notices
  в build package; no DRM in core (entitlement только в cloud).
- **PK-4 Web Studio** ⬜ — платный конфигуратор поверх core API;
  Cockpit остаётся open local debugger.

---

## Поглощённые дорожки

| Прежний план | Куда встроен |
|---|---|
| `dovetail_joint` / `tongue_groove` (остаток R4) | **A1** — драйвер-клиент портов |
| `rail_slider` (остаток R5) | **A4** — рельс Workshop Wall System |
| «R3 split_plane → R4 snap/dovetail → R5 assembly-intents» (README) | split_plane ✅ (butt_pin), snap ✅; dovetail → **A1**, assembly-intents → **M1** |
| `pin_hinge`, `friction_hinge`, `living_hinge`, threads, `ratchet_teeth` | **E-этап**, по итерации на штуку со своей физикой |
| Bio-4A (extends/preset/family) | механизм строится в **A4** |
| Bio-4B пресеты, Bio-5 curved, Bio-6 motifs & assemblies | параллельная линия; multi-part био-сборки — после **A1** (порты) |
| Bio-4M implicit SDF skin (BIOMORPHIC.md) | движок стиль-паков giger/creature в **P4**; stage B (кламп-интеграция) остаётся в Bio-линии |
| `space_colonization_branching` | после Bio-5, вне критического пути |
| Фаза 4 «LLM frontend» (README) | requirements-переводчик в **A3**, functional plan в **M1**; LLM никогда не мозг геометрии |
| add_zip_tie_slots, TPU-рекессы, магнитные карманы | прародители soft–hard интерфейсов **P3** |

## Правила движения

1. Волна закрыта только при: golden-пример + тесты + `verified_by`-валидаторы
   на каждую заявленную фичу. Статус в таблицах меняется на ✅ только после
   этого.
2. Ничего не помечается сделанным без измеряемой проверки — canon honesty
   распространяется и на сам роудмап.
3. Порядок волн можно менять по обстоятельствам мастерской; критерии приёмки
   волны — нет (их можно только честно пересматривать отдельным коммитом).
4. Документ обновляется в конце каждой волны; устаревшие дорожки не
   стираются, а переносятся в «Поглощённые дорожки».
5. Ядро одно на все аудитории: режим меняет приоритеты, словари и состав
   пакетов — никогда не ослабляет проверки и не форкает геометрию.
6. Новые region-роли и сущности режимов — строго по закону «роль приходит
   со своим потребителем»: сущность появляется вместе с валидатором,
   который её измеряет, иначе это словарная галлюцинация.
