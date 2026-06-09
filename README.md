# SIGINT-RF-GUI

Desktop **GUI** workspace for SIGINT RF applications. Instrument drivers and waveform logic stay in the sibling **device** repository so this tree can focus on UI and orchestration.

## Relationship to `SIGINT-RF-DEVICE-VSG_SMW200A`

The SMW200A **RsSmw wrapper** and ARB tooling live next door:

`../SIGINT-RF-DEVICE-VSG_SMW200A`

Keep both repos under the same parent folder (for example `iceye/SIGINT-RF-GUI` and `iceye/SIGINT-RF-DEVICE-VSG_SMW200A`). `vsg_bridge.py` resolves that path at import time and loads:

`../SIGINT-RF-DEVICE-VSG_SMW200A/SIGINT-RF-DEVICE-VSG_SMW200A/vsg_smw200a.py`

## `vsg_bridge.py`

`SIGINT-RF-GUI/SIGINT-RF-GUI/vsg_bridge.py` is **not** a second copy of the driver. It re-exports the device API so the GUI does not need manual `sys.path` edits.

```python
from vsg_bridge import VsgSmw200a, is_rs_smw_installed
```

Quick hardware check (runs the device module’s CLI; uses `vsg_config.yaml` in the device folder and `SMW_*` env overrides — see device README):

```powershell
cd SIGINT-RF-GUI\SIGINT-RF-GUI
python vsg_bridge.py
```

## Requirements

- **Python** ≥ 3.10 (align with the device project).
- **RsSmw**, **PyYAML**, and a **VISA** stack on the PC when using `VsgSmw200a` (YAML loads `../SIGINT-RF-DEVICE-VSG_SMW200A/.../vsg_config.yaml`).

```powershell
cd SIGINT-RF-GUI\SIGINT-RF-GUI
pip install -r requirements.txt
```

You can instead install the device project in editable mode (pulls the same dependencies and documents the full toolset):

```powershell
pip install -e ..\SIGINT-RF-DEVICE-VSG_SMW200A
```

## Layout

```
SIGINT-RF-GUI/
  pyproject.toml
  README.md                    # this file
  SIGINT-RF-GUI/
    vsg_bridge.py              # bridge to device vsg_smw200a.py (reads device vsg_config.yaml)
    requirements.txt
```

Add new UI entrypoints and packages under `SIGINT-RF-GUI/SIGINT-RF-GUI/` (or introduce a `src/` layout when the application grows).

## Further reading

See **`../SIGINT-RF-DEVICE-VSG_SMW200A/README.md`** for ARB catalog usage (`smw200a_arb_signals.py`), the SCPI/TCP tool (`rs_smw_fsw_tcp.py`), and `rs_scpi_tcp` expectations.

## License

MIT (see `pyproject.toml` if specified).
