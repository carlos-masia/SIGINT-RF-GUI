"""
GUI-side bridge to the SMW200A VSG driver in the device repository.

Loads the real implementation from:
  …/iceye/SIGINT-RF-DEVICE-VSG_SMW200A/SIGINT-RF-DEVICE-VSG_SMW200A/vsg_smw200a.py

Import from the GUI project:

    from vsg_bridge import VsgSmw200a, is_rs_smw_installed

You do not need to modify sys.path in main.py if this module is imported first.

CLI smoke test (no arguments; uses ``vsg_config.yaml`` and ``SMW_*`` env vars; delegates to the device ``__main__``):

    python vsg_bridge.py
"""

from __future__ import annotations

import importlib.util
import runpy
from pathlib import Path


def _device_vsg_path() -> Path:
    # …/iceye/SIGINT-RF-GUI/SIGINT-RF-GUI/this_file.py -> iceye/
    iceye = Path(__file__).resolve().parent.parent.parent
    return (
        iceye
        / "SIGINT-RF-DEVICE-VSG_SMW200A"
        / "SIGINT-RF-DEVICE-VSG_SMW200A"
        / "vsg_smw200a.py"
    )


def _load_impl():
    path = _device_vsg_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"Instrument module not found:\n  {path}\n"
            "SMW200A communication code should live under SIGINT-RF-DEVICE-VSG_SMW200A."
        )
    name = "_sigint_vsg_smw200a_device_impl"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not build import spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_impl = _load_impl()

VsgSmw200a = _impl.VsgSmw200a
is_rs_smw_installed = _impl.is_rs_smw_installed
build_visa_resource = _impl.build_visa_resource
default_visa_from_env = _impl.default_visa_from_env
DEFAULT_SMW_IP = _impl.DEFAULT_SMW_IP
DEFAULT_SOCKET_PORT = _impl.DEFAULT_SOCKET_PORT
DEFAULT_TRANSPORT = _impl.DEFAULT_TRANSPORT
Transport = _impl.Transport
default_transport = _impl.default_transport
default_socket_port = _impl.default_socket_port
default_smw_ip = _impl.default_smw_ip
default_visa_from_config = _impl.default_visa_from_config
config_file_path = _impl.config_file_path
clear_vsg_config_cache = _impl.clear_vsg_config_cache
VSG_CONFIG_FILENAME = _impl.VSG_CONFIG_FILENAME

__all__ = (
    "VsgSmw200a",
    "is_rs_smw_installed",
    "build_visa_resource",
    "default_visa_from_env",
    "default_visa_from_config",
    "default_transport",
    "default_socket_port",
    "default_smw_ip",
    "DEFAULT_SMW_IP",
    "DEFAULT_SOCKET_PORT",
    "DEFAULT_TRANSPORT",
    "Transport",
    "config_file_path",
    "clear_vsg_config_cache",
    "VSG_CONFIG_FILENAME",
)


if __name__ == "__main__":
    runpy.run_path(str(_device_vsg_path()), run_name="__main__")
