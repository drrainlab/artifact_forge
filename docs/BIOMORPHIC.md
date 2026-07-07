# Biomorphic Products — канон раздела

Раздел «Биоморфные изделия»: библиотека Biomechanical Product System — полезные
3D-печатные объекты, где инженерная функция совмещена с органической/костной/
биомеханической формой. Две параллельные линии:

```
A. Functional Core Archetypes   — инженерные ядра (функция)
B. Biomorphic Skin / Exoskeleton Modifiers — слой формы по разрешённым регионам
```

## Законы раздела

1. **functional core owns function; biomorphic layer owns form.**
   Изделие сначала — честный инженерный объект (нагрузка, крепления, посадки,
   каналы, толщины, print orientation). Био-слой накладывается только на
   безопасные зоны и только после того, как ядро проходит валидацию.
2. **Bio package should not own generic mounting logic.**
   Workshop Mounts Pack — functional-core provider для всех настенных /
   подстольных / рейковых / трубных держателей (wall_screw_mount, pegboard,
   french cleat, rail, pipe clamp, zip tie …). Био-версии крепежей оформляются
   как presets/extensions поверх workshop-ядер (`extends:` — механизм Bio-4A),
   НИКОГДА не как новый functional core, если функция уже покрыта.
3. **Красивый органический объект со сломанной функцией — FAIL.**
   Style claim без validator-backed геометрии — галлюцинация: фича остаётся
   missing / engine gap (см. Honesty ниже).
4. **Биоморфный слой растёт только там, где разрешает region map.**

## Маппинг bio-ролей → RegionRole

Новая роль enum'а оправдана только новым КЛАССОМ ПОВЕДЕНИЯ (другой таргетинг
модификаторов, другая keepout-семантика, валидатор, который её читает).
Флейвор живёт в `id`/`label`/`aliases` региона.

| Роль из ТЗ | RegionRole | Комментарий |
|---|---|---|
| decorative_outer_shell, exoskeleton_panel | `exoskeleton_panel` (НОВАЯ) | поверхность, где растут рёбра И режутся окна |
| rib_anchor | `rib_anchor` (НОВАЯ) | куда обязаны приземляться корни рёбер |
| boss/channel/contact/interface keepout | `interface_keepout` (НОВАЯ) | ведёт себя одинаково: вето вырезам; в PROTECTED_ROLES |
| load_path_region, primary_load_path | `high_stress_region` | уже protected; рёбра растут К нему |
| window_safe_zone | `aesthetic_lightening` | «удалять материал можно» |
| saddle_contact | `soft_contact_surface` | точное совпадение семантики |
| rail_interface | `mounting_surface` | роль добавим вместе с rail-модификатором |
| screw_zone | `fastener_keepout` | существующая |
| snap_root | `high_stress_region` (+ region.snap_root_not_perforated) | существующий чек |
| secondary_load_surface | — (drop) | никто не читает; вторичное усиление — свойство графа |
| vent_surface | позже, вместе с add_gill_vents | правило «роль приходит со своим потребителем» |
| grip_texture_zone | позже, вместе с handle_grip ядром | то же |
| electronics/water keepout | `interface_keepout` (id-флейвор) | до появления спец-валидаторов |

`EXO_PROTECTED_ROLES` (form/exoskeleton/masks.py) — строже глобального
`PROTECTED_ROLES`: добавляет soft_contact/seal/retaining. Глобальный набор НЕ
расширяем этими ролями — сдвинул бы golden-поля существующих архетипов;
sync-тест гарантирует PROTECTED ⊆ EXO_PROTECTED.

## Таргетинг-семантика био-модификаторов

- `apply_biomorphic_exoskeleton`: **primary target `exoskeleton_panel`**
  (поверхность роста рёбер); fallback `aesthetic_lightening` для plate-ядер —
  аппликатор пишет note, когда работает по fallback.
- `add_bone_windows`: главный потребитель `aesthetic_lightening` (зона
  перфорации). Окна без графа.
- Общий forbidden-набор всех био-модификаторов: fastener_keepout,
  high_stress_region, soft_contact_surface, retaining_flexure, seal_surface,
  interface_keepout.

## Жизненный цикл архетипа (`maturity`)

```
draft → metadata_only → recipe_valid → form_valid → sandbox_buildable → production_buildable
```

Информационное поле `maturity:` на ArchetypeSpec (Bio-0). Вычисляемый статус
(recipe/buildable/metadata_only) остаётся источником правды о собираемости.
Bio-4A может расширить maturity на presets/families/extensions — чтобы у
`angle_grinder_holder_65mm_biomorphic` (продукт-пресет) был свой этап жизни.

## Правила добавления модификатора

Каждый новый био-модификатор обязан указать: target roles + forbidden roles
(общий набор выше — минимум), типизированные params с диапазонами, validators
(что ИЗМЕРЯЕТ обещанное), provides_features (только verified_by-подкреплённые),
golden-архетип для теста. Модификатор без аппликатора легален и честен:
apply даёт engine-gap WARN, фичи не строятся (см. organic_taper_outer_shell,
biomech_surface_texture — паттерн «declared ahead of applicator»).

## Load paths

Силовые биоморфные изделия объявляют маршруты силы на архетипе:

```yaml
load_paths:
  - {from: wall_screw_bosses, to: tool_cradle, priority: primary}
  - {from: lower_flange_zone, to: cantilever_tip, priority: secondary}
```

`from`/`to` — id регионов (биндятся fail-fast при загрузке). Substrate Bio-2
использует их как сиды роста; проверки: `form.load_paths_connected` (маршрут
существует в rib-графе), `form.no_load_path_through_keepout` (полилиния чиста),
`form.primary_load_path_has_ribs` (Bio-3: утолщённые рёбра на primary).
`form.rib_roots_touch_substrate` покрывает «rib_roots_touch_mounting_regions»
из ТЗ. Без load_paths — эвристика (HIGH_STRESS-центры + датумы), проверки
проходят vacuously.

## Honesty по фазам

Bio-2 создаёт **проверяемый skeleton intent** (IR): rib graph, окна, маски,
debug JSON — form.* проверки проходят на validate. Материализация в CAD — Bio-3:
verified_by био-фич включают `topology.exoskeleton_ribs_materialized` /
`topology.organic_windows_open`, поэтому до Bio-3 фичи честно
**supported-but-not-built** (mark_built требует ВСЕ verified_by). Это задумано.

## Roadmap

Био-дорожка встроена в мастер-план [ROADMAP.md](ROADMAP.md): механизм
extends/preset (Bio-4A) строится в волне A4, multi-part био-сборки
(Bio-6) — после портов (A1).

- **Bio-0** vocabulary/roles/metadata; **Bio-1** branch clamp core;
  **Bio-2** exoskeleton IR — сделаны этой итерацией.
- **Bio-3** Exoskeleton CAD Materialization (обязательный следующий шаг):
  rib graph → smooth ribs (rib_tube_sweep), node blends (metaball_params уже
  в IR), organic window cuts, welded to substrate; тогда же — аппликаторы
  organic_taper_outer_shell / biomech_surface_texture.
- **Bio-4A** Workshop Mounts bridge: маппинг workshop-регионов → био-роли,
  механизм extends/preset/family, maturity на пресетах.
- **Bio-4B** biomorphic presets поверх workshop mounts:
  angle_grinder_holder_65mm_biomorphic, heat_gun_holder_bone_windows,
  cable_hose_wall_hook_biomorphic, e27_wall_lamp_socket_holder_biomech,
  branch_tool_mount_adapter_bio.
- **Bio-5** Curved/Cylindrical/Swept surfaces (маппинг по кривым панелям;
  сейчас аппликатор честно отказывает на cylindrical).
- **Bio-6** Biomechanical Motifs & Assemblies: vertebra chains, tendon
  bridges, organic latches, bio dovetail covers, multi-part сборки.

Будущие модификаторы (roadmap; YAML-заглушек не плодим): add_tendon_ribs,
add_gill_vents, add_segmented_armor_plates, add_pore_field,
add_mycelium_network, add_vertebra_segments, add_load_path_ribs (структурный,
shared с Workshop), add_blended_boss_cluster, add_organic_outer_shell,
add_muscle_fillet_transition.

## Критерий качества

Изделие успешно, когда одновременно: работает функционально; печатается без
абсурдных поддержек; не ломает посадки/каналы/интерфейсы; экономит пластик,
где можно; усиливает load paths, где нужно; выглядит выращенным, а не
коробкой с декором.

## Bio-4M — Implicit Exoskeleton Skin (SDF, STL-first)

Bio-4M is the visual/mesh successor to BRep Bio-3 for organic-looking
parts; BRep path remains useful for exact/simple mechanical geometry;
implicit path is required for Giger/bone/grown surfaces.

BRep path remains source of exact mechanical truth (STEP). Implicit mesh
path is source of organic printable appearance (STL).

### Включение

```yaml
style:
  surface: biomechanical_exoskeleton   # обязательное условие
  skin: implicit                       # включает SDF-движок
  skin_resolution: 0.4                 # воксель, мм (0.2–1.0)
  # опциональные оверрайды (по умолчанию — производные от organicity o):
  # skin_k_blend: 1.2+2.5o   skin_k_weld: 2.0+2.5o   skin_k_lip: 1.0+1.5o
  # base_inflation: 2.0      # 0 отключает весь organic_base_shell слой
```

`skin: implicit` на любой другой поверхности — ValueError. Если implicit-
экспорт невозможен (revolve/sweep-тело, pins/lofts, cylindrical-поля, нет
экзоскелета, не установлен scikit-image) — сборка падает честным
PipelineFailure; молчаливого отката на BRep-STL НЕ существует.

### Порядок сборки SDF = закон (`compiler/implicit/recipe.py`)

```
body hard-union
→ organic_base_shell:            # «выращенность», не декор
    canvas_pad                   # призма над канвасом (окно минус маски),
                                 # base_inflation с falloff→0 к маскам —
                                 # интерфейсы не пухнут
    boss_growth                  # сферы r = head_r+3 вокруг болтовых колонн
    asymmetry_noise              # немного seeded low-freq блобов в safe-канвасе
                                 # (амплитуда мала, клиренс к кипаутам, детерминизм)
→ skin smooth-union (капсулы+узлы, k_blend)
→ smin(body+shell, skin, k_weld) # мышечные сращения
→ smax − window prisms (k_lip)   # губы органических окон
→ HARD CUTS LAST                 # болты (hole_cut_dims — общий источник с BRep),
                                 # зенковки-фрустумы, driver-access цилиндры,
                                 # каналы, box-cuts, неорганические поля — ТОЧНЫЕ
→ keep_in                        # клип по mate/mounting-плоскости
```

Никакой блоб не может сузить функциональное отверстие: hard cuts идут
последними, и это проверяется семплированием АНАЛИТИЧЕСКОГО SDF
(`manufacturing.implicit_skin_fidelity`,
`manufacturing.boss_growth_preserves_fastener_access`,
`manufacturing.skin_assembly_clearance`), а не только меша.

### Честность экспорта

- `part.stl` — производственный выход (marching cubes, watertight,
  байт-детерминированный собственный STL-writer);
- `part.step` — упрощённый BRep-референс; в honesty-репорте это явный
  engine gap: «part.step is the simplified BRep reference; production
  output is part.stl (implicit skin)»;
- `exports.stl_source: implicit|brep` + `exports.skin` (воксели, сетка,
  треугольники, k-параметры);
- **окна-рекессы — явная честность**: `exports.skin.organic_windows =
  {mode, through_cuts, reason}`. На плите окна сквозные (through_cuts:
  true — легально для плиты); на клампе Bio-4M stage 2 окна будут
  РЕКЕССАМИ (защита седла/канала) — пользователь не должен ожидать
  сквозных окон референса и получить сюрприз;
- `quality.rectangularity_reduced` — метрика по НАШИМ массивам меша: доля
  площади треугольников с нормалью в ≤5° от осевых направлений, только по
  skin-канвасу (окно минус маски, над панелью); порог 0.55. На pre-flight
  demo plate — gate чекпойнта, на прочих изделиях — WARN-only до
  накопления опыта;
- `quality.window_shadow_present` — IR-уровень: глубина окна ≥ 2.5 мм,
  иначе честный WARN «мелкая гравировка вместо окна»;
- guards: воксельный бюджет 16M (превышение → авто-огрубление с WARN),
  разрешение ≤ min(min_rib_d/2, min_ligament)/3 (грубее → авто-уточнение);
- `side_profile`-ориентация зеркалит `orient_for_print`; drop-to-bed идёт
  по zmin МЕША — отличается от BRep на «гордую» высоту скина
  (задокументированное отличие).

### Файлы

`compiler/implicit/{sdf,recipe,from_form,mesh,stl,skin}.py`; общий
источник размеров крепежа — `core/fasteners.hole_cut_dims` (BRep-резак
`cad/holes.py` отрефакторен на него, поведение идентично). Stage 1 —
планарная плита (`biomorphic_exoskeleton_demo_plate_implicit.yaml`);
интеграция с profile_surface-маппингом клампа — stage B
(`TODO(bio-4m-integration)` в `from_form._planar_skin_geometry`).
