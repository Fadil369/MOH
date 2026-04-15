import structlog
import logging
from typing import Any, MutableMapping


def phi_masking_processor(logger, method, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    phi_fields = {"patient_id", "name", "dob", "nric", "national_id"}
    for field in phi_fields:
        if field in event_dict:
            val = str(event_dict[field])
            if field == "patient_id" and len(val) >= 4:
                event_dict[field] = f"***-XX-{val[-4:].upper()}"
            else:
                event_dict[field] = "***REDACTED***"
    return event_dict


def configure_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            phi_masking_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__):
    configure_logging()
    return structlog.get_logger(name)
