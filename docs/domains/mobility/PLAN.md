# Mobility / Bike / Vehicle — доменный план (MB)

Развёртка домена из [ECOSYSTEM.md](../../ECOSYSTEM.md) («Future Domains
to Watch → Mobility / Bike / Vehicle Accessories»). Канон шаблона —
[INDEX.md](../INDEX.md).

## 1. Scope и позиционирование

Аксессуары для велосипеда, салона авто и van/camper-пространств:
крепления света и камер на руль, клипсы и органайзеры салона,
cargo-организация на 2020-профилях. Ценность AF против STL-каталогов:
диаметр руля — ПАРАМЕТР (22.2 / 25.4 / 31.8 мм — один YAML), payload —
съёмный dovetail-адаптер, environment-гейты — валидаторы, а не мелкий
шрифт в описании.

**Каких claims домен НЕ делает:**

- НЕ airbag zone, НЕ pedal zone, НЕ зона обзора водителя;
- НЕ road-safety-critical part (тормоза, рулевые тяги, детские кресла);
- никаких crash-rated / vibration-rated заявлений без измеряющих проб;
- PLA для high-heat салона запрещается гейтом, а не «не рекомендуется».

## 2. Mode / Environment / Tier

Домен = pack, НЕ новый mode (правило пяти осей). Auto/Vehicle — это
**environment profile**, не режим: так решено в ECOSYSTEM («base mode +
warnings; отдельный Mobility-mode ТОЛЬКО когда появятся соответствующие
валидаторы»).

```text
mode:        Engineering / Utility / Workshop
environment: vehicle / outdoor / high-heat / vibration / UV
tier:        Free + Certified Free; Pro — families и системы
```

## 3. Что уже есть в движке — карта реюза

Компас домена: **bike light mount почти собран из готового** — руль это
труба, а вся манжетно-адаптерная механика A1 уже golden на предплечье.

| Building block | Статус | Реюз в домене |
|---|---|---|
| `pipe_clip_v1_sideprint` (snap_c арк-ретенция) | ✅ | руль = труба Ø22.2–31.8; та же арк-физика, тот же sideprint «ноль нависаний» |
| A1 свап-механика: `forearm_cuff_socket_v1` + `flashlight_adapter_25_v1` ↔ `rail_plate_adapter_v1`, харнес `assembly/swap.py` | ✅ | фонарь ↔ action-cam plate на руле — ТОТ ЖЕ dovetail_rail сокет и тот же харнес, тело крепления не меняется ни байтом |
| Интерфейсы `dovetail_rail`, `snap_joint`, `strap_slot_pair`, `screw_pattern` (frame normal/up, mate-валидация, `forge compat`) | ✅ | typed-порты домена готовы, матрица совместимости выводится |
| `wall_ring_mount`, `clamp_half_lower/upper` (TPU-ланды) | ✅ | хомутовые крепления на трубы рамы / стойки кемпера |
| `add_strap_slots` (15–40мм), `add_zip_tie_slots`, `cord_slot_pair` | ✅ | ремни/стяжки — штатное velo-крепление |
| `aluminum_profile_ref_v1` (2020) + `profile_seat_slot`, `endcap_dock_pockets` | ✅ | van/camper cargo-системы на стандартном профиле |
| `edge_magnet_pockets`, `nut_trap`, `heatset_insert_pocket` | ✅ | съёмные крышки органайзеров, металлический крепёж |
| `form.stability_footprint` (COM), snap strain-физика | ✅ | база для retention-проверок |
| Environment-profile носитель на instance | ⬜ | БЛОКЕР MB-2: материал-гейты по среде негде повесить |
| Vibration-валидаторы | ⬜ | честно: измеряющих проб нет — только WARN-hints |
| Text embossing op (маркировка «NOT FOR SAFETY USE») | ⬜ | желателен, не блокер |

## 4. Волны MB-1..3

### MB-1 — Handlebar Mount System ⬜

Golden-артефакт: **`bike_light_handlebar_mount`** — snap_c-клип на руль
(арк-ретенция `pipe_clip_v1_sideprint`, параметр bar_d) + `dovetail_rail`
сокет; свап фонарь ↔ action-cam plate ЧЕРЕЗ существующий swap-харнес
(`flashlight_adapter_25_v1` / `rail_plate_adapter_v1` реюзаются как есть
или с минимальным пресетом). Дополнительно: strap-вариант крепления
(`add_strap_slots`) для карбоновых рулей, где snap нежелателен.

Критерий: golden под bar_d 22.2 и 31.8 без правки геометрии руками;
`interface.swap_part_builds` + `form.handlebar_retention_ok` зелёные;
`forge compat` показывает mate руль-клип ↔ оба адаптера.

### MB-2 — Car Interior Clips ⬜

Клипсы кабеля/очков/парковочных карт, dashboard-safe держатели
(не в зоне обзора/airbag). **Зависимость: environment-носитель на
instance ⬜** — гейт «PLA не для салона» обязан стать измеряемым
`manufacturing.material_env_ok`, а не примечанием. До закрытия гейта
волна не стартует (фича без валидатора = галлюцинация).

### MB-3 — Cargo / Van / Camper ⬜

Органайзеры на 2020-профилях (реюз `aluminum_profile_ref_v1`,
`process: reference` из VF-4): крючки, лотки, страп-анкеры, разделители.
Family единого шага крепления — кандидат в механизм A4.

## 5. Интерфейсы и стандарты домена

**Handlebar Mount Standard** (по образцу Cassette Interface Standard):

- shared-параметры: `bar_d`, `clamp_w`, `strap_width`, `payload_offset`;
- frame-ключи: `bar_axis` (ось трубы), `payload_n` (нормаль сокета),
  `strap_tab_*`;
- typed ports: `dovetail_rail` (payload, female на клипе),
  `strap_slot_pair` (ремень), `snap_joint` (арк-захват руля);
  cassette-урок реюзается: `shared:` перезаписывает параметры свопнутой
  детали — рассинхрон адаптеров непредставим.

Payload-адаптеры домен НЕ плодит: любой существующий/будущий
dovetail-адаптер платформы (фонарь, плата, будущие) совместим по compat.

## 6. Валидаторы-кандидаты

| Валидатор | База | Статус |
|---|---|---|
| `form.handlebar_retention_ok` | реюз snap strain 1.5·δ·t/L² + арк-охват | ⬜ (сборка из готового) |
| `form.bar_diameter_in_range` | clearance-band интерфейса | ⬜ |
| `manufacturing.material_env_ok` | environment-носитель ⬜ — capability gap | ⬜ БЛОКЕР MB-2 |
| `assembly.payload_swap_verified` | прямой реюз `interface.swap_part_builds` | ✅ механика |
| `manufacturing.vibration_hints` | **WARN-уровень**: честно — без измерений это предупреждение (locknut/страховочная стяжка), не проверка | ⬜ |

## 7. Free / Pro граница (Printables-тест)

| Free / Certified | Pro |
|---|---|
| bike_light_handlebar_mount под один bar_d, простая cable clip салона, одиночный крюк на 2020 | family «весь диапазон рулей × payload-адаптеры» с compat-матрицей и отчётами |
| одиночные организаторы | van/camper cargo-СИСТЕМА (единый шаг, BOM, print notes) |
| — | commercial output / print-farm license |

Одиночный держатель фонаря есть на Printables — он Free. Платна
система: параметрический диапазон + верифицированный своп + отчёты.

## 8. Риски и claims

1. Среда агрессивная (UV, +70°C салон, вибрация) — до появления
   environment-гейтов домен обязан носить `vehicle-environment-warning`
   (Pack Trust Badge из ECOSYSTEM) на всех изделиях.
2. Vibration-hints не выдавать за проверки: WARN с текстом «не измерено».
3. Юридическая рамка в каждом PACK.md: accessory, not a safety device;
   зона установки — ответственность пользователя, но запретные зоны
   перечислены явно.
4. Отказ крепления = потеря фонаря/камеры, не авария — payload-класс
   изделий фиксируется в claims (никаких кронштейнов детских кресел).

## 9. Связи

- **A1/A1.5 ✅** — несущая механика домена (порты, dovetail, swap-харнес,
  frames); MB-1 — третий swap-драйвер после манжеты и VF-кассет.
- **A2 BOM ⬜** — ремни/винты/гайки MB-изделий в build package.
- **Environment-носитель ⬜** (линия PK, «технические носители») —
  блокер MB-2; MB — его первый настоящий клиент-заказчик.
- **Линия P** — strap-механика (P2/P3) общая с wearable; кемпер-крюки
  граничат с Workshop Wall System (A4).
- **Линия VF** — 2020-профиль и `process: reference` реюзаются в MB-3.
- Соседние домены: repair (клипсы салона ≈ replacement clips),
  electronics (крепления камер/сенсоров на транспорте).

Общие capability-gaps этого домена (лесенки посадок, environment/material
гейты, contact-safety словарь, text embossing, threads/hinge/slide, grid-
стандарт) централизованы в [CAPABILITIES.md](../CAPABILITIES.md) — домен их
КЛИЕНТ, не владелец.
