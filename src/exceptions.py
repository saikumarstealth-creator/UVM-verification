"""
Custom exceptions for UVM TB Generator with structured error codes.
Industry-standard error taxonomy.
"""

from __future__ import annotations


class UVMGenError(Exception):
    """Base exception for all UVM TB Generator errors."""
    code: str = "UNKNOWN_ERROR"
    status_code: int = 500
    details: str = ""

    def __init__(self, message: str = "", details: str = "", status_code: int | None = None):
        self.message = message or self.__doc__ or str(self.code)
        self.details = details
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
            "status_code": self.status_code,
        }


class SpecNotFoundError(UVMGenError):
    code = "SPEC_NOT_FOUND"
    status_code = 404


class SpecValidationError(UVMGenError):
    code = "SPEC_VALIDATION_FAILED"
    status_code = 422


class SpecParseError(UVMGenError):
    code = "SPEC_PARSE_ERROR"
    status_code = 422


class PipelineRunError(UVMGenError):
    code = "PIPELINE_RUN_FAILED"
    status_code = 500


class ModelNotTrainedError(UVMGenError):
    code = "MODEL_NOT_TRAINED"
    status_code = 400


class GenerationError(UVMGenError):
    code = "GENERATION_FAILED"
    status_code = 500


class SimulationError(UVMGenError):
    code = "SIMULATION_FAILED"
    status_code = 500


class SimulatorNotFoundError(UVMGenError):
    code = "SIMULATOR_NOT_FOUND"
    status_code = 400


class RegistryError(UVMGenError):
    code = "REGISTRY_ERROR"
    status_code = 500


class ConfigurationError(UVMGenError):
    code = "CONFIGURATION_ERROR"
    status_code = 400


class ProtocolNotSupportedError(UVMGenError):
    code = "PROTOCOL_NOT_SUPPORTED"
    status_code = 400
    details = "Supported protocols: uart, spi, i2c, axi4lite, apb, wishbone"
