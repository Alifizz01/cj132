# -*- coding: utf-8 -*-
"""
Created on Fri May 28 09:04:29 2021

@author: o27477438
"""

from .panel import panel
from .thermal import thermal_thin, thermal_extracted_thin
from .definitions import B_0, T_0
from scipy.optimize import newton_krylov, minimize

import pandas as pd

from copy import copy

class panel_thin(panel):

    def thermalEquilibrium(self, voltage, season, P_Albedo=0, P_IR=0, verbose=False):

        front_side = self.thermalProperties()
        area, _, rear_side, cond, tilt = self.prepareParameters()

        if verbose:
            print("Setting Panel-wide season to", season)
        self.setSeason(season)

        def teq_calc(t_in):

            t_in = t_in[0] + T_0

            if t_in > 200 or t_in < -200:
                return abs(t_in * 100)

            self.setTemperature(t_in)
            p_elec = self.currentAtVoltage(voltage) * voltage
            t_therm = thermal_thin(season * B_0, P_Albedo, P_IR, p_elec, front_side, rear_side, tilt)

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
        sca, rear_side, cellArea = self.thermalProperties()
        area, _, rear_side, _, tilt = self.prepareParameters()

        def pmp_calc(t_test):

            pmp_therm = thermal_extracted_thin(t_test[0], season * B_0, P_Albedo, P_IR, sca, rear_side, tilt)
            self.setTemperature(t_test[0])
            pmp_elec = self.calcMP(step=step)["power"] / cellArea

            if verbose:
                print("Searching PMP Optimum @", t_test[0], " degC,", round(pmp_therm,3), "vs", round(pmp_elec, 3) )

            return abs(pmp_therm - pmp_elec)

        if tstart == None:
            tstart=20

        t_best = minimize(pmp_calc, x0=tstart, method="Nelder-Mead", options={"xatol":0.1, "fatol":1})["x"][0]
        self.setTemperature(t_best)
        return self.calcMP(step=step)
