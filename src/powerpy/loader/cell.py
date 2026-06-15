"""Load cell_params sheet and the referenced electrical/diode JSON."""
import json
from pathlib import Path

from powerpy.loader._common import load_keyvalue_sheet
from powerpy.schemas.cell import (
    CellParameters,
    CellElectrical,
    ShuntDiodeParameters,
)


def load_cell_parameters(params_file: Path, data_dir: Path) -> CellParameters:
    values = load_keyvalue_sheet(params_file, "cell_params", data_dir)

    cell_ref = values["cell_reference_file"]
    electrical = load_cell_electrical_from_json(cell_ref)

    # CELL-level shunt diode: accept the new key name and the legacy one.
    diode_ref = values.get("cell_shunt_diode_reference_file") or values["diode_reference_file"]
    diode = load_shunt_diode_from_json(diode_ref)

    # STRING-level shunt diode: optional -- only when the workbook provides it.
    string_diode_ref = values.get("string_shunt_diode_reference_file")
    string_diode = (load_shunt_diode_from_json(string_diode_ref)
                    if string_diode_ref else None)

    return CellParameters(
        name=values["cell_name"],
        manufacturer=values["manufacturer"],
        base_material=values["base_material"],
        junction=values["junction"],
        ar_coating=values["ar_coating"],
        front_contact=values["front_contact"],
        rear_contact=values["rear_contact"],
        substrate_material=values["substrate_material"],
        cell_length_mm=values["cell_length"],
        cell_width_mm=values["cell_width"],
        cell_thickness_um=values["cell_thickness"],
        substrate_thickness_um=values["substrate_thickness"],
        cell_area_cm2=values["cell_area"],
        cell_mass_mg=values["cell_mass"],
        reference_file=cell_ref,
        diode_reference_file=diode_ref,
        electrical=electrical,
        diode=diode,
        string_diode=string_diode,
        string_diode_reference_file=string_diode_ref,
    )


def load_cell_electrical_from_json(json_path: Path) -> CellElectrical:
    """Load the cell's electrical parameters from its JSON reference file."""
    if not json_path.exists():
        raise FileNotFoundError(f"Cell reference file does not exist: {json_path}")

    with open(json_path, "r") as f:
        data = json.load(f)

    # Accept both the modern schema keys (isc_bol, ...) and the real
    # project's legacy keys (isc, imp, vmp, voc, area).
    def pick(*keys, default=None):
        for k in keys:
            if k in data:
                return data[k]
        return default

    # regressor curves vs Dose [%] (remaining factors + temp coefficients)
    regressors = {k: data[k] for k in
                  ("r_isc", "r_imp", "r_vmp", "r_voc",
                   "isc_dt", "imp_dt", "vmp_dt", "voc_dt")
                  if isinstance(data.get(k), dict) and "dose" in data[k]}

    return CellElectrical(
        isc_bol=float(pick("isc_bol", "isc")),
        voc_bol=float(pick("voc_bol", "voc")),
        imp_bol=float(pick("imp_bol", "imp")),
        vmp_bol=float(pick("vmp_bol", "vmp")),
        temp_coeff_isc=float(pick("temp_coeff_isc", default=0.0)),
        temp_coeff_voc=float(pick("temp_coeff_voc", default=0.0)),
        degradation=data.get("degradation", {}),
        regressors=regressors,
        alpha=float(pick("alpha", default=0.0)),
        epsilon=float(pick("epsilon", default=0.0)),
        r_interconnect=float(pick("r_interconnect", default=0.0)),
        t_ref=float(pick("t_ref", default=28.0)),
        area_m2=float(pick("area_m2", "area", default=0.0)),
    )


def load_shunt_diode_from_json(json_path: Path) -> ShuntDiodeParameters:
    """Load the shunt-diode parameters from the diode reference JSON.

    Tolerant of minimal/legacy diode files: every field is optional and
    falls back to the dataclass default.
    """
    if not json_path.exists():
        raise FileNotFoundError(f"Diode reference file does not exist: {json_path}")

    with open(json_path, "r") as f:
        data = json.load(f)

    # Accept both modern (name, i0, ...) and the real project's legacy keys
    # (diode_name, diode_i0, ...).
    def pick(*keys, default=None):
        for k in keys:
            if k in data:
                return data[k]
        return default

    return ShuntDiodeParameters(
        name=str(pick("name", "diode_name", default="")),
        reference=str(pick("reference", "diode_reference", default="")),
        i0=float(pick("i0", "diode_i0", default=0.0)),
        n=float(pick("n", "diode_n", default=1.0)),
        rs=float(pick("rs", "diode_rs", default=0.0)),
        t_ref=float(pick("t_ref", "diode_t_ref", default=25.0)),
        v_forward=float(pick("v_forward", "diode_v_forward", default=0.7)),
    )
