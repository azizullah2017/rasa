import asyncio
import copy
import logging
import os
import shutil
import warnings
from pathlib import Path
from types import TracebackType
from typing import (
    Any,
    Coroutine,
    Dict,
    List,
    Optional,
    Text,
    Type,
    TypeVar,
    Union,
    ContextManager,
    Set,
)

from socket import SOCK_DGRAM, SOCK_STREAM
import numpy as np
import rasa.utils.io
from rasa.constants import (
    DEFAULT_LOG_LEVEL_LIBRARIES,
    ENV_LOG_LEVEL_LIBRARIES,
    ENV_LOG_LEVEL_MATPLOTLIB,
    ENV_LOG_LEVEL_RABBITMQ,
    ENV_LOG_LEVEL_KAFKA,
)
from rasa.shared.constants import DEFAULT_LOG_LEVEL, ENV_LOG_LEVEL, TCP_PROTOCOL
import rasa.shared.utils.io

logger = logging.getLogger(__name__)

T = TypeVar("T")

EXPECTED_WARNINGS = [
    # TODO (issue #9932)
    (
        np.VisibleDeprecationWarning,
        "Creating an ndarray from ragged nested sequences.*",
    ),
    # cf. https://github.com/tensorflow/tensorflow/issues/38168
    (
        UserWarning,
        "Converting sparse IndexedSlices.* to a dense Tensor of unknown "
        "shape. This may consume a large amount of memory.",
    ),
    (UserWarning, "Slot auto-fill has been removed in 3.0 .*",),
]


class TempDirectoryPath(str, ContextManager):
    """Represents a path to an temporary directory.

    When used as a context manager, it erases the contents of the directory on exit.
    """

    def __enter__(self) -> "TempDirectoryPath":
        return self

    def __exit__(
        self,
        _exc: Optional[Type[BaseException]],
        _value: Optional[Exception],
        _tb: Optional[TracebackType],
    ) -> None:
        if os.path.exists(self):
            shutil.rmtree(self)


def read_global_config(path: Text) -> Dict[Text, Any]:
    """Read global Rasa configuration.

    Args:
        path: Path to the configuration
    Returns:
        The global configuration
    """
    # noinspection PyBroadException
    try:
        return rasa.shared.utils.io.read_config_file(path)
    except Exception:
        # if things go south we pretend there is no config
        return {}


def configure_logging_and_warnings(
    log_level: Optional[int] = None,
    warn_only_once: bool = True,
    filter_repeated_logs: bool = True,
) -> None:
    """Sets log levels of various loggers and sets up filters for warnings and logs.

    Args:
        log_level: The log level to be used for the 'Rasa' logger. Pass `None` to use
            either the environment variable 'LOG_LEVEL' if it is specified, or the
            default log level otherwise.
        warn_only_once: determines whether user warnings should be filtered by the
            `warnings` module to appear only "once"
        filter_repeated_logs: determines whether `RepeatedLogFilter`s are added to
            the handlers of the root logger
    """
    if log_level is None:  # Log level NOTSET is 0 so we use `is None` here
        log_level = os.environ.get(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL)
        # Change log level from str to int (note that log_level in function parameter
        # int already, coming from CLI argparse parameter).
        log_level = logging.getLevelName(log_level)

    logging.getLogger("rasa").setLevel(log_level)
    # Assign log level to env variable in str format (not int). Why do we assign?
    os.environ[ENV_LOG_LEVEL] = logging.getLevelName(log_level)

    configure_library_logging()

    if filter_repeated_logs:
        for handler in logging.getLogger().handlers:
            handler.addFilter(RepeatedLogFilter())

    _filter_warnings(log_level=log_level, warn_only_once=warn_only_once)


def _filter_warnings(log_level: Optional[int], warn_only_once: bool = True) -> None:
    """Sets up filters for warnings.

    Args:
        log_level: the current log level. Certain warnings will only be filtered out
            if we're not in debug mode.
        warn_only_once: determines whether user warnings should be filtered by the
            `warnings` module to appear only "once"
    """
    if warn_only_once:
        warnings.filterwarnings("once", category=UserWarning)
    if log_level and log_level > logging.DEBUG:
        for warning_type, warning_message in EXPECTED_WARNINGS:
            warnings.filterwarnings(
                "ignore", message=f".*{warning_message}", category=warning_type
            )


def configure_library_logging() -> None:
    """Configures log levels of used libraries such as kafka, matplotlib, pika."""
    library_log_level = os.environ.get(
        ENV_LOG_LEVEL_LIBRARIES, DEFAULT_LOG_LEVEL_LIBRARIES,
    )
    update_tensorflow_log_level()
    update_asyncio_log_level()
    update_apscheduler_log_level()
    update_socketio_log_level()
    update_matplotlib_log_level(library_log_level)
    update_kafka_log_level(library_log_level)
    update_rabbitmq_log_level(library_log_level)


def update_apscheduler_log_level() -> None:
    """Configures the log level of `apscheduler.*` loggers."""
    log_level = os.environ.get(ENV_LOG_LEVEL_LIBRARIES, DEFAULT_LOG_LEVEL_LIBRARIES)

    apscheduler_loggers = [
        "apscheduler",
        "apscheduler.scheduler",
        "apscheduler.executors",
        "apscheduler.executors.default",
    ]

    for logger_name in apscheduler_loggers:
        logging.getLogger(logger_name).setLevel(log_level)
        logging.getLogger(logger_name).propagate = False


def update_socketio_log_level() -> None:
    """Set the log level of socketio."""
    log_level = os.environ.get(ENV_LOG_LEVEL_LIBRARIES, DEFAULT_LOG_LEVEL_LIBRARIES)

    socketio_loggers = ["websockets.protocol", "engineio.server", "socketio.server"]

    for logger_name in socketio_loggers:
        logging.getLogger(logger_name).setLevel(log_level)
        logging.getLogger(logger_name).propagate = False


def update_tensorflow_log_level() -> None:
    """Sets Tensorflow log level based on env variable 'LOG_LEVEL_LIBRARIES'."""
    # Disables libvinfer, tensorRT, cuda, AVX2 and FMA warnings (CPU support).
    # This variable needs to be set before the
    # first import since some warnings are raised on the first import.
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

    log_level = os.environ.get(ENV_LOG_LEVEL_LIBRARIES, DEFAULT_LOG_LEVEL_LIBRARIES)

    if not log_level:
        log_level = "ERROR"

    logging.getLogger("tensorflow").setLevel(log_level)
    logging.getLogger("tensorflow").propagate = False


def update_sanic_log_level(
    log_file: Optional[Text] = None,
    use_syslog: Optional[bool] = False,
    syslog_address: Optional[Text] = None,
    syslog_port: Optional[int] = None,
    syslog_protocol: Optional[Text] = None,
) -> None:
    """Set the log level to 'LOG_LEVEL_LIBRARIES' environment variable ."""
    from sanic.log import logger, error_logger, access_logger

    log_level = os.environ.get(ENV_LOG_LEVEL_LIBRARIES, DEFAULT_LOG_LEVEL_LIBRARIES)

    logger.setLevel(log_level)
    error_logger.setLevel(log_level)
    access_logger.setLevel(log_level)

    logger.propagate = False
    error_logger.propagate = False
    access_logger.propagate = False

    if log_file is not None:
        formatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        error_logger.addHandler(file_handler)
        access_logger.addHandler(file_handler)
    if use_syslog:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)-5.5s] [%(process)d]" " %(message)s"
        )
        socktype = SOCK_STREAM if syslog_protocol == TCP_PROTOCOL else SOCK_DGRAM
        syslog_handler = logging.handlers.SysLogHandler(
            address=(syslog_address, syslog_port), socktype=socktype,
        )
        syslog_handler.setFormatter(formatter)
        logger.addHandler(syslog_handler)
        error_logger.addHandler(syslog_handler)
        access_logger.addHandler(syslog_handler)


def update_asyncio_log_level() -> None:
    """Set the log level of asyncio to the log level.

    Uses the log level specified in the environment variable 'LOG_LEVEL_LIBRARIES'.
    """
    log_level = os.environ.get(ENV_LOG_LEVEL_LIBRARIES, DEFAULT_LOG_LEVEL_LIBRARIES)
    logging.getLogger("asyncio").setLevel(log_level)


def update_matplotlib_log_level(library_log_level: Text) -> None:
    """Set the log level of matplotlib.

    Uses the library specific log level or the general libraries log level.
    """
    log_level = os.environ.get(ENV_LOG_LEVEL_MATPLOTLIB, library_log_level)
    logging.getLogger("matplotlib").setLevel(log_level)


def update_kafka_log_level(library_log_level: Text) -> None:
    """Set the log level of kafka.

    Uses the library specific log level or the general libraries log level.
    """
    log_level = os.environ.get(ENV_LOG_LEVEL_KAFKA, library_log_level)
    logging.getLogger("kafka").setLevel(log_level)


def update_rabbitmq_log_level(library_log_level: Text) -> None:
    """Set the log level of pika.

    Uses the library specific log level or the general libraries log level.
    """
    log_level = os.environ.get(ENV_LOG_LEVEL_RABBITMQ, library_log_level)
    logging.getLogger("aio_pika").setLevel(log_level)
    logging.getLogger("aiormq").setLevel(log_level)


def sort_list_of_dicts_by_first_key(dicts: List[Dict]) -> List[Dict]:
    """Sorts a list of dictionaries by their first key."""
    return sorted(dicts, key=lambda d: list(d.keys())[0])


def write_global_config_value(name: Text, value: Any) -> bool:
    """Read global Rasa configuration.

    Args:
        name: Name of the configuration key
        value: Value the configuration key should be set to

    Returns:
        `True` if the operation was successful.
    """
    # need to use `rasa.constants.GLOBAL_USER_CONFIG_PATH` to allow patching
    # in tests
    config_path = rasa.constants.GLOBAL_USER_CONFIG_PATH
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        c = read_global_config(config_path)
        c[name] = value
        rasa.shared.utils.io.write_yaml(c, rasa.constants.GLOBAL_USER_CONFIG_PATH)
        return True
    except Exception as e:
        logger.warning(f"Failed to write global config. Error: {e}. Skipping.")
        return False


def read_global_config_value(name: Text, unavailable_ok: bool = True) -> Any:
    """Read a value from the global Rasa configuration."""

    def not_found() -> None:
        if unavailable_ok:
            return None
        else:
            raise ValueError(f"Configuration '{name}' key not found.")

    # need to use `rasa.constants.GLOBAL_USER_CONFIG_PATH` to allow patching
    # in tests
    config_path = rasa.constants.GLOBAL_USER_CONFIG_PATH

    if not os.path.exists(config_path):
        return not_found()

    c = read_global_config(config_path)

    if name in c:
        return c[name]
    else:
        return not_found()


def update_existing_keys(
    original: Dict[Any, Any], updates: Dict[Any, Any]
) -> Dict[Any, Any]:
    """Iterate through all the updates and update a value in the original dictionary.

    If the updates contain a key that is not present in the original dict, it will
    be ignored.
    """
    updated = original.copy()
    for k, v in updates.items():
        if k in updated:
            updated[k] = v
    return updated


def override_defaults(
    defaults: Optional[Dict[Text, Any]], custom: Optional[Dict[Text, Any]]
) -> Dict[Text, Any]:
    """Override default config with the given config.

    We cannot use `dict.update` method because configs contain nested dicts.

    Args:
        defaults: default config
        custom: user config containing new parameters

    Returns:
        updated config
    """
    config = copy.deepcopy(defaults) if defaults else {}

    if not custom:
        return config

    for key in custom.keys():
        if isinstance(config.get(key), dict):
            config[key].update(custom[key])
            continue
        config[key] = custom[key]

    return config


class RepeatedLogFilter(logging.Filter):
    """Filter repeated log records."""

    last_log = None

    def filter(self, record: logging.LogRecord) -> bool:
        """Determines whether current log is different to last log."""
        current_log = (
            record.levelno,
            record.pathname,
            record.lineno,
            record.msg,
            record.args,
        )
        if current_log != self.last_log:
            self.last_log = current_log
            return True
        return False


async def call_potential_coroutine(
    coroutine_or_return_value: Union[Any, Coroutine]
) -> Any:
    """Awaits coroutine or returns value directly if it's not a coroutine.

    Args:
        coroutine_or_return_value: Either the return value of a synchronous function
            call or a coroutine which needs to be await first.

    Returns:
        The return value of the function.
    """
    if asyncio.iscoroutine(coroutine_or_return_value):
        return await coroutine_or_return_value

    return coroutine_or_return_value


def directory_size_in_mb(
    path: Path, filenames_to_exclude: Optional[List[Text]] = None
) -> float:
    """Calculates the size of a directory.

    Args:
        path: The path to the directory.
        filenames_to_exclude: Allows excluding certain files from the calculation.

    Returns:
        Directory size in MiB.
    """
    filenames_to_exclude = filenames_to_exclude or []
    size = 0.0
    for root, _dirs, files in os.walk(path):
        for filename in files:
            if filename in filenames_to_exclude:
                continue
            size += (Path(root) / filename).stat().st_size

    # bytes to MiB
    return size / 1_048_576


def copy_directory(source: Path, destination: Path) -> None:
    """Copies the content of one directory into another.

    Unlike `shutil.copytree` this doesn't raise if `destination` already exists.

    # TODO: Drop this in favor of `shutil.copytree(..., dirs_exist_ok=True)` when
    # dropping Python 3.7.

    Args:
        source: The directory whose contents should be copied to `destination`.
        destination: The directory which should contain the content `source` in the end.

    Raises:
        ValueError: If destination is not empty.
    """
    if not destination.exists():
        destination.mkdir(parents=True)

    if list(destination.glob("*")):
        raise ValueError(
            f"Destination path '{destination}' is not empty. Directories "
            f"can only be copied to empty directories."
        )

    for item in source.glob("*"):
        if item.is_dir():
            shutil.copytree(item, destination / item.name)
        else:
            shutil.copy2(item, destination / item.name)


def find_unavailable_packages(package_names: List[Text]) -> Set[Text]:
    """Tries to import all package names and returns the packages where it failed.

    Args:
        package_names: The package names to import.

    Returns:
        Package names that could not be imported.
    """
    import importlib

    failed_imports = set()
    for package in package_names:
        try:
            importlib.import_module(package)
        except ImportError:
            failed_imports.add(package)

    return failed_imports


def module_path_from_class(clazz: Type) -> Text:
    """Return the module path of an instance's class."""
    return clazz.__module__ + "." + clazz.__name__
