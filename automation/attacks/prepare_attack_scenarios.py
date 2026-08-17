#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_ROOT = Path("/home/ubuntu/AirGuard-6LoWPAN")

SCENARIOS = {
    "UDP_Flood": "airguard-attack-udp-flood",
    "DIS_Flood": "airguard-attack-dis-flood",
    "DIO_Flood": "airguard-attack-dio-flood",
}

def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]

def remove_script_runner(root: ET.Element) -> None:
    for plugin in list(root.findall("plugin")):
        if (plugin.text or "").strip() == "org.contikios.cooja.plugins.ScriptRunner":
            root.remove(plugin)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root_dir = args.project_root.resolve()
    baseline = root_dir / "simulations/baseline/AirGuard_Baseline_CrossLayer.csc"
    if not baseline.is_file():
        raise SystemExit(f"Baseline bulunamadı: {baseline}")

    source_tree = ET.parse(baseline)
    out_dir = root_dir / "simulations/attacks"
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, firmware_folder in SCENARIOS.items():
        root = copy.deepcopy(source_tree.getroot())
        simulation = root.find("simulation")
        if simulation is None:
            raise SystemExit("<simulation> bulunamadı")
        title = simulation.find("title")
        if title is not None:
            title.text = f"AirGuard-6LoWPAN {name} Attack"
        radio = simulation.find("radiomedium")
        if radio is None:
            raise SystemExit("<radiomedium> bulunamadı")
        radio.find("success_ratio_tx").text = "1.0"
        radio.find("success_ratio_rx").text = "1.0"
        for source in root.iter():
            if local(source.tag) != "source":
                continue
            text = source.text or ""
            if "udp-server.c" in text:
                source.text = f"[CONFIG_DIR]/../../firmware/{firmware_folder}/udp-server.c"
            elif "udp-client.c" in text:
                source.text = f"[CONFIG_DIR]/../../firmware/{firmware_folder}/udp-client.c"
        remove_script_runner(root)
        output = out_dir / f"AirGuard_Attack_{name}_CrossLayer.csc"
        ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
        print(f"[OK] {output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
