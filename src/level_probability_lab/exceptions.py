class LabError(Exception):
    """Base error for Level Probability Lab."""


class ConfigError(LabError):
    pass


class ValidationError(LabError):
    pass


class MissingCredentialsError(LabError):
    pass


class DownloadBlocked(LabError):
    pass


class CostCapExceeded(LabError):
    pass


class UncertainChargeError(LabError):
    pass


class EnvironmentMismatch(LabError):
    pass


class ForecastLocked(LabError):
    pass


class SessionBoundaryError(LabError):
    pass
