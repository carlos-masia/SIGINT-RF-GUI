# SIGINT-RF-GUI

**Shiny** web UI for the SMW200A **ARB catalog** workflow (same idea as `smw200a_arb_signals.py --gui` in the device repo). Instrument code, `rs_scpi_tcp`, and the Tk smoke test live in **`SIGINT-RF-DEVICE-VSG_SMW200A`** — this repo only ships `vsg_gui.py` plus packaging.

## What lives where

| Piece | Location |
|-------|----------|
| Shiny app | `SIGINT-RF-GUI/SIGINT-RF-GUI/vsg_gui.py` → console script **`sigint-rf-gui-shiny`** |
| `VsgSmw200a`, `smw200a_arb_signals`, `rs_scpi_tcp`, minimal Tk VISA smoke | **`SIGINT-RF-DEVICE-VSG_SMW200A`** (installed as a dependency from git, or clone sibling under `iceye/`) |

Expected layout when running from a checkout (no editable device install):

```text
iceye/
  SIGINT-RF-GUI/
  SIGINT-RF-DEVICE-VSG_SMW200A/
    SIGINT-RF-DEVICE-VSG_SMW200A/
      smw200a_arb_signals.py
      vsg_smw200a.py
      rs_scpi_tcp.py
      vsg_config.yaml
```

`vsg_gui.py` resolves `iceye/` from the script path and loads the ARB module from that sibling folder. **`import rs_scpi_tcp`** uses the device copy (includes `smw_query_idn` for **Test SMW**).

## Tk: minimal VISA / `*IDN?` window

Use the **device** package entry point (not this repo):

```powershell
pip install -e path/to/SIGINT-RF-DEVICE-VSG_SMW200A
sigint-rf-vsg-tk
```

That runs `vsg_tk_smoke.py` next to `vsg_smw200a.py` (`from vsg_smw200a import VsgSmw200a`, …).

## Run the Shiny GUI

From the **SIGINT-RF-GUI** repo root:

```powershell
cd SIGINT-RF-GUI
pip install -e .
sigint-rf-gui-shiny
```

Or from the `iceye` root:

```powershell
python -m shiny run --reload SIGINT-RF-GUI/SIGINT-RF-GUI/vsg_gui.py:app
```

## Requirements

See `pyproject.toml`: Python **≥ 3.14.5**, **Shiny**, **RsSmw**, **PyYAML**, and the **SIGINT-RF-DEVICE-VSG_SMW200A** dependency (git pin). VISA on the PC when using `play()` / `VsgSmw200a`.

## Layout

```text
SIGINT-RF-GUI/
  pyproject.toml
  README.md
  SIGINT-RF-GUI/
    vsg_gui.py
```

## Further reading

**`../SIGINT-RF-DEVICE-VSG_SMW200A/README.md`** — ARB catalog, YAML, `rs_smw_fsw_tcp`, and packaging for the device repo.

## License

MIT (see `pyproject.toml`).
