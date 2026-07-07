"""Implicit SDF exoskeleton skin engine (Bio-4M, docs/BIOMORPHIC.md).

STL-first organic geometry: the Form IR is compiled into an analytic
signed-distance recipe (``recipe.py``), evaluated on a voxel grid
(``mesh.py``), meshed with marching cubes and written as a byte-
deterministic binary STL (``stl.py``). ``skin.py`` orchestrates the
export and emits the honesty findings.

numpy + lazy scikit-image only — importing this package never loads
cadquery (it lives beside, not inside, the BRep compiler).

Truth sources (docs/BIOMORPHIC.md): BRep path remains source of exact
mechanical truth (STEP). Implicit mesh path is source of organic printable
appearance (STL).
"""
