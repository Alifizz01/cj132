# -*- coding: utf-8 -*-
"""
Created on Fri Jan 18 07:54:25 2019

@author: o27477438
"""

import pandas as pd
import string as pystring
import numpy as np
import matplotlib.pyplot as plt
import math
import pkg_resources

from copy import deepcopy, copy

from scipy.optimize import newton_krylov, minimize_scalar, minimize

from .datamgmt import getSubstrateData
from .definitions import B_0, T_0
from .thermal import thermal, thermal_extracted
from .electric import IVPlot


class panel():

    def __init__(self, tSections=None, tSubstrate=None, tArea=0, localSubstrateFile=False):

        self.sections = tSections

        self.temperature_front = 0
        self.temperature_rear  = 0
        self.area = tArea

        self.season_angle = 0

        self.angle_alpha = 0
        self.angle_beta  = 0


        if not localSubstrateFile:
            filename = pkg_resources.resource_filename(__name__, "data/substrates/" + tSubstrate + ".json")
            self.substrate = getSubstrateData(filename)
        else:
            self.substrate = getSubstrateData(tSubstrate+".json")

    @classmethod
    def fromSingleSection(cls, tSection, count, tSubstrate, tArea, localSubstrateFile=False):

        tNames = [pystring.ascii_uppercase[x] for x in range(count)]
        tSections = [deepcopy(tSection) for x in range(count)]

        return cls(tSections=dict(zip(tNames, tSections)), tSubstrate=tSubstrate, tArea=tArea, localSubstrateFile=localSubstrateFile)

    @classmethod
    def fromSections(cls, sections, tSubstrate, tArea, names=None, localSubstrateFile=False):

        if names is None:
            tNames = [pystring.ascii_uppercase[x] for x in range(len(sections))]
        else:
            tNames = deepcopy(names)
        tSections = deepcopy(sections)

        return cls(tSections=dict(zip(tNames, tSections)), tSubstrate=tSubstrate, tArea=tArea, localSubstrateFile=localSubstrateFile)

    def addLossI(self, name, factor, verbose=True):
        for tSection in self.sections:
            self.sections[tSection].addLossI(name=name, factor=factor, verbose=verbose)

    def addLossV(self, name, factor, verbose=True):
        for tSection in self.sections:
            self.sections[tSection].addLossV(name=name, factor=factor, verbose=verbose)

    def setDose(self, dose_i, dose_v):
        for tSection in self.sections:
            self.sections[tSection].setDose(dose_i=dose_i, dose_v=dose_v)

    def setSubstrate(self, tSubstrate):
        self.substrate = getSubstrateData(tSubstrate)

    def setTemperature(self, temperature):
        self.temperature_front = temperature
        for tSection in self.sections:
            self.sections[tSection].setTemperature(temperature)

    def setModel(self, model):
        for tSection in self.sections:
            self.sections[tSection].setModel(model)

    def setCell(self, cell_type):
        for tSection in self.sections:
            self.sections[tSection].setCell(cell_type)

    def setDiode(self, diode_type):
        for tSection in self.sections:
            self.sections[tSection].setDiode(diode_type)

    def setAngles(self, alpha, beta):

        self.angle_alpha = alpha
        self.angle_beta  = beta

        for tSection in self.sections:
            self.sections[tSection].setAngles(alpha, beta)

    def setSeason(self, season):
        self.season = season
        for tSection in self.sections:
            self.sections[tSection].setSeason(season)

    def setSeasonAngle(self, season_angle):
        self.season_angle = season_angle
        for tSection in self.sections:
            self.sections[tSection].setSeasonAngle(season_angle)

    def removeLosses(self):
        for tSection in self.sections:
            self.sections[tSection].removeLosses()

    def renameSection(self, name, newName):
        self.sections[newName] = self.sections[name]
        self.sections.pop(name)

    def removeSection(self, name):
        self.sections.pop(name)

    def calcVoc(self):
        return max([self.sections[tSection].calcVoc() for tSection in self.sections])

    def calcIsc(self):
        return sum([self.sections[tSection].calcIsc() for tSection in self.sections])

    def currentAtVoltage(self, voltage):
        return sum([self.sections[tSection].currentAtVoltage(voltage) for tSection in self.sections])

    def powerAtVoltage(self, voltage):
        return self.currentAtVoltage(voltage) * voltage

    def calcIVCurve(self, step=0.1):

        dfs = []
        for i, tSection in enumerate(self.sections):
            dfx = self.sections[tSection].calcIVCurve(step=step)
            dfx = dfx[["current"]]
            dfx.columns = ["current_" + str(i)]
            dfs.append(dfx)

        df = pd.concat(dfs, axis=1).fillna(0)
        df["current"] = df.sum(axis = 1)
        df["power"] = df.index * df["current"]

        return df[["current", "power"]]

    def calcMP(self, step=0.1):
        df = self.calcIVCurve(step=step)
        mpp = df[df["power"] == df["power"].max()].reset_index().to_dict("records")[0]
        return mpp

    def calcQuad(self, step=0.1):

        mp = self.calcMP(step)

        return {"isc": self.calcIsc(),
                "voc": self.calcVoc(),
                "vmp": mp["voltage"],
                "imp": mp["current"],
                "pmp": mp["power"]
                }
            for tString in self.sections[tSection].strings:
                for tCell in self.sections[tSection].strings[tString].cells:
                    cellArea += self.sections[tSection].strings[tString].cells[tCell].config["area"]

        return cellArea

    def prepareParameters(self):

        front_side = {}
        front_side["alpha"]   = deepcopy(self.substrate["alpha_front"])
        front_side["epsilon"] = deepcopy(self.substrate["epsilon_front"])

        rear_side = {}
        rear_side["alpha"]   = deepcopy(self.substrate["alpha_rear"])
        rear_side["epsilon"] = deepcopy(self.substrate["epsilon_rear"])
        rear_side["area"]    = deepcopy(self.area)

        area = deepcopy(self.area)
        front_side["epsilon"] = deepcopy(self.substrate["epsilon_front"])

        rear_side = {}
        rear_side["alpha"]   = deepcopy(self.substrate["alpha_rear"])
        rear_side["epsilon"] = deepcopy(self.substrate["epsilon_rear"])
        rear_side["area"]    = deepcopy(self.area)

        area = deepcopy(self.area)

        conductivity = deepcopy(self.substrate["conductivity"])
        thickness    = deepcopy(self.substrate["thickness"])

        angle_alpha  = deepcopy(self.angle_alpha)
        angle_beta   = deepcopy(self.angle_beta)
        season_angle = deepcopy(self.season_angle)

        tilt = math.cos(math.radians(angle_alpha - season_angle)) * math.cos(math.radians(angle_beta))

        return area, front_side, rear_side, conductivity / thickness, tilt

    def thermalProperties(self):

        area, front_side, rear_side, cond, _ = self.prepareParameters()

        dfs = []

        for tSection in self.sections:
            for tString in self.sections[tSection].strings:
                for tCell in self.sections[tSection].strings[tString].cells:
                    c = copy(self.sections[tSection].strings[tString].cells[tCell].config)
                    dfs.append({"area": c["area"], "alpha": c["alpha"], "epsilon": c["epsilon"]})

        df = pd.DataFrame(dfs)

        front_side["area"] = area - df["area"].sum()

        if front_side["area"] < 0:
            print("Substrate area is negative, aborting calculation.")
            return int(0)

        dfs.append(front_side)
        df = pd.DataFrame(dfs)

        return df

    def thermalEquilibrium(self, voltage, season, P_Albedo=0, P_IR=0, verbose=False):

        front_side = self.thermalProperties()
        area, _, rear_side, cond, tilt = self.prepareParameters()

        if verbose:
            print("Setting Panel-wide season to", season)
        self.setSeason(season)

        if type(front_side) == int:
            return 0

        def teq_calc(t_in):

            t_in = t_in[0] + T_0

            if t_in > 200 or t_in < -200:
                return abs(t_in * 100)

            self.setTemperature(t_in)
            p_elec = self.currentAtVoltage(voltage) * voltage
            t_therm = thermal(season * B_0, P_Albedo, P_IR, p_elec, front_side, rear_side, cond, tilt)

            self.temperature_front = t_therm["T_Front"]
            self.temperature_rear  = t_therm["T_Rear"]

            return abs(t_in - t_therm["T_Front"])

        #t_set = newton_krylov(teq_calc, [20], f_rtol=1)[0]
        t_set = minimize(teq_calc, x0=-T_0, method="Nelder-Mead", options={"fatol":0.1})["x"][0] + T_0
        self.setTemperature(t_set)

        if verbose:
            print("Setting Panel-wide temperature to equilibrium of", t_set, "degC")

        return t_set

    def optimPMP(self, season, P_Albedo=0, P_IR=0, step=0.1, tstart=None, verbose=False):

        self.setTemperature(20)
        self.setSeason(season)
        front_side = self.thermalProperties()
        area, _, rear_side, cond, tilt = self.prepareParameters()

        if verbose:
            print("Setting Panel-wide season to", season)

        def pmp_calc(t_test):

            pmp_therm = thermal_extracted(t_test[0], season * B_0, P_IR, front_side, rear_side, cond, tilt)
            self.setTemperature(t_test[0])
            pmp_elec = self.calcMP(step=step)["power"]

            if verbose:
                print("Searching PMP Optimum @", t_test[0], " degC,", round(pmp_therm,3), "vs", round(pmp_elec, 3) )

            return abs(pmp_therm - pmp_elec)

        if tstart == None:
            tstart=20

        t_best = minimize(pmp_calc, x0=tstart, method="Nelder-Mead", options={"xatol":0.1, "fatol":1})["x"][0]
        self.setTemperature(t_best)
        return self.calcMP(step=step)
