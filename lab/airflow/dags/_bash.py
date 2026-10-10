import json
import logging
import subprocess
from collections.abc import Callable


def _log_line(logger: logging.Logger, log: dict) -> None:
    level = log.get("info", {}).get("level", "info")
    msg = log.get("info", {}).get("msg")

    if level == "debug":
        logger.debug(msg)
    elif level == "warn":
        logger.warning(msg)
    elif level == "error":
        logger.error(msg)
    else:
        logger.info(msg)


def execute_bash_cmd(cmd: str, stdout_func: Callable | None = None) -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.info(cmd)

    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for line in process.stdout:
        line = line.strip()
        if not line:
            continue

        try:
            log = json.loads(line)
        except json.JSONDecodeError:
            logger.info(line)
            continue

        _log_line(logger, log)

        if stdout_func:
            stdout_func(log)

    process.wait()

    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)
