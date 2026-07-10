# Доменные планы Artifact Forge

Развёртка «Future Domains to Watch» из [ECOSYSTEM.md](../ECOSYSTEM.md):
каждый недоохваченный домен — собственный план в подпапке. Домены НЕ
становятся режимами (правило пяти осей: **новый рынок ≠ новый mode;
новый валидаторный контракт = новый mode**) — это packs/domains поверх
существующих режимов и environment-профилей.

Принципы всех планов:

1. **Пять осей**: mode = проверка; pack = упаковка; environment =
   условия; style = внешний язык; tier = free/certified/pro.
2. **Printables-тест**: платно только то, что сложно повторить обычным
   STL (families, системы, отчёты, workflow).
3. **Honest claims**: каждый план фиксирует, каких заявлений домен НЕ
   делает.
4. **Канон волн**: первая волна каждого домена обязана иметь именованный
   golden-артефакт; фича без validator-backed геометрии = галлюцинация.
5. **Карта реюза честная**: план ссылается только на существующие
   ops/архетипы/интерфейсы; отсутствующие building blocks помечены ⬜.

Общие capability-gaps доменов централизованы в
[CAPABILITIES.md](CAPABILITIES.md) — матрица «gap → домены-клиенты →
owner wave»; домен не реализует общий блок локально, он его клиент.

**Статус доменных волн** в таблице = реализованы ли СОБСТВЕННЫЕ
waves/goldens домена. Не путать с ✅ внутри PLAN.md — там это уже
существующие building blocks движка, которые домен реюзает.

| Домен | Slug | Scope одной строкой | Приоритет | Статус доменных волн |
|---|---|---|---|---|
| Repair / Spare Parts | [repair](repair/PLAN.md) | right-to-repair: ручки, защёлки, адаптеры, fit-шаблоны | **P1** | ⬜ |
| Jigs / Fixtures | [jigs](jigs/PLAN.md) | production aids: кондукторы, упоры, калибры, B2B-отчёты | **P1** | ⬜ |
| Music / Studio | [studio](studio/PLAN.md) | creator-витрина: маунты, кабель-менеджмент, стенды | **P1** | ⬜ |
| Electronics / IoT | [electronics](electronics/PLAN.md) | корпуса плат, sensor mounts, DIN/гланды | P2 | ⬜ |
| Mobility / Bike / Vehicle | [mobility](mobility/PLAN.md) | руль/салон/кемпер-аксессуары с env-гейтами | P2 | ⬜ |
| Education / FabLab | [education](education/PLAN.md) | учебные наборы, printable validators demo | P2 | ⬜ |
| Accessibility / Adaptive | [accessibility](accessibility/PLAN.md) | daily-living grips/aids, no medical claims | P3 | ⬜ |
| Craft / Mold / Ceramics | [craft](craft/PLAN.md) | параметрические формы: draft, усадка, ключи | P3 | ⬜ |
| Pet / Aquarium / Terrarium | [pet](pet/PLAN.md) | wet/humid крепёж и системы с toxicity-warnings | P3 | ⬜ |
| Medical / Dental | [medical](medical/EXCLUDED.md) | **explicitly excluded** до внешнего certification path | — | ⛔ |

Приоритет P1 — дешёвая витрина и быстрый B2B: repair и jigs почти
целиком собираются из готовых ops, studio — из готовых архетипов
пресетами.

Единый шаблон PLAN.md: 1 Scope и позиционирование · 2 Mode/Env/Tier ·
3 Что уже есть в движке (+ gaps ⬜) · 4 Волны с golden-артефактом ·
5 Интерфейсы и стандарты домена · 6 Валидаторы-кандидаты · 7 Free/Pro
граница · 8 Риски и claims · 9 Связи с линиями A/E/M/P/VF/PK/CP.
