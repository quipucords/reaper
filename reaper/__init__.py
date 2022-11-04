"""Package for reaping the clouds."""

import logging.config

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s | %(levelname)s | %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "": {"handlers": ["console"], "level": "INFO"},
        "reaper": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "azure": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
logging.config.dictConfig(LOGGING)
