# Discrete Element Analysis

{% hint style="warning" %}
**To do:** one-paragraph introduction to discrete element (block) models of masonry: rigid blocks, contacts between them, and equilibrium at the contacts. Keep it at the level of the RhinoVAULT TNA page and link out for depth.
{% endhint %}

## Solvers

COMPAS Masonry gives access to four solvers. They differ in what they compute and in what a problem may contain.
How each is configured in Rhino is described in [2c. Solver](../manual/2-problem/solver.md).

| Solver | Package | Computes | Problem may contain |
| --- | --- | --- | --- |
| RBE (rigid block equilibrium) | [compas_cra](https://blockresearchgroup.github.io/compas_cra/reference/compas_cra.equilibrium/) | contact forces, no displacements | self-weight only |
| CRA (coupled rigid-block analysis) | [compas_cra](https://blockresearchgroup.github.io/compas_cra/reference/compas_cra.equilibrium/) | contact forces, no displacements | self-weight only |
| LMGC90 (non-smooth contact dynamics) | [compas_lmgc90](https://github.com/BlockResearchGroup/compas_lmgc90) + [LMGC90](https://lmgc90.pages-git-xen.lmgc.univ-montp2.fr/lmgc90_dev/) | displacements and contact forces | loads and prescribed displacements |
| 3DEC (distinct element method) | [compas_3dec](https://github.com/BlockResearchGroup/compas_3dec) + [Itasca 3DEC](https://www.itascacg.com/software/3dec) | displacements and contact forces | loads and prescribed displacements, solved as stages |

{% hint style="warning" %}
**To do:** confirm the 'Computes' column for 3DEC, and add a one-line 'when to use it' per solver.
{% endhint %}

## References

1. Kao, G. T. C., Iannuzzo, A., Thomaszewski, B., Coros, S., Van Mele, T., & Block, P. (2022). Coupled Rigid-Block Analysis: Stability-Aware Design of Complex Discrete-Element Assemblies. *Computer-Aided Design*, 103216. [link](https://www.sciencedirect.com/science/article/pii/S0010448522000161)
2. Kao, G. T. C., Iannuzzo, A., Coros, S., Van Mele, T., & Block, P. (2021). Understanding the rigid-block equilibrium method by way of mathematical programming. *Proceedings of the Institution of Civil Engineers - Engineering and Computational Mechanics*, 174(4), 178-192. [link](https://www.icevirtuallibrary.com/doi/abs/10.1680/jencm.20.00036)

{% hint style="info" %}
**Under the hood** — the data model and the solver interfaces are documented in compas_dem: [models](https://blockresearchgroup.github.io/compas_dem/latest/api/compas_dem.models.html), [problem](https://blockresearchgroup.github.io/compas_dem/latest/api/compas_dem.problem.html), [analysis](https://blockresearchgroup.github.io/compas_dem/latest/api/compas_dem.analysis.html), and the [compas_dem tutorial](https://blockresearchgroup.github.io/compas_dem/latest/tutorial.html).
{% endhint %}
