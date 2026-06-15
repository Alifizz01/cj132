# -*- coding: utf-8 -*-
"""Build the COMPLETE params.xlsx (every sheet) from scratch.

Auto-generated from the working params.xlsx, so it reproduces all sheets
exactly: document, cell_params, mission_orbit, mission_param, sections,
losses, radiation_fluxes, structure, analysis, requirement.

Edit the SHEETS data below to change values, then re-run to rebuild.

Usage:
    python scripts/build_params.py                 # -> params.xlsx (repo root)
    python scripts/build_params.py out.xlsx        # -> a chosen path
"""
import datetime  # noqa: F401  (used by baked-in date values)
import sys
from pathlib import Path

import openpyxl

# Each entry: (sheet_name, [row, row, ...]); row[0] is the header row.
SHEETS = [

    # --- cell_params (17 data rows) ---
    # columns: param | name | value | unit | type | source
    ('cell_params', [
        ['param', 'name', 'value', 'unit', 'type', 'source'],  # header
        ['cell_name', 'Cell Name', '3G30LARS GEO', '-', 'string', 'datasheet'],
        ['cell_reference_file', 'Cell Reference File', 'cells/3G30LARS_GEO.json', '-', 'path', '-'],
        ['cell_shunt_diode_reference_file', "Cell Shunt Diode's reference File", 'diodes/external.json', '-', 'path', '-'],
        ['manufacturer', 'Manufacturer', 'Azur Space Solar Power', '-', 'string', 'datasheet'],
        ['base_material', 'Base Material', 'GaInP2/GaAs on Ge Substrate', '-', 'string', 'datasheet'],
        ['junction', 'Junction', 'DEMO', '-', 'string', '-'],
        ['ar_coating', 'A/R Coating', 'TiOx / Al2O3', '-', 'string', 'datasheet'],
        ['front_contact', 'Front Contact', 'Au / Ag / AuZn weldable', '-', 'string', 'datasheet'],
        ['rear_contact', 'Rear Contact', 'AuGe / Ag / Au weldable', '-', 'string', 'datasheet'],
        ['substrate_material', 'Substrate Material', 'p-Ge', '-', 'string', 'datasheet'],
        ['substrate_thickness', 'Substrate Thickness', 140, 'um', 'float', 'datasheet'],
        ['cell_length', 'Cell Length', 124.3, 'mm', 'float', 'datasheet'],
        ['cell_width', 'Cell Width', 60.5, 'mm', 'float', 'datasheet'],
        ['cell_thickness', 'Cell Thickness', 160, 'um', 'float', 'datasheet'],
        ['cell_area', 'Cell Area', 70.75, 'cm2', 'float', 'datasheet'],
        ['cell_mass', 'Cell Mass', 6100, 'mg', 'float', 'datasheet'],
        ['string_shunt_diode_reference_file', "String Shunt Diode's reference File", 'diodes/aRoche.json', None, 'path', None],
    ]),

    # --- sections (24 data rows) ---
    # columns: section_ref | section_id | wing_id | panel_id | n_strings_parallel | resistance | n_scas_series_per_string | include
    ('sections', [
        ['section_ref', 'section_id', 'wing_id', 'panel_id', 'n_strings_parallel', 'resistance', 'n_scas_series_per_string', 'include'],  # header
        ['section_a_w1p1', 'A', 1, 1, 4, 0.20481105, 54, True],
        ['section_b_w1p1', 'B', 1, 1, 3, 0.25220475, 54, True],
        ['section_c_w1p1', 'C', 1, 1, 3, 0.200742075, 54, True],
        ['section_d_w1p1', 'D', 1, 1, 3, 0.32318775, 54, True],
        ['section_a_w1p2', 'A', 1, 2, 4, 0.283398233, 54, True],
        ['section_b_w1p2', 'B', 1, 2, 3, 0.480109175, 54, True],
        ['section_c_w1p2', 'C', 1, 2, 3, 0.53157185, 54, True],
        ['section_d_w1p2', 'D', 1, 2, 3, 0.53867015, 54, True],
        ['section_a_w1p3', 'A', 1, 3, 4, 0.501585317, 54, True],
        ['section_b_w1p3', 'B', 1, 3, 3, 0.69736615, 54, True],
        ['section_c_w1p3', 'C', 1, 3, 3, 0.645903475, 54, True],
        ['section_d_w1p3', 'D', 1, 3, 3, 0.76834915, 54, True],
        ['section_a_w2p1', 'A', 2, 1, 4, 0.20481105, 54, True],
        ['section_b_w2p1', 'B', 2, 1, 3, 0.25220475, 54, True],
        ['section_c_w2p1', 'C', 2, 1, 3, 0.200742075, 54, True],
        ['section_d_w2p1', 'D', 2, 1, 3, 0.32318775, 54, True],
        ['section_a_w2p2', 'A', 2, 2, 4, 0.283398233, 54, True],
        ['section_b_w2p2', 'B', 2, 2, 3, 0.480109175, 54, True],
        ['section_c_w2p2', 'C', 2, 2, 3, 0.53157185, 54, True],
        ['section_d_w2p2', 'D', 2, 2, 3, 0.53867015, 54, True],
        ['section_a_w2p3', 'A', 2, 3, 4, 0.501585317, 54, True],
        ['section_b_w2p3', 'B', 2, 3, 3, 0.69736615, 54, True],
        ['section_c_w2p3', 'C', 2, 3, 3, 0.645903475, 54, True],
        ['section_d_w2p3', 'D', 2, 3, 3, 0.76834915, 54, True],
    ]),

    # --- losses (21 data rows) ---
    # columns: name | phase | value | level | unit | description | source | include
    ('losses', [
        ['name', 'phase', 'value', 'level', 'unit', 'description', 'source', 'include'],  # header
        ['Coverglass loss', 'BOL_ATC', 0.988, 'cell', '-', 'Cover glass transmission', 'AZUR datasheet', True],
        ['Coverglass loss', 'BOL_BC', 0.988, 'cell', '-', 'Cover glass transmission', 'AZUR datasheet', True],
        ['Coverglass loss', 'End_of_LEOP', 0.988, 'cell', '-', 'Cover glass transmission', 'AZUR datasheet', True],
        ['Coverglass loss', 'End_of_ORP', 0.988, 'cell', '-', 'Cover glass transmission', 'AZUR datasheet', True],
        ['Coverglass loss', 'End_of_Life', 0.988, 'cell', '-', 'Cover glass transmission', 'AZUR datasheet', True],
        ['RSS', 'BOL_ATC', 0.978, 'cell', '-', 'Radiation-shielded shunt diode leakage', 'Internal estimate', True],
        ['RSS', 'BOL_BC', 0.995, 'cell', '-', 'Radiation-shielded shunt diode leakage', 'Internal estimate', True],
        ['RSS', 'End_of_LEOP', 0.978, 'cell', '-', 'Radiation-shielded shunt diode leakage', 'Internal estimate', True],
        ['RSS', 'End_of_ORP', 0.978, 'cell', '-', 'Radiation-shielded shunt diode leakage', 'Internal estimate', True],
        ['RSS', 'End_of_Life', 0.978, 'cell', '-', 'Radiation-shielded shunt diode leakage', 'Internal estimate', True],
        ['UV & Micrometeorite', 'BOL_ATC', 0.975, 'cell', '-', 'UV darkening + micrometeorite', 'Internal estimate', True],
        ['UV & Micrometeorite', 'BOL_BC', 0.975, 'cell', '-', 'UV darkening + micrometeorite', 'Internal estimate', True],
        ['UV & Micrometeorite', 'End_of_LEOP', 0.975, 'cell', '-', 'UV darkening + micrometeorite', 'Internal estimate', True],
        ['UV & Micrometeorite', 'End_of_ORP', 0.975, 'cell', '-', 'UV darkening + micrometeorite', 'Internal estimate', True],
        ['UV & Micrometeorite', 'End_of_Life', 0.975, 'cell', '-', 'UV darkening + micrometeorite', 'Internal estimate', True],
        ['String loss', 'End_of_Life', 0.987, 'string', '-', 'Soldering interconnect series loss', 'PS-PV-004', True],
        ['SADM misalignment', 'BOL_ATC', 1, 'array', '-', 'Solar array drive mechanism misalignment', 'ECSS-ECSSI', True],
        ['SADM misalignment', 'BOL_BC', 1, 'array', '-', 'Solar array drive mechanism misalignment', 'ECSS-ECSSI', True],
        ['SADM misalignment', 'End_of_LEOP', 1, 'array', '-', 'Solar array drive mechanism misalignment', 'ECSS-ECSSI', True],
        ['SADM misalignment', 'End_of_ORP', 1, 'array', '-', 'Solar array drive mechanism misalignment', 'ECSS-ECSSI', True],
        ['SADM misalignment', 'End_of_Life', 1, 'array', '-', 'Solar array drive mechanism misalignment', 'ECSS-ECSSI', True],
    ]),

    # --- radiation_fluxes (12 data rows) ---
    # columns: name | launch_config | phase | param | value | unit | description | source | include
    ('radiation_fluxes', [
        ['name', 'launch_config', 'phase', 'param', 'value', 'unit', 'description', 'source', 'include'],  # header
        ['fluence', 'single', 'End_of_LEOP', 'isc', 1910000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
        ['fluence', 'single', 'End_of_LEOP', 'voc', 2450000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
        ['fluence', 'single', 'End_of_ORP', 'isc', 11000000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
        ['fluence', 'single', 'End_of_ORP', 'voc', 11900000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
        ['fluence', 'single', 'End_of_Life', 'isc', 1130000000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
        ['fluence', 'single', 'End_of_Life', 'voc', 1360000000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
        ['fluence', 'dual', 'End_of_LEOP', 'isc', 167000000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
        ['fluence', 'dual', 'End_of_LEOP', 'voc', 473000000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
        ['fluence', 'dual', 'End_of_ORP', 'isc', 1340000000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
        ['fluence', 'dual', 'End_of_ORP', 'voc', 3760000000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
        ['fluence', 'dual', 'End_of_Life', 'isc', 2460000000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
        ['fluence', 'dual', 'End_of_Life', 'voc', 5110000000000000, 'e/cm2', '1 MeV equivalent electron fluence', 'Table 4', True],
    ]),

    # --- document (9 data rows) ---
    # columns: param | name | value | type | notes
    ('document', [
        ['param', 'name', 'value', 'type', 'notes'],  # header
        ['doc_number', 'Document Number', 'G2G-ADSO-AN-10003', 'string', None],
        ['doc_title', 'Document Title', 'Solar Array Analysis - Mission XYZ', 'string', None],
        ['issued_date', 'Issued Date', '2026-05-16', 'date', None],
        ['project', 'Project', 'XYZ Telecom Satellite', 'string', None],
        ['project_name', 'Project Name', 'XYZ Telecom Satellite', 'string', None],
        ['project_code', 'Project Code', 'XYZ-001', 'string', None],
        ['prepared_by', 'Prepared By', 'M. A. I. bin Ibrahim', 'string', None],
        ['approved_by', 'Approved By', None, 'string', None],
        ['logo_file', 'Logo File', 'assets/airbus_logo.png', 'path', None],
    ]),

    # --- structure (7 data rows) ---
    # columns: include | id | title | description | type | ref | audience
    ('structure', [
        ['include', 'id', 'title', 'description', 'type', 'ref', 'audience'],  # header
        [True, 'cell_params', 'Cell Parameters', None, 'cell_params', None, 'both'],
        [True, 'cell_regressors', 'Cell Radiation Regressors', None, 'figure', 'cell_regressors', 'both'],
        [True, 'sections_table', 'Sections and Harness', None, 'sections_table', None, 'both'],
        [True, 'loss_budget', 'Loss Factor Budget', None, 'loss_table', None, 'both'],
        [True, 'results', 'Results', None, 'results_table', None, 'both'],
        [True, 'fig_iv_section', 'Per-Section IV Curves by Wing and Position', None, 'figure', 'iv_sections', 'both'],
        [True, 'fig_iv_panel', 'Whole-Array IV/PV Curve', None, 'figure', 'iv_panel', 'both'],
    ]),

    # --- mission_orbit (18 data rows) ---
    # columns: param | name | value | unit | type | source
    ('mission_orbit', [
        ['param', 'name', 'value', 'unit', 'type', 'source'],  # header
        ['orbit_type', 'Orbit Type', 'GEO', '-', 'string', None],
        ['altitude_km', 'Altitude', 35786, 'km', 'float', None],
        ['inclination_deg', 'Inclination', 0, 'deg', 'float', None],
        ['eclipse_duration_min', 'Max Eclipse Duration', 72, 'min', 'float', None],
        ['launch_date', 'Launch Date', datetime.datetime(2027, 3, 15, 0, 0), '-', 'date', None],
        ['mission_duration_years', 'Mission Duration', 15, 'years', 'float', None],
        ['leop_duration_days', 'LEOP Duration', 10, 'days', 'float', None],
        ['orp_duration_months', 'ORP Duration', 3, 'months', 'float', None],
        ['sun_intensity_bol', 'Sun Intensity BOL', 1367, 'W/m2', 'float', None],
        ['sun_intensity_eol_min', 'Sun Intensity EOL Min', 1322, 'W/m2', 'float', None],
        ['temp_max_K', 'Max Temperature', 363, 'K', 'float', None],
        ['temp_min_K', 'Min Temperature', 173, 'K', 'float', None],
        ['bus_voltage', 'Bus Voltage', 101.5, 'V', 'float', None],
        ['max_string_current', 'Max String Current', 2.5, 'A', 'float', None],
        ['max_beta_angle_deg', 'Max Beta Angle', 23.5, 'deg', 'float', None],
        ['bond_albedo', 'Bond Albedo', 0.30, '-', 'float', None],
        ['planet_temp_k', 'Planet Temperature', 255.0, 'K', 'float', None],
        ['ir_emissivity', 'Planet IR Emissivity', 1.0, '-', 'float', None],
    ]),

    # --- mission_param (24 data rows) ---
    # columns: name | launch_config | phase | value | unit | source | description | include
    ('mission_param', [
        ['name', 'launch_config', 'phase', 'value', 'unit', 'source', 'description', 'include'],  # header
        ['bus_voltage', 'single', 'End_of_ORP', 105.5, 'V', 'Table 7', None, True],
        ['bus_voltage', 'single', 'End_of_Life', 101.5, 'V', 'Table 7', None, True],
        ['bus_voltage', 'dual', 'End_of_ORP', 101.5, 'V', 'Table 7', None, True],
        ['bus_voltage', 'dual', 'End_of_Life', 101.5, 'V', 'Table 7', None, True],
        ['req_power', 'single', 'End_of_ORP', 8350, 'W', 'Table 7', None, True],
        ['req_power', 'single', 'End_of_Life', 7550, 'W', 'Table 7', None, True],
        ['req_power', 'dual', 'End_of_ORP', 8350, 'W', 'Table 7', None, True],
        ['req_power', 'dual', 'End_of_Life', 7550, 'W', 'Table 7', None, True],
        ['predicted_power', 'single', 'End_of_LEOP', 9193, 'W', 'Table 7', None, True],
        ['predicted_power', 'single', 'End_of_ORP', 9102, 'W', 'Table 7', None, True],
        ['predicted_power', 'single', 'End_of_Life', 8275, 'W', 'Table 7', None, True],
        ['predicted_power', 'dual', 'End_of_LEOP', 9103, 'W', 'Table 7', None, True],
        ['predicted_power', 'dual', 'End_of_ORP', 8364, 'W', 'Table 7', None, True],
        ['predicted_power', 'dual', 'End_of_Life', 7584, 'W', 'Table 7', None, True],
        ['delta_to_req', 'single', 'End_of_ORP', 9, '%', 'Table 7', None, True],
        ['delta_to_req', 'single', 'End_of_Life', 9.6, '%', 'Table 7', None, True],
        ['delta_to_req', 'dual', 'End_of_ORP', 0.2, '%', 'Table 7', None, True],
        ['delta_to_req', 'dual', 'End_of_Life', 0.4, '%', 'Table 7', None, True],
        ['pva_temperature', 'single', 'End_of_LEOP', 45.1, 'degC', 'Table 7', None, True],
        ['pva_temperature', 'single', 'End_of_ORP', 45.5, 'degC', 'Table 7', None, True],
        ['pva_temperature', 'single', 'End_of_Life', 49.4, 'degC', 'Table 7', None, True],
        ['pva_temperature', 'dual', 'End_of_LEOP', 46.9, 'degC', 'Table 7', None, True],
        ['pva_temperature', 'dual', 'End_of_ORP', 49.5, 'degC', 'Table 7', None, True],
        ['pva_temperature', 'dual', 'End_of_Life', 51.1, 'degC', 'Table 7', None, True],
    ]),

    # --- analysis (2 data rows) ---
    # columns: launch | phase | season | temperature | string_loss | sun_angle | v_operating
    ('analysis', [
        ['launch', 'phase', 'season', 'temperature', 'string_loss', 'sun_angle', 'v_operating'],  # header
        ['single', 'End_of_Life', '1322/1367', 51.1, 1, 0, 101.5],
        ['dual', 'End_of_Life', '1322/1367', 51.1, 1, 0, 101.5],
    ]),

    # --- requirement (13 data rows) ---
    # columns: param | type | value
    ('requirement', [
        ['param', 'type', 'value'],  # header
        ['voltage_operating', 'float', 101.5],
        ['voltage_unit', 'string', 'V'],
        ['max_section_current', 'float', 5.4],
        ['max_section_current_unit', 'string', 'A'],
        ['magnetic_moment_max', 'float', 1],
        ['magnetic_moment_unit', 'string', 'Am^2'],
        ['eor_power_min', 'float', 8350],
        ['eol_power_min', 'float', 7550],
        ['power_unit', 'string', 'W'],
        ['sun_angle', 'float', 23.5],
        ['sun_angle_unit', 'string', 'deg'],
        ['flux_at_array', 'float', 1321],
        ['flux_unit', 'string', 'W/m^2'],
    ]),
]


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(__file__).resolve().parent.parent / 'params.xlsx'
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in SHEETS:
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(list(r))
    try:
        wb.save(out)
    except PermissionError:
        sys.exit('ERROR: %s is open/locked in Excel. Close it or pass another path.' % out)
    print('built %d sheets -> %s' % (len(SHEETS), out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
