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
