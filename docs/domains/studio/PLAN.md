# Music / Studio / Creator — доменный план (ST)

Развёртка домена из [ECOSYSTEM.md](../../ECOSYSTEM.md) («Future Domains
to Watch → Music / Studio / Creator Tools»). Канон шаблона —
[INDEX.md](../INDEX.md).

## 1. Scope и позиционирование

Рабочее место музыканта/креатора: крепления аудио-интерфейсов, стенды
синтов и контроллеров, кабель-менеджмент патч-кабелей, крюки наушников,
акустика и LED-каналы. **Самый дешёвый showcase-домен платформы**: реюз
почти 100%, большинство изделий — чистые YAML-пресеты на существующих
ops/архетипах, ни одного нового building block в первой волне.

**Каких claims домен НЕ делает:**

- никаких акустических заявлений («улучшает звук комнаты» — spacers
  держат панель, не сертифицируют RT60);
- никакой электробезопасности (LED-каналы — механика, не электрика);
- не rack-mount стандарт 19" с несущими заявлениями (только desktop).

## 2. Mode / Environment / Tier

Домен = pack, НЕ новый mode: у стола музыканта нет уникального
валидаторного контракта — хватает Utility/Engineering/Workshop
(ECOSYSTEM: «Desk / Studio → domain / pack»).

```text
mode:        Utility / Workshop / Engineering
environment: desk / studio
style:       retro-futurist / minimalist / cinematic
tier:        Free / Certified-центричный; Pro минимален
```

## 3. Что уже есть в движке — карта реюза

| Building block | Статус | Реюз в домене |
|---|---|---|
| `underdesk_cable_clip_v2/v3` (v3 sideprint) | ✅ | база golden ST-1: подстольный маунт — то же семейство |
| `headphone_hook_v1` | ✅ | studio-пресет как есть |
| `cable_comb_v1`, `cable_raceway_v1`, `cable_grommet_plate_v1`, `cable_junction_box_v1`, `zip_tie_anchor_v1` | ✅ | патч-кабели, разводка стола |
| `phone_stand_v1` (device_slot = f(tilt), COM-гейт) | ✅ | обобщение на контроллеры: MPC / MiniFreak — тот же slot-механизм и тот же `form.stability_footprint` |
| `adapter_plate_v1`, `fastener_plate_v1`, `standoff_pattern`, `boss_pattern` | ✅ | крепёжные плиты под интерфейсы и мелкое железо |
| `enclosure_base_v1`/`enclosure_lid_v1` (+ `*_snap_v1`), `port_cutout` (usb_c/audio), `wire_exit` | ✅ | педали, DI-боксы, кастомные коробки |
| `wall_tool_ring_clamp_v1` / `wall_ring_mount` | ✅ | настенные кольца под микрофоны/наушники по Ø |
| `truss_beam_v1`, `shelf_bracket_v1` (loft + косынки) | ✅ | desktop risers ST-3 |
| Интерфейсы `screw_pattern`, `snap_joint`, `cable_pass`; `forge compat` | ✅ | typed-порты и совместимость из коробки |
| Модификаторы hex/grid/voronoi, магнитные карманы, био-скины Bio-4M | ✅ | стилевая витрина (retro-futurist панели) |
| Text embossing op (подписи каналов на combs) | ⬜ | приятный, не блокер |
| Style registry как поле схем | ⬜ | стили пока словарь документа (канон ECOSYSTEM) |

Capability gaps домен НЕ создаёт — в этом его ценность как витрины.

## 4. Волны ST-1..3

### ST-1 — Desk Audio Essentials ⬜

Golden-артефакт: **`underdesk_audio_interface_mount`** — пресет на
существующих ops (rounded_plate + rounded_rect_cutout + screw/heatset +
cord_slot_pair) — **чистый YAML, ноль нового Python**; размерные пресеты
MiniFuse / Scarlett. Рядом в волне: `patch_cable_comb` пресет
(cable_comb_v1, шаг под патч-кабели) и headphone hook studio-пресет.

Критерий: golden билдится в grade A под два размерных пресета
(MiniFuse 2 / Scarlett 2i2) сменой одного блока параметров;
`form.device_slot_fit_ok` и manufacturing.* зелёные; фото-сет для
галереи OS-7.

### ST-2 — Stands & Mic Line ⬜

Стенды синтов/контроллеров: generalization `phone_stand_v1` —
device_slot = f(tilt) для MPC One / MiniFreak (device-пресеты по массе
и габаритам), **COM-гейт `form.stability_footprint` уже существует** и
становится главным гейтом волны (тяжёлый контроллер на наклонном
стенде — ровно его случай). Плюс mic cable clips (клипсы XLR на стойку —
семейство underdesk/pipe-клипс).

### ST-3 — Room & Light ⬜

Acoustic panel spacers (adapter_plate + standoff_pattern; claims — см.
§1), LED/neon strip channels (реюз `cable_raceway_v1` — канал есть
канал), desktop risers (`truss_beam_v1` / `shelf_bracket_v1` с
косынками). Стилевые пресеты retro-futurist поверх готовых модификаторов.

## 5. Интерфейсы и стандарты домена

**Desk Device Mount Standard** (по образцу Cassette Interface Standard):

- shared-параметры: `device_w/d/h`, `tilt_deg`, `lip_h`, `cable_gap`;
- frame-ключи: `slot_floor_n` (нормаль ложа), `cable_exit_*`;
- typed ports: `screw_pattern` (подстольный/настенный крепёж),
  `cable_pass` (выход кабелей — инстансы порта, объявленного в A1),
  `snap_joint` (съёмные крышки боксов).

Device-пресеты (MiniFuse, Scarlett, MPC, MiniFreak) — словарь данных
поверх стандарта, не новые архетипы: смена устройства = смена пресета.

## 6. Валидаторы-кандидаты

| Валидатор | База | Статус |
|---|---|---|
| `form.stability_footprint` | существует (COM-гейт phone_stand) | ✅ реюз как есть |
| `form.device_slot_fit_ok` | clearance-band механика интерфейсов | ✅ механика есть |
| `form.cable_comb_throat_ok` | измерение горла зуба vs Ø кабеля | ✅ механика есть |
| `manufacturing.min_wall` / `bed_fit` / `overhang` / `supportless` | существуют | ✅ |
| `assembly.no_orphan_ports`, `interface.mate_frames_opposed` | существуют | ✅ |

Всё существует или собирается из существующего — новых
валидатор-семейств волны не требуют.

## 7. Free / Pro граница (Printables-тест)

Домен **Free/Certified-центричный**: почти всё одиночное легко найти на
Printables — значит оно Free by rule. Pro минимален:

| Free / Certified | Pro |
|---|---|
| interface mount, patch comb, headphone hook, стенд под один девайс, LED-канал | разве что **full studio kit**: согласованный набор (mount + combs + стенды + risers) с единым стилем, compat-отчётом и BOM |
| device-пресеты по одному | батч-генерация размерной линейки для print-farm |

Если full kit не наберёт добавленной ценности — честно остаётся
Certified Free: роль домена не выручка (см. §8–9).

## 8. Риски и claims

1. Главный риск — нулевой: нет тела, воды, транспорта, нагрузок выше
   настольных. Именно поэтому домен — идеальная витрина.
2. Не обещать акустику/электрику (см. §1) — claims фиксируются в PACK.md.
3. Стенды с тяжёлыми контроллерами — единственная механика риска:
   COM-гейт обязателен на каждом device-пресете (не только на golden).
4. Риск репутационный: витрина обязана быть «boringly reliable» —
   Certified-критерии (golden + print confirmation) без исключений.

## 9. Связи

- **Роль в экосистеме**: витрина CP-registry и фото-галереи OS-7;
  аудитория автора — домен служит доверию и комьюнити, не выручке.
- **A1/A1.5 ✅** — screw/snap/cable_pass порты; `forge compat` на studio
  kit. **A2 BOM ⬜** — винты/вставки в build package для kit-варианта.
- **Линия PK** — ST-1 кандидат в первый чистый pure-YAML pack (PK-1
  прецедент «пак без Python»); Certified-критерии PK-2 обкатываются тут.
- **Линия CP** — образцовый community-шаблон: «сделай пресет своего
  девайса» = идеальный good first pack (OS-6).
- Соседние домены: electronics (enclosures/DIN глубже), education
  (стенд как урок параметризации), repair (ручки/ножки аппаратуры).

Общие capability-gaps этого домена (лесенки посадок, environment/material
гейты, contact-safety словарь, text embossing, threads/hinge/slide, grid-
стандарт) централизованы в [CAPABILITIES.md](../CAPABILITIES.md) — домен их
КЛИЕНТ, не владелец.
