"""Pack discovery mechanics — determinism, idempotency, collision guard,
the disable flag. Fake packs are injected by monkeypatching discovery."""
from __future__ import annotations

import pytest

from artifact_forge_ng import packs
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS  # shim: populates ops


class _FakeEntryPoint:
    def __init__(self, name, fn):
        self.name = name
        self._fn = fn

    def load(self):
        return self._fn


@pytest.fixture(autouse=True)
def _reset_pack_state(monkeypatch):
    monkeypatch.setattr(packs, "_loaded", None)
    monkeypatch.delenv(packs.DISABLE_ENV, raising=False)
    yield
    packs._loaded = None


def test_no_packs_installed_is_a_noop(monkeypatch):
    monkeypatch.setattr(packs, "_discover", lambda: [])
    assert packs.load_packs() == {}
    assert packs.pack_data_dirs() == []


def test_disable_env_skips_discovery(monkeypatch):
    def boom():
        raise AssertionError("discovery must not run when disabled")
    monkeypatch.setattr(packs, "_discover", boom)
    monkeypatch.setenv(packs.DISABLE_ENV, "1")
    assert packs.load_packs() == {}


def test_load_is_idempotent(monkeypatch):
    calls = []

    def register(ctx):
        calls.append(ctx.pack_id)

    monkeypatch.setattr(packs, "_discover",
                        lambda: [_FakeEntryPoint("demo", register)])
    packs.load_packs()
    packs.load_packs()
    assert calls == ["demo"]


def test_deterministic_order(monkeypatch):
    order = []
    eps = [_FakeEntryPoint(n, lambda ctx, n=n: order.append(n))
           for n in ("zeta", "alpha")]
    monkeypatch.setattr(packs, "_discover",
                        lambda: sorted(eps, key=lambda e: e.name))
    packs.load_packs()
    assert order == ["alpha", "zeta"]


def test_clobbering_existing_op_fails_fast(monkeypatch):
    existing = next(iter(RECIPE_OPS))

    def register(ctx):
        RECIPE_OPS[existing] = "clobbered"

    monkeypatch.setattr(packs, "_discover",
                        lambda: [_FakeEntryPoint("evil", register)])
    original = RECIPE_OPS[existing]
    try:
        with pytest.raises(packs.PackError, match="replaced existing"):
            packs.load_packs()
    finally:
        RECIPE_OPS[existing] = original


def test_declared_override_is_allowed(monkeypatch):
    existing = next(iter(RECIPE_OPS))

    def register(ctx):
        ctx.declare_override(existing)
        RECIPE_OPS[existing] = RECIPE_OPS[existing]  # replace with itself

    monkeypatch.setattr(packs, "_discover",
                        lambda: [_FakeEntryPoint("patch", register)])
    packs.load_packs()  # no PackError


def test_register_crash_is_wrapped(monkeypatch):
    def register(ctx):
        raise ValueError("boom")

    monkeypatch.setattr(packs, "_discover",
                        lambda: [_FakeEntryPoint("broken", register)])
    with pytest.raises(packs.PackError, match="register\\(\\) failed"):
        packs.load_packs()


def test_missing_data_dir_fails(monkeypatch, tmp_path):
    def register(ctx):
        ctx.add_data_dir(tmp_path / "nope")

    monkeypatch.setattr(packs, "_discover",
                        lambda: [_FakeEntryPoint("demo", register)])
    with pytest.raises(packs.PackError, match="does not exist"):
        packs.load_packs()


def test_data_dirs_are_collected(monkeypatch, tmp_path):
    d = tmp_path / "data"
    d.mkdir()

    def register(ctx):
        ctx.add_data_dir(d)

    monkeypatch.setattr(packs, "_discover",
                        lambda: [_FakeEntryPoint("demo", register)])
    assert packs.pack_data_dirs() == [("demo", d)]
