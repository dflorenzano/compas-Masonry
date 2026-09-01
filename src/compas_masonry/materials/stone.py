from .material import Material


class Stone(Material):
    """Class representing a generic stone material.

    Parameters
    ----------
    Ecm : float, optional
        Modulus of elasticity in [GPa].
    density : float, optional
        Density of the material in [kg/m3].
        If not provided, 2400 kg/m3 is used.
    poisson : float, optional
        Poisson's ratio.
        If not provided, `poisson = 0.2` is used.
    name : str, optional
        Name of the material.

    Attributes
    ----------
    Ecm : float
        Modulus of elasticity in [Pa].

    """

    @property
    def __data__(self) -> dict:
        data = super().__data__
        data.update(
            {
                "Ecm": self.Ecm,
                "density": self.density,
                "poisson": self.poisson,
                "name": self.name,
            }
        )
        return data

    def __init__(
        self,
        Ecm: float = None,
        density: float = 2400,
        poisson: float = 0.2,
        name: str = None,
    ):
        super().__init__(name=name)

        self.Ecm = Ecm
        self.density = density
        self.poisson = poisson
        self.name = name

    @property
    def rho(self) -> float:
        return self.density

    @property
    def nu(self) -> float:
        return self.poisson

    @property
    def G(self) -> float:
        if self.Ecm:
            return self.Ecm / (2 * (1 + self.nu))
        raise ValueError("Ecm must be defined to compute G")
