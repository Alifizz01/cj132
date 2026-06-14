# -*- coding: utf-8 -*-
"""
Created on Thu Jan 10 15:14:18 2019

@author: o27477438
"""

import pandas as pd
import pkg_resources
import json
from scipy.interpolate import interp1d
import pickle
import numpy as np
import os


# from .definitions import remote_definitions, local_definitions

def getAvailableCells():
    """
    This function returns all the available types of cells. All cell files have the extension .json.
    """
    cell_dir = pkg_resources.resource_filename(__name__, "data/cells")
    cells = os.listdir(cell_dir)
    cells = [x.replace(".json", "") for x in cells]
    return cells

def getAvailableSubstrates():
    """
    This function returns all the available types of cells. All cell files have the extension .json.
    """
    cell_dir = pkg_resources.resource_filename(__name__, "data/substrates")
    cells = os.listdir(cell_dir)
    cells = [x.replace(".json", "") for x in cells]
    return cells

def getAvailableDiodes():
    """
    This function returns all the available types of cells. All cell files have the extension .json.
    """
    cell_dir = pkg_resources.resource_filename(__name__, "data/diodes")
    cells = os.listdir(cell_dir)
    cells = [x.replace(".json", "") for x in cells]
    return cells


def getCellData(filename, interpolation_type="linear"):
    """
    This function returns the dictionaries 'config_dict' and 'reg_dict' which are compilations of the data corresponding
    to the cell type that we input.
    """

    with open(filename, 'r') as f:
        cdef = json.load(f)
    config_dict = {}
    for key in ['name', 'reference', 'alpha', 'epsilon', 'isc', 'imp', 'vmp', 'voc', 'r_interconnect', 't_ref', 'area']:
        config_dict[key] = cdef[key]

    reg_dict = {}
    for reg in ['isc_dt', 'imp_dt', 'vmp_dt', 'voc_dt', 'r_isc', 'r_imp', 'r_vmp', 'r_voc']:
        reg_dict[reg] = interp1d(np.array(cdef[reg]["dose"]) * 10 ** 14, cdef[reg]["value"], kind=interpolation_type)

    return config_dict, reg_dict


def getDiodeData(filename):

    """
    This function returns the dictionary 'config_dict' which is a compilation of the data corresponding
    to the diode type that we input.
    """

    with open(filename, 'r') as f:
        cdef = json.load(f)
    config_dict = {}
    for key in ['diode_name', 'diode_reference', 'diode_i0', 'diode_n', 'diode_t_ref','diode_rs']:
        config_dict[key] = cdef[key]

    return config_dict


def getSubstrateData(filename):

    """
    This function returns the dictionary 'config_dict' which is a compilation of the data corresponding
    to the panel substrate type that we input.
    """

    with open(filename, 'r') as f:
        cdef = json.load(f)
    config_dict = {}
    for key in ["name", "alpha_front", "alpha_rear", "conductivity", "epsilon_front", "epsilon_rear", "thickness"]:
        config_dict[key] = cdef[key]

    return config_dict


def deepcopy(data):
    return pickle.loads(pickle.dumps(data))
