# Artifact Forge — экосистема: open-core, паки, режимы

Канон коммерческой, лицензионной и pack-модели платформы. Технический
мастер-план — [ROADMAP.md](ROADMAP.md); этот документ отвечает на вопрос
«что открыто, что продаётся и почему», не меняя ни строчки кода.

Формула:

```text
AF = open-source parametric manufacturing engine
     + certified product packs
     + honest validators
     + product modes
     + future Web Studio
```

Рыночная формула: **parametric app store for useful 3D-printable
objects**. Монетизируется не факт генерации STL, а каталог, качество
паков, валидаторы, golden-примеры, отчёты, удобный UI, Web Studio,
print-farm/B2B workflow, premium-стили и custom-разработка архетипов.

**Тезис доверия**: открытые валидаторы, golden-тесты и honesty-отчёты
доказывают, что AF — не prompt-to-STL игрушка. Примеры контрактов,
которые уже измеряются, а не постулируются: `min_wall`, keepouts,
`no_orphan_ports`, `mate_frames_opposed`, water path + overflow honesty,
BOM, print notes, donning window / body-contact для wearable, «functional
core owns safety; skin owns style» для biomorphic.

---

## Пять осей экосистемы

Система не расползается по рынкам (`household_mode`, `auto_mode`,
`garden_mode`…) — вместо этого пять ортогональных осей:

```text
Modes        = проверка (чем изделие опасно/сложно и как его валидировать).
Packs        = продуктовая/коммерческая упаковка (кому продаётся).
Environments = условия эксплуатации (household, vehicle, wet, high-heat…).
Styles       = внешний язык (biomorphic, minimalist, cinematic…).
Tiers        = free / certified / pro.
```

Один pack может содержать изделия разных modes; каждое изделие явно
знает свой mode.

**Главное правило создания mode:**

```text
Новый рынок ≠ новый mode.
Новый валидаторный контракт = новый mode.
```

Применение правила:

| Направление | Что это | Почему |
|---|---|---|
| Household / Home | domain / pack | нет уникальных проверок — хватает Utility/Engineering |
| Desk / Studio | domain / pack | то же |
| Auto / Vehicle | environment profile; позже возможно mode | пока: base mode + warnings (heat/vibration/visibility/airbag); отдельный Mobility-mode ТОЛЬКО когда появятся соответствующие валидаторы |
| Garden | domain | нет своего контракта |
| Plant / Grow | **mode** | вода/свет/растения/обслуживание — свой контракт |
| Workshop | **mode** | нагрузки/стена/инструмент |
| Wearable | **mode** | тело/ремни/комфорт/donning |
| Eyewear | **подрежим Wearable** | лицо/переносица/линзы/дужки — свои constraints |
| Cinema / Prop | **mode** | реквизит/actor-fit/визуальная серия |
| Biomorphic | **overlay** | меняет форму, не владеет функцией |

Компактный финальный список режимов:

```text
Core validation mode:   1. Engineering
Product modes:          2. Utility   3. Workshop/Load-bearing   4. Fluid/Grow
                        5. Wearable/Body-fit   6. Eyewear/Face-fit (подрежим
                        Wearable, выделен из-за сложности)   7. Cinema/Prop
Cross-cutting overlay:  8. Biomorphic/Bioform (style-overlay, не рынок)
```

Environment Profiles (стартовый словарь): household, desk/studio,
vehicle, outdoor, garden, wet/humid, high-heat, child-visible (но НЕ
child-safe unless tested). Style Overlays: biomorphic, minimalist,
retro-futurist, industrial, cinematic.

Примеры комбинаций:

```text
household cable organizer: mode Utility · env household/desk · style minimalist
car phone cable clip:      mode Utility · env vehicle/high-heat/vibration
vertical farm cassette:    mode Fluid/Grow · env indoor/wet · style functional
parametric glasses:        mode Eyewear · env wearable/face-fit · style minimalist|cinematic
alien wrist computer:      mode Cinema/Prop · secondary Wearable · style Biomorphic
biomorphic tool holder:    mode Workshop · env workshop · style Biomorphic
```

В этой итерации Environments и Styles — словарь ДОКУМЕНТА, не поля схем;
технические носители (environment profile на instance, расширение style
registry) — будущие волны (см. линию PK, честно ⬜).

---

## Mode Contract Matrix

| Mode | Смысл | Контракт качества | Коммерческий угол | Статус |
|---|---|---|---|---|
| Engineering | базовая инженерная строгость AF | размеры, min_wall, ports, frames, keepouts, printability | фундамент всех паков | ✅ |
| Utility | бытовые полезные детали | клипсы, крюки, органайзеры, screw zones | Free Starter / витрина | ✅ |
| Workshop | мастерская и инструмент | heavy-duty, wall mounts, ribs, screw patterns, tolerance presets | Workshop Pro | 🔶 |
| Grow / VF | растения, вода, фитолампы | water path, collector, rail, carrier, BOM, overflow honesty | Grow Pro / первый эталон | ✅/🔶 |
| Wearable | тело, ремни, манжеты; подрежимы: Body-mounted utility / **Eyewear (face-fit)** / Costume-prop | body_fit, donning window, strap slots, contact zones, face-fit dims для eyewear, no medical claims | Starter/Pro, cosplay/outdoor/maker; **Eyewear Generator Pro — флагман** | 🔶 |
| Cinema / Prop | реквизит | visual continuity, safe props, modular assembly, actor-fit | Prop Studio / Cinema Pro | ⬜ |
| Biomorphic | органический стиль | functional core owns safety; skin owns style; keepouts protected | premium style layer / Bioform Pro | 🔶 |

Пояснения: Engineering — не отдельный домен, а базовая строгость,
которую используют все остальные режимы. Biomorphic — cross-cutting
style overlay, не самостоятельный рынок. Eyewear — подрежим Wearable,
выделенный из-за собственного валидаторного контракта.
Household/Auto/Garden в матрице не появляются — это domains/environments:
их изделия живут в Utility/Engineering/Workshop с environment-тегами.

---

## Слоистая модель open-core

| Слой | Модель | Текущий код / статус |
|---|---|---|
| Core engine | open source | `core/`, `form/`, `product/`, `catalog/`, `validators/`, `compiler/`, `cad/`, `assembly/`, `repair/`, `review/`, `cli.py` — весь honesty-пайплайн |
| Basic builders / ops | open source | `form/profiles_*`, `recipe_ops.py`, базовые archetypes |
| Free packs | open / free | витрина реально полезных изделий |
| Certified packs | curated | `maturity=production_buildable` + golden-тесты + print confirmation |
| Pro packs | paid | архетипы + параметры + валидаторы + golden examples + отчёты + families |
| Cockpit web | open / local / debug | инженерный визуальный отладчик, не consumer studio |
| Web Studio | paid / future | аккаунты, presets, exports, ordering, private catalogs |
| B2B / custom / print-farm | paid / future | вне core-репозитория |

**Pro Packs — только там, где есть существенная инженерная,
параметрическая или производственная добавленная ценность.**

**Printables-тест** границы Free/Pro:

```text
Если аналогичный объект легко найти на Printables/MakerWorld
и AF не добавляет существенной параметризации/валидации —
он Free или Certified Free, не Pro.
```

Формула платного пака:

```text
Paid pack ≠ paid STL.

Paid pack = archetypes + parameters + validators + golden examples
          + reports + BOM/print notes + supported families + updates.
```

---

## Готовность архитектуры

Каждая строка проверяемо соответствует коду (канон honesty
распространяется и на бизнес-документ).

### Уже есть

| Возможность | Статус | Где / комментарий |
|---|---|---|
| Multi-source catalog loader | ✅ | `catalog/loader.py`: builtin + `catalog/local/`, `Catalog.origins` (id→источник), fail-fast на коллизии id |
| Pure-YAML packs | ✅ | recipe-архетипы ссылаются на ops по имени из реестра — пак без Python возможен сегодня |
| Python-pack precedent | ✅ | VF-паттерн: `recipe_ops_water.py` + `checks_water.py` авто-регистрируются |
| VF как структурный pack | ✅ | свой канон-док (VERTICAL_FARM_PACK.md), свои ops/checks, архетипы, примеры, тесты, отчёты (water/carrier/frame/BOM) |
| Maturity ladder | 🔶 | draft→production_buildable на ArchetypeSpec — информационная, нигде не enforced; готовый certification-гейт |
| Cockpit отделим от core | ✅ | `[web]` extra, импорты только web→core |
| Ports/frames как несущий стандарт | ✅ | после A1/A1.5 — основа Certified-нарратива о совместимости |

### Не хватает

| Возможность | Статус | Комментарий |
|---|---|---|
| PackManifest (`pack.yaml`) | ⬜ | будущая PK-1 |
| `packs/` как третий источник | ⬜ | малая правка loader-а (по образцу LOCAL_DIR) |
| license / author / pack metadata | ⬜ | будущие поля в схемах и отчётах |
| entitlement | ⬜ | ТОЛЬКО cloud-слой, не core |
| plugin discovery | ⬜ | namespace/plugin-механизма нет |
| pack tier enforcement | ⬜ | будущая PK-line |

---

## Структура пака (VF-прецедент)

```text
packs/<name>/
  PACK.md            # законы, контракты, интерфейсы
  pack.yaml          # манифест
  catalog/
    archetypes/
    modifiers/
    examples/
  form_ops/          # свои recipe-ops (если нужны)
  checks/            # свои валидаторы (если нужны)
  tests/
  golden/
  docs/
```

Минимальный будущий `pack.yaml`:

```yaml
id: grow
name: Artifact Forge Grow Pack
tier: pro
license: personal-commercial-split
version: 0.1.0
author: Artifact Forge
modes: [grow, engineering]
```

---

## Product Map по режимам

Free везде ШИРЕ, чем «обрезанное демо» — это реально полезная витрина.
Сводная граница Free/Paid:

| Направление | Free | Paid |
|---|---|---|
| Utility | почти всё базовое | большие families / batch / commercial workflow |
| Workshop | простые держатели/кронштейны | heavy-duty families, BOM, anchors, tolerance presets |
| Grow / VF | демо-модули | Vertical Farm как полноценная система |
| Wearable | простые манжеты/ремешки | body-fit families, очки, сложные крепления |
| Eyewear | демо-оправа / fit-test шаблон | параметрический generator оправ |
| Cinema / Prop | простые панели/greebles | continuity packs, actor-fit, production workflow |
| Biomorphic | demo style | premium bioform/exoskeleton skins |
| B2B | нет | private catalogs, custom archetypes |

### Utility Starter на инженерном ядре

Engineering — фундаментальный validation mode; Utility — продуктовый
mode поверх него. Free showcase: cable clip, wall hanger, cable comb,
zip-tie anchor, grommet, phone stand, small tray, pipe clip, screw
flange, adapter plates, pegboard/Skådis/2020-адаптеры. Роль: доказать
полезность и параметризацию как главное отличие от STL-маркетплейсов.
Tier: Free Starter + Certified Free subset.

### Workshop Starter / Pro

Starter: простые держатели инструмента, настенные крюки, pipe/hose
clips, shelf brackets, pegboard/2020-адаптеры. Pro: heavy-duty wall
mounts, tool families, handle/screw/anchor presets, tolerance presets,
ribs/buttresses, BOM, print-orientation reports. Режим: Engineering +
Workshop. Аудитория: мастерские, гаражи, DIY, print-farms.

### Grow / Vertical Farm Pro — эталон первого серьёзного пака

Состав: water rails, cassettes (coco/sprout/…), collector, caps,
frame/carrier, inlet/outlet adapters, hose mounts, phytolamp brackets,
sensor mounts. Почему Pro-quality уже сейчас: отдельные отчёты (water
path, carrier/frame report, BOM), собственная pack-структура
(ops/checks/tests/док), инженерная СИСТЕМА, а не одиночная деталь.
Риски домена: вода, overflow, обслуживание, протечки, корни,
свет/электрика. Принцип: **VF не обещает больше, чем проверяет;
overflow honesty — часть продукта, а не недостаток**.

### Wearable / Face-fit Mode

Три подрежима: Body-mounted utility / Eyewear (face-fit frames) /
Costume-prop wearable. Позиционирование: maker / outdoor / workshop /
cosplay. НЕ medical, НЕ orthopedic, НЕ safety-critical PPE.

Free: basic forearm cuff, simple strap mount, flashlight mount, basic
action-cam adapter, simple costume cuff, basic eyewear frame template +
measurement guide (non-prescription/costume).

Pro: body-fit cuff families, modular wrist/forearm device platforms,
advanced strap routing, TPU pad systems, left/right mirrored sizing,
Eyewear Generator (см. ниже), sizing presets, comfort/contact reports.

Контракт wearable-mode: contact zones protected, donning/removal window,
strap path valid, no sharp edges on contact zones, no medical /
orthopedic / certified eye-protection claims, no prescription/optical
correctness claims unless externally validated.

### Eyewear — коммерческий флагман

Двойное представление: в Mode Contract Matrix Eyewear — ПОДРЕЖИМ
Wearable (одно семейство валидаторного контракта); в Product Map — своя
подсекция со своей Free/Paid-границей, потому что генератор оправ —
самостоятельный платный флагман.

```text
Eyewear Free:
  basic frame template · measurement guide · simple non-prescription/costume frame

Eyewear Pro (parametric face-fit generator):
  face width · bridge width · lens width/height · temple length ·
  pantoscopic angle · nose pads · hinge blocks · rim thickness ·
  lens groove · screw/insert options · left/right symmetry ·
  style families · print orientation · printable fit-test strips ·
  экспорт нескольких размеров · commercial frame output license
```

Обоснование платности: не «одна оправа», а family-система — сложно
повторить обычным STL, проходит Printables-тест. Линзы, рецепты,
сертификация, защита глаз — вне scope, отдельно и осторожно.

### Cinema / Prop — честно ⬜

Будущая линия (волна P4), не текущая готовность. Возможный состав:
sci-fi панели, greebles, fake vents, prop devices, wrist computers,
модульные маски, creature costume plates, control panels, безопасный
нефункциональный реквизит. Контракт prop-mode: visual continuity,
multi-part assembly, actor-fit, non-functional safety, no real weapon
functionality, print/sand/paint workflow, scale variants. Мосты из
текущей архитектуры: dovetail-адаптеры, манжеты, biomorphic-модификаторы.

### Biomorphic — premium style layer

«Biomorphic не ломает функцию»: functional core owns safety/function,
biomorphic skin owns style/adaptation. Состав: biomorphic shells,
exoskeleton ribs, bone/vein/tendon fields, organic buttresses, branch
clamps, lamp brackets, mask/cuff shells, creature/prop surfaces.
Коммерческая граница юридически и инженерно чистая:

```text
Free core function:  bracket / clamp / cuff / holder.
Paid premium style:  biomorphic skin / exoskeleton / creature language /
                     cinematic detailing.
```

Функциональные зоны, screw zones, каналы, body-contact, ports и
keepouts НЕ принадлежат style layer — style layer обязан их уважать.

---

## Free / Certified / Pro линейка

| Tier | Смысл | Что внутри |
|---|---|---|
| Free | рост, доверие, community | полезные starter packs |
| Certified Free | витрина качества | maturity + golden + print confirmation |
| Pro | платный каталог | families, reports, BOM, advanced validators, updates |
| Studio | платный web-продукт | UI, cloud preview, presets, project saving, ordering |
| Business | B2B / custom | private catalogs, API, white-label, print-farm |

Платные флагманы:

```text
1. Vertical Farm / Grow System Pro
2. Eyewear Generator Pro
3. Workshop Heavy-Duty Families
4. Wearable Body-Fit Utility Pro
5. Biomorphic Premium Style Layer
6. Cinema/Prop Studio Workflow
7. B2B / private catalogs / custom archetypes
```

## Studio-лицензии

| Лицензия | Для кого | Возможности |
|---|---|---|
| Indie Maker | личное использование | Pro packs personal, cloud exports |
| Print Farm | мелкое производство | commercial output license, batch generation |
| Prop Studio | кино/клипы/косплей | prop packs, continuity, actor-fit variants |
| Education / FabLab | обучение | классы, локальные пресеты, free/certified packs |
| B2B Custom | компании | private archetypes, custom validators, API |

---

## Лицензии

### Core license — критерии, выбор отложен

Решение принимается **перед публичной публикацией репозитория**;
сейчас фиксируются только критерии:

| Критерий | Apache-2.0 | AGPL-3.0 | BSL / FSL |
|---|---|---|---|
| доверие maker community | высокое | среднее/высокое | спорное |
| интеграция вендорами принтеров | высокая | ниже | ниже |
| защита от cloud-клонов | низкая | высокая | высокая |
| contributor friction | низкий | выше | выше |
| совместимость с pack-бизнесом | высокая | высокая | средняя |
| простота понимания | высокая | средняя | ниже |

### Code license ≠ generated model license

```text
Generated outputs belong to the user,
subject to the license of the pack/archetype used.
```

Для Pro-паков:

```text
Personal license:   печатать для себя · дарить · дом/мастерская ·
                    не продавать массово физические отпечатки.
Commercial license: продавать отпечатки · print farm · заказное
                    производство · НЕЛЬЗЯ перепродавать сам
                    pack/archetype/source data.
```

### Носитель лицензии в архитектуре — ⬜ (PK-1/PK-3)

Будущие поля: `license`, `author`, `pack_id`, `tier`, `usage_rights`.
Поверхности отображения: ArchetypeSpec, ProductInstance,
honesty_report, BOM, build package, Web Studio export.

---

## Линия PK — Pack Economy (все волны ⬜)

### PK-1 — Pack Mechanism v1

Технически оформить паки как first-class source: `packs/` — третий
источник catalog loader (по образцу LOCAL_DIR), `pack.yaml`,
origin=`pack:<id>`, license/author/pack-метаданные + notices в
reports/BOM, выделение VF в `packs/grow/`, pack-тесты по образцу
`test_vertical_farm_pack`. Желательно после/вместе с A2 — BOM усиливает
Pro-формулу.

### PK-2 — Free Starters + Certified Criteria

Utility / Workshop / Wearable Starter, Bioform Demo. Критерии Certified:
maturity=production_buildable, golden examples, passing validators,
print confirmation, documented material/orientation, honesty report без
скрытых warnings. Карта repo boundaries перед публикацией.

### PK-3 — Commercial Layer

Personal/commercial маркировка, build package notices, Pro-metadata,
commercial output / print-farm license. **No DRM in core** — entitlement
живёт только в cloud/Web Studio.

### PK-4 — Web Studio

Accounts, presets, saved projects, cloud preview, guided configuration,
exports, order print, private catalogs, B2B/white-label. Граница:
**Cockpit = open local engineering debugger; Web Studio = paid
consumer/pro product.**

---

## Community Operating Model

Техническая структура пака, tiers и линия PK отвечают на «что»; этот
раздел — на «как»: кто публикует пак, как он проходит проверку, кто
отвечает за безопасность, как он становится Certified, как решаются
споры и как не захламить экосистему.

### Линия CP — Community Packs (все волны ⬜)

```text
CP-1 Community Pack Template   — шаблон пака + PACK_AUTHORING-гайд
CP-2 Community Registry        — реестр/индекс community-паков
CP-3 Certification Review      — процесс проверки на Certified
CP-4 Maintainer / Governance   — мейнтейнеры, споры, блокировки
```

### Жизненный цикл community-пака

```text
community_draft → community_validated → community_featured →
certified_free → official_pack

боковые состояния: deprecated · blocked
```

Связь с maturity: состояния пака — каталожный статус УПАКОВКИ;
`maturity` на архетипе — статус самого артефакта. Пак в
`community_featured` может содержать архетипы разной maturity;
`certified_free` требует production_buildable у всех.

**Главное правило:**

```text
Community pack can be useful without being certified.
Certified pack must be boringly reliable.
```

Комьюнити свободно экспериментирует; бейдж Certified получает только
то, что прошло валидаторы, golden examples, print confirmation и несёт
честные warnings — те же критерии, что у Certified Free.

### Pack Trust Badges

Не «красивые бейджи», а короткая упаковка honesty report:

```text
validated · printed · multi-printer-tested · supportless ·
commercial-output-ready · wet-safe-tested · body-contact-reviewed ·
vehicle-environment-warning · no-medical-claims
```

Каждый бейдж обязан сводиться к измеряемым проверкам/подтверждениям —
бейдж без validator-backed основания не существует (тот же канон, что
для фич).

### Contributor economy — зарезервированное место

Не реализуется сейчас, но фиксируется, чтобы потом не объяснять задним
числом путь «человек с YAML → автор certified/pro пака»:

```text
author · license · donation link · commercial upgrade path ·
official certification request · revenue share для Pro/Studio
(если появится marketplace)
```

### Open-source launch checklist

Перед публичной выкладкой репозитория:

```text
OS-1 License decision        OS-5 SECURITY.md / safety policy
OS-2 Repo cleanup            OS-6 Good first packs
OS-3 CONTRIBUTING.md         OS-7 Example gallery
OS-4 PACK_AUTHORING.md       OS-8 Public roadmap
```

Принцип: выкладывать не «просто код», а сразу «как делать паки».
Контекст рынка: у Printables уже есть free/paid-механики и
brand/community-сценарии (official brand profiles, replacement parts,
accessories, cosplay props, paid Store) — экосистема без внятного
authoring-пути проиграет им по умолчанию.

---

## Future Domains to Watch

Рынок аддитивного производства растёт ($30.6B в 2025 → $37.6B в 2026 →
прогноз $168.9B к 2033, Grand View Research; драйверы — on-demand
production, mass customization, rapid prototyping, digital
manufacturing). Поэтому AF продаётся не как «ещё один сайт моделей», а
как параметрическая инфраструктура для кастомных деталей и малых
производственных workflow.

Домены ниже НЕ становятся режимами (правило пяти осей: новый рынок ≠
новый mode) — это domains/packs поверх существующих режимов и
environment-профилей.

```text
Future Domains to Watch:
- Repair / Spare Parts / Right-to-Repair
- Manufacturing Aids / Jigs / Fixtures
- Electronics / IoT / Smart Home
- Accessibility / Adaptive Utility
- Mobility / Bike / Vehicle Accessories
- Music / Studio / Creator Tools
- Craft / Mold / Ceramics
- Pet / Aquarium / Terrarium
- Education / FabLab
- Medical/Dental — explicitly out of public scope until certification
  path exists
```

Детальные планы доменов: [docs/domains/INDEX.md](domains/INDEX.md).

### Repair / Spare Parts / Right-to-Repair

План: [domains/repair/PLAN.md](domains/repair/PLAN.md).

Возможно, важнейший недостающий домен. EU закрепляет право потребителя
требовать ремонт технически ремонтируемых товаров (стиральные машины,
пылесосы, телефоны — в разумный срок и по разумной цене); Philips уже
тестирует модель печати replacement/accessory parts через Printables с
акцентом на материал, ориентацию печати и safety/quality standards.

```text
Repair Pack / Replacement Parts Pack
mode: Engineering / Utility / Workshop
environment: household / appliance / high-heat / wet
tier: Free + Certified + B2B/OEM
```

Примеры: ручки, защёлки, крышки, направляющие, клипсы корпусов, ножки
приборов, адаптеры шлангов, держатели фильтров, replacement knobs,
appliance-specific fit templates. Это domain/pack, не новый mode.

### Jigs / Fixtures / Production Aids

План: [domains/jigs/PLAN.md](domains/jigs/PLAN.md).

Сильнейшее B2B-направление: производственный рынок смотрит на AM как на
production resource (digital twins для legacy-оборудования, reverse
engineering, on-demand replacement components, production tooling,
assembly/inspection fixtures, visual management aids).

```text
Manufacturing Aids Pack
mode: Engineering / Workshop
tier: Business / Pro
```

Примеры: drilling jigs, soldering/assembly fixtures, inspection gauges,
spacer templates, alignment blocks, repeatable cutting guides,
small-batch fixtures. Компаниям важны repeatability, reports, labels,
BOM, материал и версия — ровно то, что AF делает валидаторами.

### Electronics / IoT / Smart Home

План: [domains/electronics/PLAN.md](domains/electronics/PLAN.md).

```text
Electronics / IoT Pack
mode: Engineering / Utility
environment: indoor / outdoor / wet / high-heat
```

Примеры: корпуса ESP32/Arduino/Raspberry Pi, sensor mounts, cable
glands, DIN-rail адаптеры, wall boxes, camera mounts, LED-каналы,
вентиляционные решётки, snap-fit enclosures. Платность — только за
хорошие families: вентиляция, разные платы, кабельные вводы,
DIN/2020/стена, print notes.

### Accessibility / Adaptive Utility

План: [domains/accessibility/PLAN.md](domains/accessibility/PLAN.md).

Перспективно, но с осторожной формулировкой: НЕ medical, НЕ
rehabilitation, НЕ certified assistive device без внешней валидации.

```text
Adaptive Utility Pack
mode: Wearable / Utility / Engineering
claims: daily-living accessory, no medical claims
```

Примеры: утолщённые ручки, держатели столовых приборов, one-hand
opening aids, grip adapters, switch/button extenders,
book/phone/tablet supports, custom straps. Social-good направление:
многое должно быть Free/Certified Free; Pro — для clinics/fablabs
только после юридической проработки.

### Mobility / Bike / Vehicle Accessories

План: [domains/mobility/PLAN.md](domains/mobility/PLAN.md).

Auto остаётся environment profile, не mode.

```text
Mobility Pack
mode: Engineering / Utility / Workshop
environment: vehicle / outdoor / high-heat / vibration / UV
```

Примеры: bicycle light mounts, handlebar adapters, cargo clips,
van/camper organizers, car cable clips, dashboard-safe non-critical
holders, action-cam mounts. Жёсткие ограничения: не airbag zone, не
pedal zone, не critical road-safety part; PLA не для high-heat салона.

### Music / Studio / Creator Tools

План: [domains/studio/PLAN.md](domains/studio/PLAN.md).

Органичный для автора и недооценённый домен.

```text
Studio / Music Pack
mode: Utility / Workshop / Engineering
environment: desk / studio
style: retro-futurist / minimalist / cinematic
```

Примеры: держатели синтов/контроллеров, MPC/MiniFreak/MiniFuse cable
routing, under-desk audio interface mount, patch cable combs, headphone
hooks, mic cable clips, acoustic panel spacers, LED/neon strip mounts,
desktop risers. Отличный Free/Certified showcase: красиво фотографи-
руется, полезно, близко к аудитории, без тяжёлой ответственности.

### Craft / Mold / Ceramics

План: [domains/craft/PLAN.md](domains/craft/PLAN.md).

```text
Craft / Mold Pack
mode: Engineering / Utility
environment: workshop
```

Примеры: формы для гипса/силикона, шаблоны для керамики, stamp tools,
texture rollers, литейные воронки, jigs для повторяемых изделий,
soap/candle molds. AF-ценность — параметризация: размер, усадка, draft
angle, split lines, keys, vents.

### Pet / Aquarium / Terrarium

План: [domains/pet/PLAN.md](domains/pet/PLAN.md).

Domain + environments, не отдельный mode.

```text
Pet / Aquarium Pack
mode: Utility / Fluid-Grow / Engineering
environment: wet / humid
```

Примеры: держатели трубок, кормушки, sensor holders, aquarium cable
clips, terrarium plant mounts, misting nozzle mounts. Обязательные
предупреждения: материалы, вода, животные, чистка, токсичность.
Free/Certified Free; Pro — только при появлении серьёзной системы.

### Education / FabLab

План: [domains/education/PLAN.md](domains/education/PLAN.md).

Наполняет уже существующую Education/FabLab-лицензию продуктовым
содержанием.

```text
Education Pack
mode: Utility / Engineering / Cinema
tier: Free / Edu
```

Примеры: учебные механизмы, разрезные модели, printable validators
demo, bridge/overhang test objects, parametric lesson kits, simple
robotics chassis, classroom-safe construction kits. Стратегическая
роль: люди учатся на AF и начинают делать community packs.

### Medical / Dental — explicitly excluded

Граница записана: [domains/medical/EXCLUDED.md](domains/medical/EXCLUDED.md).

Рынок огромен (dental 3D printing: $4.9B в 2025 → $6.2B в 2026 →
прогноз $26.7B к 2033, GVR; драйверы digital dentistry и customized
high-precision solutions), но регуляторика, материалы,
биосовместимость и ответственность делают его непригодным для раннего
consumer-домена:

```text
Medical/Dental:
  excluded from public packs for now;
  research/B2B only;
  no patient-specific medical claims;
  requires external certification path.
```

---

## Риски и принципы

1. **Pro-паки технически копируемы** (YAML/data). Ответ — не DRM:
   лицензия, обновления, certified status, поддержка, Studio-удобство,
   B2B-сервисы, print-farm workflow, доверие к official packs.
2. **Honesty нельзя продавать**: Pro НЕ получает более снисходительных
   валидаторов — наоборот: строже отчёты, больше golden, лучше
   documented constraints.
3. **Mode claims честные**: Wearable — accessory, не medical; Grow —
   water path/overflow honesty, не «нет протечек» без тестов; Prop —
   safe non-functional, не оружие; Biomorphic — style shell, не ломает
   functional core.
4. **Namespace/id**: loader fail-fast на коллизии достаточно;
   конвенция префиксов `utility_/workshop_/grow_/wearable_/prop_/bio_` —
   human-readable, не security-механизм.

Архитектурная опора всей модели: большинство новых изделий собираются
как YAML / Form Recipe / Validators; новый Python нужен только для
настоящих building blocks и capability gaps — что и делает data-паки
естественной единицей продукта.
