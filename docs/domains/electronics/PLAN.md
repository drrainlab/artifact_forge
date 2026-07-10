# Electronics / IoT / Smart Home — план домена

Статусы: ✅ реализовано · 🔶 частично · ⬜ не начато. Канон шаблона —
[INDEX.md](../INDEX.md); коммерческие правила — [ECOSYSTEM.md](../../ECOSYSTEM.md).

## 1. Scope и позиционирование

Корпуса и обвязка DIY/IoT-электроники: боксы ESP32/Arduino/Raspberry Pi,
sensor mounts, кабельные вводы, DIN-rail и 2020-крепления, вентиляция,
wall boxes. Самый «готовый» домен движка: enclosure-архетипы (screw И
snap), port_cutout с PORT_SIZES, standoffs, wire_exit и весь
cable-management уже существуют — EL-1 почти чистый YAML поверх ops.

Каких claims домен НЕ делает:

- НЕ заявляет IP-рейтинги (IP54/IP65…) без физического теста — до
  seal-контракта ⬜ слово «waterproof» в отчётах непредставимо.
- НЕ сертифицирует mains-voltage корпуса: PETG/ABS не UL94-V0 by
  default; сеть 230В — предупреждение об изоляции/огнестойкости, не
  поддерживаемый сценарий.
- НЕ обещает EMI-экранирование и термодизайн (вентиляция меряется
  геометрией, не CFD).

## 2. Mode / Environment / Tier

Домен = pack, НЕ новый mode: контракт корпуса целиком закрывается
Engineering (стенки, порты, крепёж, frames) + Utility.

```text
mode:        Engineering / Utility
environment: indoor / outdoor / wet / high-heat
tier:        Free (одиночные корпуса) + Pro (families)
```

## 3. Что уже есть в движке — карта реюза

| Блок домена | Чем собирается сегодня | Статус |
|---|---|---|
| Корпус винтовой | `enclosure_base_v1` + `enclosure_lid_v1` (joint screw + lid_seat) | ✅ |
| Корпус на защёлках | `enclosure_base_snap_v1` + `enclosure_lid_snap_v1` (snap strain-физика) | ✅ |
| Вырезы разъёмов | `port_cutout` + PORT_SIZES (usb_c/audio/…) | ✅ |
| PCB-стойки | `standoff_pattern`, `boss_pattern`, `heatset_insert_pocket`, `nut_trap` | ✅ |
| Кабельные выходы | `wire_exit`, `cord_slot_pair` | ✅ |
| Вентиляция | hex/grid поля-модификаторы | ✅ |
| Кабельная обвязка вокруг узла | `cable_junction_box_v1`, `cable_raceway_v1`, `cable_grommet_plate_v1`, `cable_comb_v1`, `underdesk_cable_clip_v2/v3` | ✅ |
| Анкеровка/стяжки | `zip_tie_anchor_v1`, порт `strap_slot_pair` | ✅ |
| Крепление на 2020-профиль | `aluminum_profile_ref_v1`, `profile_seat_slot`, `endcap_dock_pockets` | ✅ |
| Кабельные порты сборки | тип `cable_pass` (реестр A1; инстансов нет) | 🔶 |
| DIN-rail clip | op пружинной защёлки TS35 | ⬜ |
| Cable gland (резьбовой ввод) | threads | ⬜ (R5-остаток, E-этап) |
| Seal-контракт (прокладка/лабиринт) | канавка + валидатор непрерывности | ⬜ |
| Маркировка корпуса | text/label embossing op | ⬜ |
| Environment-профиль на instance (outdoor gate) | носитель environment | ⬜ (линия PK) |

## 4. Волны EL-1..3

### EL-1 — Board Families + Sensor Mounts ⬜

Board-пресеты ESP32 / RPi Zero / RPi 4 / Arduino Nano/Uno на
СУЩЕСТВУЮЩИХ ops: таблица «плата → standoff-паттерн + port-вырезы» —
почти чистый YAML. Sensor mounts (BME280/PIR/камера) — малые плиты с
hole-паттернами + `zip_tie_anchor`/strap.

Golden-артефакт: **`esp32_sensor_node_box`** — `enclosure_base_snap_v1`
+ `standoff_pattern` под ESP32 + `port_cutout` usb_c + hex-vent поле +
`wire_exit` под шлейф сенсора; крышка `enclosure_lid_snap_v1`.

Критерий: golden в grade A; standoff-паттерн и вентиляция закрыты
валидаторами (§6); смена платы пресетом (esp32 → nano) не трогает
YAML-структуру — только board-ключ (закрепить тестом).

### EL-2 — Mounting: DIN / 2020 / Gland ⬜

- **DIN-rail clip op ⬜** — главный новый op домена: пружинная защёлка
  TS35 (родня snap-физики strain); приходит строго со своим
  валидатором ретенции.
- **2020-крепления** — реюз `profile_seat_slot`/`aluminum_profile_ref_v1`
  + dovetail/screw-порты: бокс на профиль без нового железа.
- **Cable gland** — зависимость threads ⬜ (E-этап); до них честный
  суррогат: `wire_exit` + зажим стяжкой (`zip_tie_anchor`) как
  strain relief, без слова «gland» в отчёте.
- Критерий: golden din_mounted_box (тот же esp32-бокс, сменённый
  mounting-пресет) + 2020-вариант; ретенция клипа измерена.

### EL-3 — Outdoor / Wet ⬜

- **Seal-контракт ⬜**: канавка под шнур/TPU-прокладку по периметру
  lid_seat + валидатор непрерывности контура (связь VF water
  discipline: «скрытых мокрых полостей нет», leak-path контролируем).
- Drip loops / нижние вводы: правило «вода не затекает по кабелю» —
  геометрический чек ориентации wire_exit вниз.
- До физического теста лучший честный вердикт — «rain-shielded,
  not rated»; IP-claims остаются вне scope (§1, §8).
- Критерий: golden outdoor_sensor_box с seal-канавкой; непрерывность
  контура и направление вводов — валидаторами.

## 5. Интерфейсы и стандарты домена

**Board Mount Standard** (по образцу Cassette Interface Standard):

1. **Shared-параметры** (контракт имён): `board_l`, `board_w`,
   `hole_pattern` (список xy), `standoff_h`, `port_side`,
   `port_offsets`, `vent_ratio`, `mount_kind` (din|2020|wall|strap).
2. **Frame-ключи**: `pcb_floor_z`, `standoff_top_z`, `port_face_*`,
   `lid_seat_z`, `vent_zone_uv` — публикуются билдером, меряются
   в позе (разъём обязан попасть в вырез — mate-проба, не вера).
3. **Typed ports**: крышка↔база — существующие `screw_pattern`/
   `snap_joint` (+ lid_seat joint); кабель сквозь стенки сборки —
   `cable_pass` (тип есть в реестре A1, первые инстансы — этот домен);
   крепление на профиль — `dovetail_rail`/`screw_pattern`. Новый
   тип-кандидат `din_rail_clip` — вводится в EL-2 вместе со своим
   mate/ретенция-валидатором ⬜.

## 6. Валидаторы-кандидаты

| Валидатор | Что меряет |
|---|---|
| `form.board_standoff_pattern_ok` | паттерн стоек совпадает с hole_pattern платы в band, стойки не под keepout-зонами разъёмов |
| `form.vent_area_ratio_ok` | суммарная площадь vent-поля ≥ vent_ratio площади стенки; перемычки ≥ min_wall |
| `form.port_cutout_reachable` | вырез соосен разъёму на standoff_h (frame-проба), фаска ввода кабеля |
| `form.din_clip_retention_ok` (буд., EL-2) | strain защёлки TS35 в band, ход отжатия отвёрткой обеспечен |
| `form.seal_groove_continuous` (буд., EL-3) | канавка прокладки — замкнутый контур постоянного сечения |
| `manufacturing.gland_thread_printable` (буд., после threads) | резьба ввода печатаема выбранным соплом/ориентацией |

## 7. Free / Pro граница (Printables-тест)

| Free / Certified Free | Pro |
|---|---|
| одиночный корпус под конкретную плату (esp32_sensor_node_box) | families: платы × вводы × крепление (DIN/2020/стена/шина) |
| sensor mount, zip-анкер | outdoor-варианты с seal-контрактом и print notes |
| — | приватные board-профили (свои PCB) + пакет A2 (BOM: винты, вставки, прокладка) |

Корпус под ESP32 есть на Printables тысячами — Free by test; платна
матрица комбинаций с mate-пробами и отчётами.

## 8. Риски и claims

- **Mains voltage**: 230В-объёмы — жёсткое предупреждение (изоляция,
  огнестойкость: PETG/ABS не UL94-V0 by default); домен не
  сертифицирует электробезопасность.
- **IP-рейтинги**: не заявляются без теста; seal-канавка даёт
  «rain-shielded», не «IP65» (honesty-канон).
- **Термика**: vent_ratio — геометрическая мера, не тепловой расчёт;
  горячие платы (RPi 4 под нагрузкой) — нота о принудительном обдуве.
- **Дрейф размеров плат**: клоны Arduino/ESP32 гуляют по отверстиям —
  board-пресеты несут source-ноту и band, не точечное значение.
- **Зависимости волн честные**: gland без threads ⬜ не обещается;
  DIN-клип без валидатора ретенции не мержится.

## 9. Связи

- **A1/A1.5 ✅**: lid/snap/screw-порты и mate-frames уже несут корпус;
  `cable_pass` получает здесь первые инстансы; `din_rail_clip` —
  кандидат в реестр типов.
- **A2 BOM ⬜**: `esp32_box_with_lid` — уже именованный критерий волны
  A2; домен — её первый потребитель (винты/вставки/прокладка в BOM).
- **A4 families ⬜**: матрица «платы × крепления» ждёт extends/preset.
- **E-этап**: threads ⬜ (гланды), E2 материальные профили (термика).
- **Линия VF ✅**: water discipline и leak-path-мышление — образец для
  seal-контракта EL-3; 2020-крепёж — общий с profile-ops VF-4.
- **Домены**: jigs (soldering fixtures под те же board-пресеты),
  repair (корпусные защёлки/крышки — общие snap-ops).

Общие capability-gaps этого домена (лесенки посадок, environment/material
гейты, contact-safety словарь, text embossing, threads/hinge/slide, grid-
стандарт) централизованы в [CAPABILITIES.md](../CAPABILITIES.md) — домен их
КЛИЕНТ, не владелец.
