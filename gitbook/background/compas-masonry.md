# COMPAS Masonry

{% hint style="warning" %}
**To do:** short history of the plugin (from the COMPAS 1 toolbox to the Rhino 8 plugin), authors and contributors, as on the RhinoVAULT background page. The two sections below are copied unchanged from the 2024 GitBook (`_gitbook/`) and need review: they mention packages and pages that no longer exist.
{% endhint %}

## SNSF Project

In recent years, our (academic/theoretical) understanding of the behaviour of unreinforced masonry (URM) structures has improved significantly, and many advanced technological solutions for conservation have been developed. However, there is still a lack of appropriate methods and tools that can be used for the assessment of URM structures in every day practice.&#x20;

Therefore, since 2018, the Block Research Group has been working on “Practical Stability Assessment Strategies for Vaulted Unreinforced Masonry Structures” with support of the Swiss National Science Foundation (SNSF). The goal of this research project is to create tools suitable for everyday engineering practice and to develop appropriate analysis strategies for diverse contexts and circumstances related to the availability of time, budget and available data.&#x20;

The SNSF research results are made available to the scientific and professional community through **COMPAS Masonry**. COMPAS Masonry represents a unique computational framework as it provides a common data management system and connects different tools and methodologies altogether. Therefore, it allows to look at the same assessment problem from different perspectives and opens up the possibility to explore several mechanical scenarios comparing different methodological solutions. Nonetheless, as an open-source framework, it offers to the industry, academy and practitioners the unique opportunity to collaborate, participate in a positive loop, where everyone can contribute.

It bundles different solvers that are built up over a common data management system, compas\_assembly, that provides a fast, direct and robust way to handle complex geometries both in terms of geometric data structures (via graph network theories) and material properties distributions. The main tools developed were **compas\_rbe**, **compas\_tno**, **compas\_prd**, **compas\_cra**, and **compas\_dem**. More information regarding each different solver can be found in the solvers page.

Beyond the computational developement and implementations of the different masonry solvers, the theoretical foundation developed during the project has been communicated though an extensive list of peer-reviewed and journal publications which are listed here.&#x20;

Additionally, the researchers of the project have participated in workshops and given presentations which are also available through the respective pages.

## Publications

A list with the publications originated from the COMPAS Masonry project is available below. By following the specfied links the publications can be downloaded.

### Publications

1. Kao, G. T. C., Iannuzzo, A., Thomaszewski, B., Coros, S., Van Mele, T., & Block, P. (2022). Coupled Rigid-Block Analysis: Stability-Aware Design of Complex Discrete-Element Assemblies. Computer-Aided Design, 103216. \[[link](https://www.sciencedirect.com/science/article/pii/S0010448522000161)]
2. Maia Avelino, R., Van Mele, T., & Block P. (2022) Advances in Thrust Network Analysis: Constrained equilibrium assessment of masonry vaulted structures.Collection of papers - Edoardo Benvenuto Prize Fondazione Franzoni ETS. To be published.
3. Maia Avelino, R., Lee, J., Van Mele, T., & Block, P. (2021). An interactive implementation of algebraic graphic statics for geometry-based teaching and design of structures. In Proceedings of the International fib Symposium on the Conceptual Design of Structures (pp. 447-454). \[[link](https://www.block.arch.ethz.ch/brg/publications/1110)]
4. Maia Avelino, R. M., Iannuzzo, A., Van Mele, T., & Block, P. (2021). Assessing the safety of vaulted masonry structures using thrust network analysis. Computers & Structures, 257, 106647.  \[[link](https://www.sciencedirect.com/science/article/pii/S0045794921001693)]
5. COMPAS Masonry: [https://blockresearchgroup.gitbook.io/compas-masonry/ ](https://blockresearchgroup.gitbook.io/compas-masonry/)
6. Iannuzzo, A., Dell’Endice, A., Maia Avelino, R., Kao, G. T. C., Van Mele, T., & Block, P. (2021). COMPAS masonry: a computational framework for practical assessment of unreinforced masonry structures. In Proceedings of the SAHC Symposium. \[[link](https://www.block.arch.ethz.ch/brg/publications/1001)]
7. Iannuzzo, A., Mele, T. V., & Block, P. (2021). Stability and load-bearing capacity assessment of a deformed multi-span masonry bridge using the PRD method. International Journal of Masonry Research and Innovation, 6(4), 422-445. \[[link](https://www.inderscienceonline.com/doi/abs/10.1504/IJMRI.2021.118842)]
8. Dell’Endice, A., Iannuzzo, A., Van Mele, T., & Block, P. (2021). Influence of settlements and geometrical imperfections on the internal stress state of masonry structures. In Proceedings of the SAHC symposium. \[[link](https://www.block.arch.ethz.ch/brg/publications/1030)]
9. Maia Avelino, R., Iannuzzo, A., Van Mele, T., & Block, P. (2021). New strategies to assess the safety of unreinforced masonry structures using thrust network analysis. In 12th International Conference on Structural Analysis of Historical Constructions (SAHC) (pp. 2124-2135). International Centre for Numerical Methods in Engineering (CIMNE). \[[link](https://www.block.arch.ethz.ch/brg/publications/1000)]
10. Kao, G. T. C., Iannuzzo, A., Coros, S., Van Mele, T., & Block, P. (2021). Understanding the rigid-block equilibrium method by way of mathematical programming. Proceedings of the Institution of Civil Engineers-Engineering and Computational Mechanics, 174(4), 178-192. \[[link](https://www.icevirtuallibrary.com/doi/abs/10.1680/jencm.20.00036)]
11. Maia Avelino, R., Iannuzzo, A., Van Mele, T., & Block, P. (2021). Parametric stability analysis of groin vaults. Applied Sciences, 11(8), 3560. \[[link](https://doi.org/10.3390/app11083560)]
12. Iannuzzo, A., Dell'Endice, A., Van Mele, T., & Block, P. (2021). Numerical limit analysis-based modelling of masonry structures subjected to large displacements. Computers & Structures, 242, 106372. \[[link](https://www.sciencedirect.com/science/article/pii/S0045794920301759)]
13. Dell'Endice, A., Iannuzzo, A., DeJong, M. J., Van Mele, T., & Block, P. (2021). Modelling imperfections in unreinforced masonry structures: Discrete Element simulations and scale model experiments of a pavilion vault. Engineering Structures, 228, 111499. \[[link](https://doi.org/10.1016/j.engstruct.2020.111499)]
14. Iannuzzo, A., Van Mele, T., & Block, P. (2020). Piecewise rigid displacement (PRD) method: a limit analysis-based approach to detect mechanisms and internal forces through two dual energy criteria. Mechanics Research Communications, 107, 103557. \[[link](https://doi.org/10.1016/j.mechrescom.2020.103557)]

Papers in preparation or submitted for review:&#x20;

1. Dell’Endice A., DeJong M.J., Van Mele T., & Block P., Structural Analysis of Unreinforced Masonry Spiral Staircases using Discrete Element Modelling. _Submitted for review_&#x20;
2. Fugger R, Maia Avelino R, Iannuzzo A, de Felice G., & Block P. A new numerical limit analysis-based strategy to retrofit masonry curved structures with FRCM systems. _Submitted for review_ - ECCOMAS2022 Conference&#x20;
3. Maia Avelino, R., Iannuzzo, A., Van Mele, T., & Block, P. (2022). An energy-based strategy to find internal stress states compatible with general boundary displacements in masonry structures. _In preparation_
