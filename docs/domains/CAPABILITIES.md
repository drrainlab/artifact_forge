# Общие capabilities доменов — карта спроса

Доменные планы вскрыли повторяющиеся capability gaps. Этот файл — их
ЕДИНСТВЕННЫЙ реестр: домен не реализует «свой маленький hinge» или свой
валидатор лесенки — он становится клиентом общей capability. Карта
доменов тем самым превращается из набора планов в **матрицу спроса на
будущие capabilities AF**.

## Матрица: gap → домены-клиенты → owner wave

| Capability gap | Домены-клиенты | Owner wave |
|---|---|---|
| environment profile (носитель на instance) | Mobility, Electronics, Pet, Repair, Craft | PK / E2 |
| manufacturing.material_env_ok | Mobility, Electronics, Repair, Pet | E2 |
| contact safety registry | Accessibility, Craft, Pet, Repair | PK / E2 |
| text embossing (G0) | Jigs, Repair, Education, Electronics, Studio | G0 |
| threads | Repair, Electronics, Education | E-stage (R5-остаток) |
| hinge / slide | Repair, Pet, Accessibility, Education | E-stage (R4/R5-остаток) |
| fit / gauge / tolerance ladder | Repair, Jigs, Education | shared Form |
| texture op | Craft, Accessibility, Biomorphic | Bio-4M / Form |
| seal / gasket continuity | Electronics, Pet-adjacent, VF-adjacent | Fluid/Seal |
| family / preset mechanism | Repair, Jigs, Electronics, Mobility, Pet | A4 (extends/family) |

## Централизованные блоки

### 1. Fit / Gauge / Tolerance Ladder — одна capability, три роли

Repair (fit-workflow), Jigs (gauge / go-no-go), Education (lesson
object) хотят ОДНУ И ТУ ЖЕ лесенку посадок:

```text
core capability: fit_ladder / tolerance_ladder / gauge_ladder
shared validators:
  form.ladder_steps_ok          — монотонность и номинал каждой ступени
  form.gauge_tolerance_ok       — go/no-go band
  form.fit_template_ladder_ok   — примерочный workflow
domain roles:
  Repair    → fit workflow (замерил узел → выбрал ступень → деталь в band)
  Jigs      → workshop gauge / go-no-go пробники
  Education → учебный объект (щупаешь clearance band руками)
```

Правило: три домена НЕ заводят три похожих валидатора с разной
семантикой — ядро одно, роли разные.

### 2. Environment & Material Profile Layer

Mobility («PLA не для салона» должен быть гейтом, не примечанием),
Electronics (outdoor/wet/high-heat, mains/IP warnings), Pet (wet/humid +
toxicity), Repair (appliance/high-heat), Craft (материалы отливки):

```text
environment профили:
  indoor · outdoor · wet · humid · high_heat · vehicle · UV · vibration
material claims (defaults):
  not_food_safe_by_default · not_animal_safe_tested · not_IP_rated ·
  not_UL94 · not_high_heat_safe_with_PLA
общий валидатор:  manufacturing.material_env_ok
warning-генератор: report.environment_warning_block
```

Носитель — будущее поле instance (линия PK, E2); до его появления
warnings живут текстовыми нотами в отчётах, но словарь уже единый.

### 3. Contact Safety Claims Registry

Food-safe/toxicity/contact-claims разбросаны по Accessibility, Craft,
Repair, Pet — собираются в один словарь (это НЕ mode, это общий
claims/material registry):

```text
contact_kind:
  skin_short · skin_long · food · animal_water · aquarium · wet_general
default:
  no certified contact claim unless explicit tested profile exists
```

### 4. G0 — Label / Text Embossing

Маленький глобальный building block с самым широким спросом (Jigs —
блокер версии/номера; Education — подписи ступеней; Repair — артикулы;
Electronics/Studio — маркировка корпусов; везде — «NOT FOR SAFETY USE»):

```text
G0 backlog:
  add_label() / add_embossed_text() / add_debossed_text()
  роли: version_tag · step_label · part_number · safety_label
```

### 5. Shared E-stage blockers (механика)

Домены НЕ реализуют собственные шарниры/резьбы — ждут общих building
blocks и стартуют волны, которые их не требуют:

```text
threads      → repair caps · electronics glands          (R5-остаток)
hinge        → repair lids · accessibility openers ·
               education hinge lesson                     (R4-остаток pin_hinge)
slide/shutter→ pet feeders · будущие механизмы            (E-stage)
```

### 6. Seal / Wet / Leak — три разных контракта на общей топологии

Валидаторы могут реюзать топологию воды, но claims разные; Electronics
НЕ становится Fluid/Grow (это Engineering/Utility + wet environment):

```text
Fluid/Grow water path : вода как рабочая среда — overflow, drain,
                        no orphan fluid ports
Electronics seal      : внешний дождь/брызги — gasket continuity,
                        «rain-shielded, not rated», БЕЗ IP-рейтингов
Pet wet               : мокрая зона + animal/toxicity warnings +
                        cleanability
```

### 7. Mounting Grid / Rail Standard

2020/grid/rail встречаются в Electronics, Mobility, Jigs, Studio, VF —
один системный слой вместо «своих рельс» в каждом домене:

```text
Mounting Grid / Rail Standard (owner: A4 Wall System):
  2020 profile · wall grid · workshop rail · camper/cargo rail ·
  fixture grid_pitch
```

## Как читать вместе с планами

Каждый PLAN.md в секциях 3 (gaps ⬜) и 9 (связи) ссылается сюда; при
реализации capability owner-волна закрывает строку матрицы, и ВСЕ
домены-клиенты получают её одновременно. Появление нового общего gap в
двух и более доменах = обязанность добавить строку в эту матрицу, а не
реализовать локально.
