# Charte Zéphyr — design system

> Source de vérité unique : les **design tokens** (variables CSS) dans
> `src/zephyr/web/__init__.py` (constante `_CSS`, bloc `:root`). Aucun composant
> n'écrit de couleur en dur : tout passe par `var(--…)`. Page vivante : `/styleguide`.

## Direction artistique
- **Style** : SaaS épuré (registre Linear/Stripe), sobre et crédible « ingénierie ».
- **Marque** : alignée sur **KORR** (korr.lu) — vert forêt + neutres, Helvetica Neue.
- **Modes** : clair **et** sombre (bascule en nav, persistée en `localStorage`,
  défaut = préférence système ; pas de flash grâce au script d'init dans `<head>`).

## Couleurs (tokens)
| Token | Clair | Rôle |
|---|---|---|
| `--bg` | `#fbfbf6` | fond appli (blanc cassé chaud) |
| `--surface` | `#ffffff` | cartes |
| `--surface-2` | `#f3f4ef` | surfaces 2ndaires, pistes |
| `--ink` | `#141513` | texte principal |
| `--muted` | `#5d6c7b` | texte secondaire (gris froid KORR) |
| `--line` | `#e6e7e1` | bordures |
| `--primary` | `#3a5b42` | **vert KORR** — actions |
| `--primary-strong` | `#2b4632` | hover / pressé |
| `--danger` / `--warn` | `#c0392b` / `#9a6b00` | sémantiques |

Le mode sombre redéfinit ces tokens (`:root[data-theme="dark"]`) — fond `#121212`,
vert éclairci `#84b58c`, etc. Notes A→E : `--a … --e`.

## Typographie
- Famille : `'Helvetica Neue', Helvetica, Arial, sans-serif` (native macOS/iOS,
  repli Arial — métrique proche ; **aucune webfont licenciée à héberger**).
- Titres en `-0.02/-0.04em` de letter-spacing, graisses 600/700.

## Espacements & formes
- Échelle **8pt** : `--s1..--s8` (4/8/12/16/24/32/48/64).
- Rayons : `--r1` 8px, `--r2` 12px, `--r3` 16px, `--pill`.
- Ombres : `--shadow-1` (cartes), `--shadow-2` (survol/pop).
- Focus : anneau `--ring` sur `:focus-visible` (accessibilité clavier).

## Composants
Boutons (`.btn`, `.btn.ghost`, `.btn.sm`), cartes (`.card`), KPI (`.kpi`),
badges (`.badge`, `.badge-ok`), chips (`.chip`), champs (`form input/select`),
toggle segmenté (`.seg`), uploaders (`.uploader`), éditeur (`.trace-layout`,
`.palette`, `.room-card`). Tous documentés et visibles sur `/styleguide`.

## Règle
Toute évolution visuelle se fait **dans les tokens** (un seul endroit), pas en
retouchant les composants un par un. Ne jamais réintroduire de hex en dur.
