"""Form IR -> solids/wires/STL/STEP. The only layer that loads the CAD
kernel; core pipelines import it lazily so ``import artifact_forge_ng``
stays cadquery-free. Includes the implicit/SDF skin sub-package."""
