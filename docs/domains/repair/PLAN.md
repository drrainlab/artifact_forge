# Repair / Spare Parts / Right-to-Repair — план домена

Статусы: ✅ реализовано · 🔶 частично · ⬜ не начато. Канон шаблона —
[INDEX.md](../INDEX.md); коммерческие правила — [ECOSYSTEM.md](../../ECOSYSTEM.md).

## 1. Scope и позиционирование

Печатаемые заменители изношенных/сломанных деталей бытовой техники и
хозяйства: ручки, ножки, втулки, шайбы, адаптеры шлангов, защёлки,
крышки, направляющие. Контекст: EU right-to-repair закрепляет право
требовать ремонт; прецедент Philips Fixables (replacement parts через
Printables с акцентом на материал, ориентацию печати и safety) — модель,
которую AF воспроизводит параметрически: не «STL похожей ручки», а
generic spare, выведенный из замеров узла и проверенный валидаторами.

Каких claims домен НЕ делает:

- НЕ обещает OEM-эквивалентность прочности/ресурса — replacement по
  замерам, не сертифицированная запчасть.
- НЕ заявляет пищевой контакт (детали кухонной техники — отдельная
  оговорка про материал/покрытие, вне гарантий домена).
- НЕ покрывает детали под давлением, нагревом выше материала, несущие
  safety-функцию (тормоза, замки детских кресел и т.п.).

## 2. Mode / Environment / Tier

Домен = pack, НЕ новый mode (правило пяти осей: нет уникального
валидаторного контракта — хватает существующих).

```text
mode:        Engineering / Utility / Workshop (по изделию)
environment: household / appliance / high-heat / wet
tier:        Free + Certified + B2B/OEM
```

## 3. Что уже есть в движке — карта реюза

| Блок домена | Чем собирается сегодня | Статус |
|---|---|---|
| Ручки-грибки, ножки, втулки, шайбы | `revolve_band`, `recipe_revolve` | ✅ |
| Пластины/накладки/крышечки | `rounded_plate`, `rounded_rect_cutout`, hole/counterbore/countersunk-паттерны | ✅ |
| Бобышки, стойки под винт | `boss_pattern`, `standoff_pattern`, `nut_trap`, `heatset_insert_pocket` | ✅ |
| Защёлки корпусов | `snap_hook_pair`, `snap_window_pair` (snap-физика strain) | ✅ |
| Корпусные фрагменты | enclosure-ops (`rounded_box_shell` + база `enclosure_base_v1`/`_snap_v1`) | ✅ |
| Крепёжные таблицы | fasteners M2–M5, heatset, гайки (`core/fasteners.py`) | ✅ |
| Крепёжные интерфейсы | порты `screw_pattern`, `heatset_insert_pattern` (A1/A1.5, frame + mate) | ✅ |
| Хомутовые/трубные заменители | `clamp_half_lower/upper`, `pipe_clip_v1_sideprint`, `axial_channel` | ✅ |
| Резьбовые заменители (крышки банок, гланды) | threads | ⬜ (R5-остаток, E-этап) |
| Маркировка детали (артикул/версия) | text/label embossing op | ⬜ |
| Петли (крышки приборов) | pin_hinge / living_hinge | ⬜ (E-этап) |
| Environment-профиль на instance (high-heat gate) | носитель environment | ⬜ (линия PK) |

## 4. Волны RP-1..3

### RP-1 — Measurement-Driven Generic Spares ⬜

Ядро домена: деталь выводится из замеров штангенциркулем, не из фото.
Golden-артефакты (оба обязательны для закрытия волны):

- **`hose_adapter_v1`** — параметрический двухступенчатый конус
  Ø-in/Ø-out с hose-barb рёбрами (`recipe_revolve` + `revolve_band`
  для рёбер): сливные шланги, пылесосы, садовый полив.
- **`replacement_knob_v1`** — ручка с посадкой на D-вал/квадрат
  (`recipe_revolve` тело + профильная выемка вала): плиты, стиральные
  машины, таймеры.

Плюс дешёвые side-goldens на готовых ops: appliance_foot (ножка с
резьбовой/гладкой втулкой — без threads пока press-fit), washer/spacer.
Критерий: оба golden в grade A, каждый параметр посадки закрыт
измеряющим валидатором (см. §6), S/M-варианты из одного YAML.

### RP-2 — Fit Templates + Appliance Families ⬜

- **Fit-templates**: печатаемые примерочные «лесенки» под замер узла —
  ступенчатые пробники диаметров вала/отверстия/паза (шаг 0.2 мм),
  пользователь примеряет, вводит номер ступени, получает деталь с
  гарантированной посадкой. Строится на `recipe_revolve` +
  hole-паттернах; это workflow, а не изделие — сердце Pro.
- **Appliance families**: family/extends/preset (механизм A4) —
  «ножки холодильников», «ручки духовок» как параметрические серии
  с maturity на пресетах.
- Критерий: golden fit_ladder + один family с ≥3 пресетами; тест
  «ступень N лесенки → деталь садится в band» закреплён валидатором.

### RP-3 — OEM / B2B профили ⬜

Брендовые replacement-каталоги по модели Fixables: приватный pack
(механизм PK-1/PK-3) с материалом/ориентацией/notes от вендора,
print confirmation как условие Certified. Зависимости: PK-1 ⬜,
text embossing ⬜ (артикул на детали), A2 BOM ⬜ (комплектность).

## 5. Интерфейсы и стандарты домена

**Spare Fit Standard** (по образцу Cassette Interface Standard):

1. **Shared-параметры** (имена — контракт): `shaft_d`, `shaft_flat_h`
   (D-вал) / `shaft_sq` (квадрат), `fit_clearance` (band 0.1–0.4),
   `hose_d_in`, `hose_d_out`, `barb_count`, `grip_d`, `grip_h`.
2. **Frame-ключи**: `shaft_axis_z`, `bore_floor_z`, `barb_od_k`,
   `grip_top_z` — публикуются билдером, меряются валидаторами.
3. **Typed ports**: посадка на вал — существующий тип
   `cylindrical_payload_socket` (female, axis = ось вала); крепёж
   накладок — `screw_pattern`/`heatset_insert_pattern`. Новый тип
   `shaft_socket` (D/квадрат-профиль) — кандидат в реестр A1,
   вводится только вместе со своим mate-валидатором ⬜.

## 6. Валидаторы-кандидаты

| Валидатор | Что меряет |
|---|---|
| `form.shaft_fit_ok` | зазор D-вал/квадрат в band (диаметр + лыска/грань), глубина посадки ≥ k·shaft_d |
| `form.knob_torque_wall_ok` | стенка вокруг вала держит момент руки (толщина от shaft_d, min_wall-обобщение) |
| `form.barb_retention_ok` | высота/шаг barb-рёбер vs hose_d (ретенция), угол наклона рёбер печатаем |
| `form.fit_template_ladder_ok` | ступени лесенки монотонны, шаг постоянен, маркировка ступени читаема (пока геометрией — насечки; текст ⬜) |
| `manufacturing.spare_orientation_declared` | print_orientation задан и согласован с нагрузкой посадки (слои НЕ поперёк вала) |

## 7. Free / Pro граница (Printables-тест)

| Free / Certified Free | Pro / B2B |
|---|---|
| одиночные ножки, шайбы, ручки, hose-адаптеры по введённым Ø | appliance families (серии пресетов с maturity) |
| один fit-ladder пробник | fit-workflow целиком (лесенка → номер ступени → деталь в band) |
| — | OEM/брендовые каталоги, print notes, отчёты, B2B-профили |

Одиночную ручку легко найти на Printables — она Free by test; ценность
AF — параметрическая посадка и workflow, они и платные.

## 8. Риски и claims

- **Прочность**: печатная деталь ≠ литая OEM; каждый отчёт несёт ноту
  о материале/ориентации; несущие/нагреваемые узлы — вне scope.
- **High-heat**: до появления environment-носителя ⬜ high-heat детали
  (ручки духовок) идут с WARN-нотой материала (PETG/ASA), не гейтом.
- **Пищевой контакт**: явная оговорка «not food-safe by default» во
  всех отчётах кухонных деталей.
- **Юридика OEM**: RP-3 только по соглашению с вендором; реверс чужих
  брендовых деталей в публичный каталог не входит.
- **Соблазн фото-реверса**: домен принципиально measurement-driven;
  «сгенерируй по фото» = галлюцинация без замеров.

## 9. Связи

- **A1/A1.5 ✅**: посадки как typed ports (`cylindrical_payload_socket`,
  screw/heatset); `shaft_socket` — кандидат в реестр.
- **A2 BOM ⬜**: комплект «деталь + винты + вставки» для RP-3.
- **A4 families ⬜**: appliance families в RP-2 ждут механизм
  extends/preset.
- **E-этап**: threads ⬜ (крышки/гланды), hinge ⬜ (крышки приборов) —
  расширяют RP-каталог, не блокируют RP-1.
- **Линия PK ⬜**: RP-3 требует pack-механизм и commercial layer.
- **Соседние домены**: jigs (fit-лесенки = родня gauge family JF-2),
  electronics (корпусные защёлки/крышки — общие ops).

Общие capability-gaps этого домена (лесенки посадок, environment/material
гейты, contact-safety словарь, text embossing, threads/hinge/slide, grid-
стандарт) централизованы в [CAPABILITIES.md](../CAPABILITIES.md) — домен их
КЛИЕНТ, не владелец.
