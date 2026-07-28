class ErreurPaie(Exception):
    pass


class ErreurCalcul(ErreurPaie):
    pass


class ErreurPeriodeInvalide(ErreurPaie):
    pass


class ErreurEmployeNonTrouve(ErreurPaie):
    pass


class ErreurContratInvalide(ErreurPaie):
    pass


class ErreurBulletinVerrouille(ErreurPaie):
    pass


class ConfigurationPaieInvalide(ErreurPaie):
    pass
