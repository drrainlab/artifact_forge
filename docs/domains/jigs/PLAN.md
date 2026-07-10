# Manufacturing Aids / Jigs / Fixtures — план домена

Статусы: ✅ реализовано · 🔶 частично · ⬜ не начато. Канон шаблона —
[INDEX.md](../INDEX.md); коммерческие правила — [ECOSYSTEM.md](../../ECOSYSTEM.md).

## 1. Scope и позиционирование

Производственная оснастка малых серий: сверлильные кондукторы, упоры,
сборочные и паяльные fixtures, калибры-лесенки, go/no-go шаблоны,
alignment-блоки. Контекст: AM как production resource — компаниям важны
repeatability, отчёты, labels, BOM, материал и версия; ровно то, что AF
делает валидаторами. Сильнейшее B2B-направление: оснастка нужна каждой
мастерской, каждая — чуть другая, параметризация окупается мгновенно.

Каких claims домен НЕ делает:

- Джиг — оснастка, НЕ мерительный инструмент класса точности: без
  калибровки на месте никакой «гарантированной точности ±0.05».
- НЕ обещает ресурс под ударные/фрезерные нагрузки — позиционирование
  и направление, не восприятие сил резания.
- Go/no-go калибры — цеховые пробники, не поверенные средства
  измерения.

## 2. Mode / Environment / Tier

Домен = pack, НЕ новый mode: контракт качества собирается из
Engineering (допуски, min_wall, frames) и Workshop (нагрузки, крепёж).

```text
mode:        Engineering / Workshop
environment: workshop / desk
tier:        Business / Pro-центричный (Free — одиночные упоры-витрина)
```

## 3. Что уже есть в движке — карта реюза

| Блок домена | Чем собирается сегодня | Статус |
|---|---|---|
| Базовые плиты оснастки | `adapter_plate_v1`, `fastener_plate_v1`, `rounded_plate` | ✅ |
| Отверстия/зенковки под крепёж заготовки | hole/counterbore/countersunk-паттерны | ✅ |
| Гайки/вставки в тело джига | `nut_trap`, `heatset_insert_pocket` | ✅ |
| Направляющие втулки кондуктора | `bearing_seat` (посадка стальной втулки/подшипника 608/625) | ✅ |
| Позиционные упоры, сменные губки | dovetail: `dovetail_adapter_body`, `dovetail_joint`, порт `dovetail_rail` | ✅ |
| Registration двух половин fixture | `pin_pair`, joint `butt_pin` (split+registration), `press_fit_pin_pair` | ✅ |
| Облегчение крупной оснастки | `truss_web_cutouts`, `truss_beam_v1` | ✅ |
| Крепёжные интерфейсы | порты `screw_pattern`/`heatset_insert_pattern` + `dovetail_rail` (A1/A1.5) | ✅ |
| Комплектность/отчёт | BOM (`assembly/bom.py`), frame_report, swap-харнес (сменные губки!) | ✅ |
| Маркировка (версия/номер джига) | text/label embossing op | ⬜ |
| Дюймовая параметризация UX | units-resolve есть; дюймовые пресеты | 🔶 (YAML-конвенция, не движок) |
| DIN/euro-палетная сетка оснастки | единый шаг системы | ⬜ (родня A4 Wall System) |

## 4. Волны JF-1..3

### JF-1 — Positioning Core ⬜

Golden-артефакты (оба обязательны):

- **`drilling_jig_v1`** — кондуктор: плита (`rounded_plate` +
  hole-паттерн) с посадками под стальные направляющие втулки
  (`bearing_seat` press-fit band) и боковым упором-линейкой; крепление
  заготовки струбциной (плита даёт clamp-кромку).
- **`stop_block_v1`** — параметрический упор (дюймовые и метрические
  пресеты из одного YAML) с dovetail-фиксацией на рельсе
  (`dovetail_adapter_body` + `dovetail_joint`): повторяемая длина
  отреза/сверловки.

Критерий: оба golden в grade A; посадка втулки и dovetail-фиксация
закрыты измеряющими валидаторами (§6); swap-тест «упор переставлен —
рельс не тронут» через существующий swap-харнес.

### JF-2 — Assembly / Soldering Fixtures + Gauge Family ⬜

- Сборочные/паяльные fixtures: плита + `standoff_pattern` под PCB/деталь
  + `pin_pair` registration двух половин + `nut_trap` для прижимов;
  окна доступа паяльника — `rounded_rect_cutout`.
- **Gauge family**: лесенки допусков (ступенчатые щупы зазоров),
  go/no-go пробники отверстий/валов — параметрические families
  (механизм A4 extends/preset). Родня fit-templates домена repair
  (RP-2) — общий валидатор лесенки.
- Критерий: golden soldering_fixture + gauge_ladder; монотонность и
  шаг ступеней — валидатором, не декларацией.

### JF-3 — Versioning, Labels, B2B Report Bundle ⬜

- Маркировка джига: номер, версия, дата — требует **text embossing op
  ⬜** (главный gap домена); до него — параметрические насечки-риски.
- **B2B report bundle**: BOM (втулки, винты, вставки — из joints/ops,
  не декларация) + материал + версия + print notes одним пакетом —
  прямой клиент A2 Build Package ⬜.
- Критерий: `drilling_jig_v1` выдаёт пакет; тест сверяет крепёж BOM с
  joints (рассинхрон непредставим — канон A2).

## 5. Интерфейсы и стандарты домена

**Fixture Interface Standard** (по образцу Cassette Interface Standard):

1. **Shared-параметры** (контракт имён): `datum_edge_offset`,
   `bushing_od`, `bushing_press_band` (0.05–0.15), `stop_travel`,
   `grid_pitch` (шаг сетки крепления оснастки), `jig_version`.
2. **Frame-ключи**: `datum_face_z`, `bushing_axis_*`, `stop_face_x`,
   `rail_u0/u1` — registration-поверхности публикуются билдером и
   меряются в позе.
3. **Typed ports**: фиксация упоров — существующий `dovetail_rail`
   (male/female, slide-ось в frame); крепление плит — `screw_pattern`;
   registration половин — joint `butt_pin`. Новых типов JF-1 не вводит
   — весь словарь A1 уже покрывает домен.

## 6. Валидаторы-кандидаты

| Валидатор | Что меряет |
|---|---|
| `form.bushing_fit_ok` | press-fit band посадки втулки, глубина ≥ k·bushing_od, стенка вокруг ≥ min_wall |
| `form.registration_surfaces_ok` | datum-грани компланарны/ортогональны в допуске, pin-registration без люфта сверх band |
| `form.gauge_tolerance_ok` | ступени калибра монотонны, шаг постоянен, кромки ступеней не тоньше сопла |
| `form.stop_repeatability_ok` | dovetail-упор: зацепление полное, люфт вдоль рабочей оси в band |
| `manufacturing.jig_orientation_declared` | рабочие поверхности не поперёк слоёв; ориентация в отчёте |
| `assembly.fixture_bom_complete` | каждая покупная позиция (втулка/винт/вставка) выведена из joint/op (клиент A2) |

## 7. Free / Pro граница (Printables-тест)

| Free / Certified Free | Business / Pro |
|---|---|
| одиночный stop_block, простой кондуктор под один диаметр | families оснастки (сетки, серии диаметров, дюйм/метрика) |
| один gauge-пробник | gauge families + fit-workflow допусков |
| — | B2B bundle: BOM + материал + версия + print notes; приватные packs |

Ценность B2B — repeatability, отчёты и версия, не сам STL упора.

## 8. Риски и claims

- **Точность**: пластиковый джиг ведёт сверло, но не заменяет станочную
  оснастку; каждый отчёт несёт ноту «verify first article».
- **Износ**: направляющая функция — у стальной втулки; сверление прямо
  по пластику — WARN, не поддерживаемый режим.
- **Термика**: паяльные fixtures — нота материала (PETG минимум, ASA
  лучше); PLA у жала — FAIL-кандидат после environment-носителя ⬜.
- **Калибры**: усадка материала смещает ступени — go/no-go честен
  только после печатной калибровки (нота в отчёте, RP/JF-общая).

## 9. Связи

- **A1/A1.5 ✅**: dovetail-порты — механизм сменных губок/упоров;
  swap-харнес — готовое доказательство перестановки оснастки.
- **A2 BOM ⬜**: JF-3 report bundle — один из первых клиентов Build
  Package (наравне с esp32_box из критерия A2).
- **A4 Wall System ⬜**: единый шаг/рельс системы — родня grid_pitch;
  gauge/appliance families ждут extends/preset.
- **E-этап**: E2 load paths усилит claims прижимов; threads ⬜ — винтовые
  прижимы джигов.
- **Домены**: repair (общий валидатор лесенок RP-2/JF-2), electronics
  (soldering fixtures под их же платы — общие standoff-паттерны).

Общие capability-gaps этого домена (лесенки посадок, environment/material
гейты, contact-safety словарь, text embossing, threads/hinge/slide, grid-
стандарт) централизованы в [CAPABILITIES.md](../CAPABILITIES.md) — домен их
КЛИЕНТ, не владелец.
