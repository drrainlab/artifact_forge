# Artifact Forge NG — YAML Product Grammar Engine

Deterministic-first генератор 3D-печатаемых изделий. Источник истины —
типизированная YAML Product Grammar (каталог архетипов + product instance),
не свободный LLM-spec. LLM (фаза 4, ещё не подключён) — только переводчик
намерения в YAML; мозг геометрии — каталог, Form IR и валидаторы.

## Pipeline

```
product.yaml
  → catalog load (fail-fast привязка всех имён)
  → parameter resolve (units, expr, clamps, declaration order)
  → capability report (requested / supported / built / missing)
  → Form IR (точные line/arc-профили, semantic regions — БЕЗ CadQuery)
  → form validators (golden gate: пока не зелёные, CAD не трогаем)
  → compile_part (CadQuery: экструзия профиля, weld, blends, holes, hex)
  → geometry validators (topology probes / regions / manufacturing)
  → contract + score (critical FAIL → grade F, score не маскирует)
  → honesty report + STL/STEP
```

## Команды

```bash
uv sync --extra cad                 # окружение (form-слой работает и без cad)
uv run forge validate catalog/examples/desk_cable_clip_20mm.yaml   # без CAD
uv run forge build    catalog/examples/desk_cable_clip_20mm.yaml -o out
uv run pytest                       # 140 тестов; tier-1 без cadquery
uv run pytest -m "not cad"          # только быстрые IR-тесты
```

## Ключевые гарантии

- **built ⊆ supported** на уровне pydantic-схемы: unsupported-фича физически
  не сериализуется как built; фича built ⟺ все её `verified_by`-валидаторы PASS.
- **Симметричное C-кольцо непредставимо случайно**: рот, губы и стенка — один
  замкнутый 2D-контур; клампы (`lower ≥ 1.6×upper`, `mouth_gap ≤ 0.7×bundle_d`)
  живут в YAML архетипа; топология-пробы меряют реальный солид.
- **strict mode**: unknown validator = ошибка загрузки; unsupported requested
  feature = fail; critical topology fail = exit ≠ 0; никаких fallback'ов.
- **Ремонт только YAML-патчами** (`+3mm` / absolute / expr) с ре-валидацией
  через те же схемы; правила детерминированные, выжившие находки → engine_gaps.

## Структура

```
src/artifact_forge_ng/
  core/        units, expr (sandboxed AST), грамматика значений, findings
  product/     pydantic-схемы (archetype/instance/modifier/contract), resolver, capability
  catalog/     loader + data/ (features.yaml, modifiers/, archetypes/)
  form/        Form IR: section (line/arc), profiles, molded, regions, fields,
               silhouette, validators — не импортирует cadquery (есть тест)
  archetypes/  Python form-билдеры (underdesk_cable_clip)
  cad/         Geometry-шов (порт v1), booleans (weld), fillets, holes, probes
  compiler/    wires → solids (compile_part) → pipeline (forge build)
  validators/  реестр проверок + topology/region/manufacturing пробы + runner
  review/      score (hard gate), quality v0, honesty report
  repair/      YAML-патчи + детерминированные правила + ledger
```

## Каталог (фаза 5)

| Архетип | Что это | Ключевые проверки |
|---|---|---|
| `underdesk_cable_clip_v2_molded` | флагман: асимметричная боковая клипса под стол | not_symmetric_c_ring, mouth/lips, screw_access |
| `adapter_plate_v1` | переходная пластина: 2 узора отверстий + борт | min_web, holes_within_outline |
| `cable_comb_v1` | гребёнка: полость+горло на каждый кабель | slots_open, throat_retention (горло < кабеля) |
| `zip_tie_anchor_v1` | площадка под стяжку (омега-туннель) | tunnel_fits_tie, tunnel_open |
| `wall_hook_v1` | J-крюк на саморезы (вешалка/ключи) | tip_lip_present, bay_open |
| `headphone_hook_v1` | широкий крюк для наушников (тот же билдер) | + wide_contact_band |
| `lamp_socket_cup_v1` | чашка патрона E27/GU10 (revolve) | revolve_axis_clear, cavity_open |
| `lamp_bracket_v1` | кронштейн лампы с каналом проводки | **channel_continuous по L-пути** |
| `phone_stand_v1` | подставка для телефона | slot=f(tilt) точно, **stability_footprint (COM)** |

Примеры: `catalog/examples/*.yaml` — все строятся `forge build` в pass/A.
Пара кронштейн+чашка стыкуется: датум `arm_tip` ↔ bolt-circle `mount_bc`.

## Модификаторы (Modifier Kernel v1)

Typed, region-bound трансформации над Form IR — модификатор не имеет права
ломать продуктовую топологию. Архетип владеет функцией, модификатор —
адаптацией. Каждый: читает целевой регион → выводит keepouts (защищённые
регионы + отверстия + **вырезы более ранних модификаторов**) → эмитит
IR-фичи → компилятор режет/приваривает ровно их → валидаторы подтверждают
→ только после PASS фича считается built.

| Модификатор | Тип | Гарантия |
|---|---|---|
| `add_hex_perforation` | field | web между ячейками ≥ wall_gap (меряется!) |
| `add_grid_slot_field` | field | слоты целиком вне keepouts |
| `add_voronoi_field` | field | **стабильный seed** (тот же YAML → тот же объект), Lloyd-релаксация, лигамент ≥ min_ligament |
| `add_magnet_pockets` | interface | глухие карманы, кожа за дном проверяется целой |
| `add_zip_tie_slots` | interface | пара сквозных слотов, fail если keepout мешает |
| `add_ribs` | structural (**аддитивный**) | рёбра приварены (weld-правило) и подтверждены пробой |

`cut_mode: through | recess` у всех полей. Функциональные подстройки
(mouth_gap и т.п.) — это YAML-патчи repair-слоя, НЕ модификаторы.

## Bio-organic SurfaceStyle

`style: {surface: biomorphic_utility_part, organicity, softness, asymmetry,
vein_rhythm, seed}` — НЕ «сделай органично», а компиляция слайдеров в
контролируемые form-проходы:
- **softness** масштабирует декоративные радиусы (contact_r — инженерный,
  не трогается);
- **organicity** выгибает длинные внешние грани профиля наружу (материал
  только добавляется, стенки не тоньшают); стыки дуга-дуга скругляются
  честными тангенциальными филлетами;
- **asymmetry** — детерминированный jitter прогибов (seed в YAML);
- **vein_rhythm** — вены-гребни поперёк спинки (архетип сам назначает
  грань), позиции читаются с УЖЕ выгнутой дуги профиля.

Неприкосновенно by construction: контактные поверхности, пазы/рты, плоское
печатное основание, крепёж, силуэтное семейство. Пример:
`phone_stand_bio.yaml` — та же инженерия (тригонометрия паза, COM-гейт),
органическая кожа.

## Product Cockpit (forge ui) — Dark Forge OS v2

`uv run forge ui` (extra `[web]`) поднимает локальную кабину — **визуальный
отладчик инженерной правды**, не «чат + 3D viewer». UI показывает цепочку
понял → может → построил → проверил → честно сообщил и никогда не выдумывает
состояние: каждая панель — view model из serialize.py поверх того же
пайплайна (паритет CLI ↔ Cockpit закреплён тестом). Сердце — CAD-free
`/api/validate` (живые слайдеры, wizard, patch-preview). Пять линз:
3D (STL + позы сборок из assembly_pose), **Section — точный SVG из
IR-сегментов** (для профильных изделий правда живёт тут, не в меше),
Region (цветные семантические регионы), Honesty (requested/supported/
built/verified), Manufacturing. Wizard 5 стадий (intent → contract →
capability → live-параметры → Form-превью → Forge); семантические правки —
patch-preview до какого-либо CAD. LLM (Anthropic) — строго переводчик
intent/patch; без ключа кабина честно показывает LLM: OFF и работает
детерминированно (keyword-intent + intents-кнопки). Ошибки — всегда
structured findings, не traceback.

## Verified Assemblies (assembly/v1)

Сборка — typed-объект, а не текстовое соглашение между деталями. `forge
validate|build` принимают `assembly/v1` теми же командами: root-деталь как
единственная система отсчёта, части inline (self-contained), `shared:`
инжектит стыковочные размеры ОДИН раз (рассинхрон mount_bc непредставим),
joints из fail-fast реестра. Проверки в два эшелона: joint-IR ДО CAD
(совпадение болт-кругов в позе, совместимость диаметров clear↔tap) и
fit-пробы в собранной позе после per-part билдов: `assembly.no_interference`
(объём пересечения), `assembly.screw_axes_clear` (каждый винт физически
пройдёт) и киллер-проверка `assembly.channel_continuous_across` — кабель
проходит через ВСЕ детали (по-сегментный worst-case, пробку не разбавить
длинным путём). Каждая деталь печатается в своей ориентации; `assembled.step`
— compound в позе (без fuse), `assembly_report.yaml` — позы/joints/grade.
Демо: `desk_lamp_e27.yaml` (кронштейн + чашка E27, 4×M4, сквозная
проводка) и `esp32_box_with_lid.yaml` — коробка с крышкой: `lid_seat`
(размерная цепочка плаг↔интерьер−2·clearance до CAD + посадка в позе),
`screw_joint` в бобышки и `press_fit_pin_pair` (пин ТОЛЩЕ гнезда на
interference; реальный overlap измеряется и обязан попасть в декларацию).
Дорожная карта: R3 split_plane → R4 snap/dovetail → R5 assembly-intents.

## Geometry Builders & Recipe (docs/BUILDERS.md)

Канонический реестр билдеров — [docs/BUILDERS.md](docs/BUILDERS.md):
`archetype = что делаем · builder = каким приёмом · modifier = как адаптируем`.
Контракт билдера: геометрия + semantic regions + frame-ключи + валидаторы —
все четыре, иначе это галлюцинация. Волна R1 реализована: `form: {type:
recipe, ops: [...]}` — архетип собирается из зарегистрированных ops прямо в
YAML, без нового Python. Ops биндятся fail-fast при загрузке каталога, и
каталог ОТКАЗЫВАЕТСЯ грузить рецепт, не подписанный на валидаторы своих ops.
YAML-only архетипы (ни строчки нового Python): `cable_grommet_plate_v1`
(грометка), `enclosure_base_v1` (корпус: шелл + бобышки + usb-порт +
вентиляция модификатором), `bearing_turntable_base_v1` (посадка 608 с
проверяемой губой + филлотаксис-спираль). Плюс новые Python-билдеры волн:
snap C-clip с балкой в профиле (`broom_clip_25mm`, support-free) и
лофт-кронштейн с косынками (`shelf_bracket_150`, конус by construction).

## Semantic Edit (forge edit)

Правка = **rebuild from semantic source**, не хирургия меша:

```bash
uv run forge edit catalog/examples/desk_cable_clip_20mm.yaml \
    --intent make_support_free -o out
```

Патчи типизированы (functional / manufacturing / structural / style) и несут
**preserve-контракт**: перечисленные параметры обязаны выйти из пересборки
численно идентичными, а фичи — validator-built. Нарушение = провал правки
(проверяется, а не обещается). Intents v1: `make_support_free`, `make_biomorphic`, `remove_perforation`,
`make_stronger`. Выход: самодостаточный отредактированный YAML + STL +
`edit_report.yaml` (preserved / changed / printability before-after).

Патч умеет **миграцию между архетипами** одного object_class:
`make_support_free` на клипсе переводит её на
`underdesk_cable_clip_v3_sideprint` — вариант, где крепёжный фланец лежит
ВНУТРИ экструдируемого профиля (язык назад за крюк, саморезы вдоль языка).
Деталь становится константной экструзией, а `print_orientation:
side_profile` запекает в STL ориентацию «профилем на стол, ось экструзии
вверх» — у такой печати ноль нависаний **by construction** (каждый слой —
одна и та же фигура), что проверяется `form.constant_section` и честным
`manufacturing.overhang`. Тот же валидатор честен и про v2 фланцем вниз:
мостящийся круглый потолок полости И консольные губы (урок реальной
слайсер-сессии). Trade-off тоже в отчёте: изгиб губ идёт поперёк слоёв —
3+ периметра. Teardrop-полость (`cavity_roof: teardrop`) остаётся ручным
патчем для тех, кто хочет печатать фланцем вниз.
