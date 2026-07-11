# Security policy

## Supported versions

The `main` branch. There are no maintained release branches yet.

## Reporting a vulnerability

Please email **pinepico8@gmail.com** with a description and reproduction
steps. Do not open a public issue for anything you believe is
exploitable. You should get an initial response within a few days.

## Scope notes

- The engine evaluates YAML with `yaml.safe_load` and expressions in a
  sandboxed AST evaluator (`core/expr`); anything that escapes either is
  in scope and very much of interest.
- The web cockpit (`forge ui`) is a **local development tool** bound to
  localhost; it is not hardened for exposure to untrusted networks, and
  running it on a public interface is out of scope.
- API keys (optional, LLM intent translation only) are read from the
  environment or a local `.env`; the engine never sends your geometry
  anywhere unless you enable that feature.
