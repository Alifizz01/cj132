# -*- coding: utf-8 -*-
"""
Created on Fri Jan 18 07:53:01 2019

@author: o27477438
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import pkg_resources

from scipy.optimize import fmin, minimize
from scipy.interpolate import interp1d
import ujson

from .datamgmt import getCellData, getDiodeData
from .electric import cellBuilder, RShuntModel, RSeriesModel, IVPlot, ng_sim
from .definitions import spice_options, T_Circuit

import hashlib


def deepcopy(a):
    return ujson.loads(ujson.dumps(a))


class cell(object):

    """

    The standard simulation model is the RSeriesModel. In case the RShuntModel shall be used,
    it has to be given by using: model="RShuntModel"

    """

    def __init__(self, cell_type, model="RSeriesModel", diode_type="open", localCellFile=False, localDiodeFile=False):

        """
        The cell constructor
        cell_type: input the cell type and the program will search the corresponding .json file in the database
        model: RSeriesModel or RShuntModel
        diode_type: -- self explanatory --
        """

        self.doses = {"i": 0, "v": 0}
        self.lossesI = {}
        self.lossesI = {}
        self.lossesV = {}
        self.config  = {}
        self.regressors = {}

        self.temperature = 28

        self.season = 1

        self.angle_alpha = 0
        self.angle_beta  = 0
        self.season_angle = 0

        self.model = model

        self.crack = 0

        if cell_type is not None:

            self.type = cell_type

            if not localCellFile:
                filename = pkg_resources.resource_filename(__name__, "data/cells/" + cell_type + ".json")
                tCfg, tReg = getCellData(filename)
            else:
                tCfg, tReg = getCellData(cell_type+".json")

            self.config = {**self.config, **tCfg}
            self.regressors = {**self.regressors, **tReg}
            self.temperature = self.config["t_ref"]

        if diode_type is not None:
            self.diode = diode_type
            if not localDiodeFile:
                filename = pkg_resources.resource_filename(__name__, "data/diodes/" + diode_type + ".json")
                dCfg = getDiodeData(filename)
            else:
                dCfg = getDiodeData(diode_type+".json")

            self.config = {**self.config, **dCfg}


    def addLossI(self, name, factor, verbose=True):

        """

        Using this function, a new loss factor on the cell's current is added. This means, that
        Before being used in the simulation, all loss factors are multiplied. This means, that
        RSS losses need to be calculated manually before being used, e.g. through the function RSS_loss from the
        utilities submodule.

        name : This variable gives the name of the loss factor, e.g. "Coverglass"

        factor : This variable gives the loss factor itself, e.g. 0.98

        verbose : This variable can be either "True" or "False" and declares, if a warning shall be given
        in case an already existing loss factor is overwritten.

        """

        if name in self.lossesI:
            if verbose:
                print("Warning: Overwriting current loss factor")

        self.lossesI[name] = factor

    def addLossV(self, name, factor, verbose=True):

        """

        Using this function, a new loss factor on the cell's voltage is added. This means, that
        Before being used in the simulation, all loss factors are multiplied. This means, that
        RSS losses need to be calculated manually before being used, e.g. through the function RSS_loss from the
        utilities submodule.

        name : This variable gives the name of the loss factor, e.g. "Coverglass"

        factor : This variable gives the loss factor itself, e.g. 0.98

        verbose : This variable can be either "True" or "False" and declares, if a warning shall be given
        in case an already existing loss factor is overwritten.

        """

        if name in self.lossesV:
            if verbose:
                print("Warning: Overwriting current loss factor")

        self.lossesV[name] = factor

    def setDose(self, dose_i, dose_v):

        """

        Using this function, the applicable dose is set. The input has to be given in units of 10**14.
        A warning is printed if the input appears to still include the 10**14 factor, but it is then set anyways.

        dose_i : Equivalent 1MeV electron dose on current
        dose_v : Equivalent 1MeV electron dose on voltage

        """

        self.doses["i"] = dose_i * 10 ** 14
        self.doses["v"] = dose_v * 10 ** 14

        if (dose_i > 1000) or (dose_v > 1000):
            print("WARNING: Input has to be in 10^14")

    def setTemperature(self, temperature):

        """

        This function sets the temperature of the cell in degrees celsius.
        If the cell's temperature has been calculated previously using one of the
        functions to determine thermal equilibrium, temperature does not need to be set anymore.

        temperature : temperature of the cell in °C.

        """

        self.temperature = temperature

    def setModel(self, model):

        """

        This function sets the model for the respective cell.

        model : either "RSeriesModel" or "RShuntModel" (case-sensitive!)

        """

        self.model = model

    def setSeason(self, season):

        """

        This function sets the season of the cell. The input can any of:
        - SS for 0.967
        - WS for 1.034
        - VEX for 1.008
        - AEX for 0.993
        - 1 (=AM0, 1367 W/m^2)
        - 0 (cell is dead)
        - any other multiple of AM0

        season : input as described above.

        """

        if season == "SS":
            season = 0.967
            self.setSeasonAngle(23.5)

        if season == "WS":
            season = 1.034
            self.setSeasonAngle(-23.5)

        if season == "VEX":
            season = 1.008

        if season == "AEX":
            season = 0.993

        self.season = season

    def setAngles(self, alpha, beta):

        """

        This function sets the tilt angles between solar cell surface and sun incidence.
        If both angles are set to zero (this is set as standard), sun incidence is perpendicular.

        alpha : first tilting angle in degrees.
        beta  : second tilting angle in degrees.

        """

        self.angle_alpha = alpha
        self.angle_beta  = beta

    def setSeasonAngle(self, season_angle):

        """

        This function sets the season angle, which is added to alpha before simulation.

        """

        self.season_angle = season_angle

    def setCell(self, cell_type):

        """

        This function allows to change the cell type after the cell has already been created.
        Names as given in the cell parameter database have to be used.

        cell_type : name of cell in cell parameter database

        """

        old_diode = self.diode

        self.type = cell_type
        tCfg, tReg = getCellData(cell_type)
        self.config = tCfg
        self.regressors = tReg
        self.temperature = self.config["t_ref"]

        self.diode = old_diode
        dCfg = getDiodeData(old_diode)
        self.config = {**self.config, **dCfg}

    def resizeCell(self, area_new, resize_diode=False):

        """
        area_new: new area of the solar cell
        new cell with new area
        """

        size_coeff = area_new / self.config["area"]

        # update size, isc, imp
        self.config["area"] = area_new
        # self.config["isc"] = self.config["isc"] * size_coeff  # OCR_UNCLEAR: bottom rows partially obscured
        self.config["imp"] = self.config["imp"] * size_coeff

        # update regressor phi
        for reg in ["isc_dt", "imp_dt"]:
            tx, ty = self.regressors[reg].x, self.regressors[reg].y
            ty = np.array(ty) * size_coeff
            self.regressors[reg] = interp1d(tx, ty)

        if resize_diode:
            self.config["diode_i0"] = self.config["diode_i0"] * size_coeff


    def setDiode(self, diode_type):

        """
        setting the diode
        """

        # old_cell = self.type

        # self.type = old_cell
        # tCfg, tReg = getCellData(old_cell)
        # self.config = tCfg
        # self.regressors = tReg
        # self.temperature = self.config["t_ref"]

        self.diode = diode_type
        dCfg = getDiodeData(diode_type)
        self.config = {**self.config, **dCfg}

    def removeLosses(self):

        """
        This function removes ALL loss factors.
        """

        self.lossesI = {}
        self.lossesV = {}

    def prepareModel(self):

        """
        This method compiles all the needed parameters needed to build the simulation model in ngspice into the output
        """

        # fetch all input data safely
        model       = deepcopy(self.model)
        config      = deepcopy(self.config)
        temperature = deepcopy(float(self.temperature))
        lossesI     = deepcopy(self.lossesI)
        lossesV     = deepcopy(self.lossesV)
        doses       = deepcopy(self.doses)

        # calculate effective angle w.r.t sun
        buffer_alpha        = deepcopy(self.angle_alpha)
        buffer_beta         = deepcopy(self.angle_beta)
        buffer_season_angle = deepcopy(self.season_angle)
        tilt = math.cos(math.radians(buffer_alpha + buffer_season_angle)) * math.cos(math.radians(buffer_beta))

        # collect and multiply loss factors
        lossesI["inherited_tilt"] = deepcopy(tilt)
        lossesI["inherited_season"] = deepcopy(self.season)
        lossI = np.product(list(lossesI.values()))
        lossV = np.product(list(lossesV.values()))

        # calculate imp_acc to formula found in excel pp
        config["imp_dt"] = self.regressors["imp_dt"](doses["i"])
        config["isc_dt"] = self.regressors["isc_dt"](doses["i"])

        if temperature > 0:
            imp_dt = config["imp_dt"]
        else:
            imp_dt = (config["isc_dt"] * \
                     (-temperature) + config["imp_dt"] * config["t_ref"]) / \
                     (config["t_ref"] - temperature)

        # calculate cell properties at given dose and temperature
        isc = config["isc"] * self.regressors["r_isc"](doses["i"])
        isc = isc + self.regressors["isc_dt"](doses["i"]) * (temperature - config["t_ref"])

        imp = config["imp"] * self.regressors["r_imp"](doses["i"])
        imp = imp + imp_dt * (temperature - config["t_ref"])

        vmp = config["vmp"] * self.regressors["r_vmp"](doses["v"])
        vmp = vmp + self.regressors["vmp_dt"](doses["v"]) * (temperature - config["t_ref"])

        voc = config["voc"] * self.regressors["r_voc"](doses["v"])
        voc = voc + self.regressors["voc_dt"](doses["v"]) * (temperature - config["t_ref"])

        # determine correction factors for voltage in line with old PP
        if self.season != 0:
            vmp_correction = (1+(self.config["isc"]-self.config["imp"])/self.config["imp"])*np.log(self.season * tilt)
            voc_correction = (1+(self.config["vmp"]/self.config["voc"])*(self.config["isc"]-self.config["imp"])/self.config["imp"])*np.log(self.season * tilt)
        else:
            vmp_correction = 1
            voc_correction = 1

        # updated application of loss factors
        isc = isc * lossI
        imp = imp * lossI
        vmp = vmp * lossV * vmp_correction
        voc = voc * lossV * voc_correction


        return model, config, isc, imp, vmp, voc

    def modelToArguments(self, model, config, isc, imp, vmp, voc, name=None, dark=False):

        """
        The method cellBuilder from electric.py is needed to generate a text string which is used for the ngspice simulation.
        However, the method cellBuilder requires arguments as an input, hence we have to convert the output of 'prepareModel'
        into arguments.

        As a remark, 'model' from the input could be either the string 'RSeriesModel' or 'RShuntModel'. But 'model' which is the output,
        is the concrete circuit ngspice simulation model in the form of a string.
        """
        # calculate circuit properties acc. to cell model (shunt/series)
        args = {}

        if model == "RShuntModel":
            args = RShuntModel(imp=imp, voc=voc, isc=isc, vmp=vmp)

        if model == "RSeriesModel":
            args = RSeriesModel(imp=imp, voc=voc, isc=isc, vmp=vmp)

        # add diode properties
        args["i0_diode"] = config["diode_i0"]
        args["n_diode"]  = config["diode_n"]
        args["rs_diode"] = config["diode_rs"]
        args["r_diode_shunt"] = 0
        args["r_diode_high"]  = 0
        args["r_diode_low"]   = 0

        # add interconnectors
        args["r_interconnect"] = config["r_interconnect"]

        # turn current of for DIV curve
        if dark:
            args["isc"] = 0

        # create hash for cell name
        if name is None:
            name = [str(args[key]) for key in args] + [self.type]
            name = hashlib.md5(str.encode(",".join(name))).hexdigest()

        # create spice model as string
        model = cellBuilder(name=name, args=args)

        return model, name

    def buildModel(self, name=None, dark=False):

        """
        This function is basically 'prepareModel' and 'modelToArguments' in a single step.
        """

        model, config, isc, imp, vmp, voc = self.prepareModel()
        model, cName = self.modelToArguments(model, config, isc, imp, vmp, voc, name=name, dark=dark)

        return model, cName

    def currentAtVoltage(self, voltage, unrestricted=False):

        """
        This function simulates the cell using ngSpice and determines the current delivered at the specified voltage.

        voltage : Voltage at which to simulate the cell.

        """

        if (voltage > self.calcVoc()) and not unrestricted:
            return 0

        sCell, sName = self.buildModel()
        circuit  = ".title pvasim\n"
        circuit += sCell
        circuit += "Xcell 1 0 " + sName + "\n"
        circuit += "Vtest 1 0 " + str(voltage) + " \n"
        circuit += spice_options
        circuit += ".op\n"
        circuit += ".end"

        plot = ng_sim(str(circuit))

        return plot["vtest#branch"].to_waveform()[0].value

    def powerAtVoltage(self, voltage):
        return self.currentAtVoltage(voltage, unrestricted=True) * voltage

    def currentAtVoltageDark(self, voltage):

        """
        This function simulates the cell using ngSpice and determines the current delivered at the specified voltage.

        voltage : Voltage at which to simulate the cell.

        """

        sCell, sName = self.buildModel(dark=True)
        circuit  = ".title pvasim\n"
        circuit += sCell
        circuit += "Xcell 1 0 " + sName + "\n"
        circuit += "Vtest 1 0 " + str(voltage) + " \n"
        circuit += spice_options
        circuit += ".op\n"
        circuit += ".end"

        plot = ng_sim(str(circuit))

        return plot["vtest#branch"].to_waveform()[0].value

    def calcIVCurve(self, step=0.01):

        """
        This function determines the IV-curve of the solar cell. For a list of considered physical parameters,
        refer to currentAtVoltage. The IV-curve is only calculated (not plotted) and returned as a pandas DataFrame.
        Simulation is always done from 0V to V_OC in the specified stepping (0.01V by standard). Decreasing stepping
        increases runtime.

        step : Voltage step

        """

        model, config, isc, imp, vmp, voc = self.prepareModel()
        sCell, sName = self.modelToArguments(model, config, isc, imp, vmp, voc, name=None, dark=False)
        voc_stop = math.floor(voc / step) * step

        circuit = ".title pvasim\n"
        circuit += sCell
        circuit += "Xcell 1 gnd " + sName + " \n"
        circuit += "Vtest 1 0 " + str(0) + "V\n"
        circuit += "Rconverge 1 0 " + str(10 ** 12) + "Ohm\n"
        circuit += spice_options
        circuit += ".dc Vtest " + str(step) + " " + str(voc_stop) + " " + str(step) + "\n"
        circuit += ".end"

        plot = ng_sim(str(circuit))

        current = np.array(plot["vtest#branch"].to_waveform())
        voltage = np.array(plot["v-sweep"].to_waveform())

        current = np.append(current, (isc, 0))
        voltage = np.append(voltage, (0, voc))

        df = pd.DataFrame(index=voltage.ravel())
        df["current"] = current
        df["power"] = df.index * df["current"]
        df = df[df["current"] >= 0]
        df.index.name = "voltage"
        df = df.sort_index()

        return df


    def calcIVCurveDark(self, v_min, v_max, step=0.01):

        """

        This function determines the IV-curve of the solar cell. For a list of considered physical parameters,
        refer to currentAtVoltage. The IV-curve is only calculated (not plotted) and returned as a pandas DataFrame.
        Simulation is always done from 0V to V_OC in the specified stepping (0.01V by standard). Decreasing stepping
        increases runtime.

        step : Voltage step

        """

        model, config, isc, imp, vmp, voc= self.prepareModel()
        sCell, sName = self.modelToArguments(model, config, isc, imp, vmp, voc, name=None, dark=True)
        voc_stop = math.floor(v_max / step) * step

        circuit = ".title pvasim\n"
        circuit += sCell
        circuit += "Xcell 1 gnd " + sName + " \n"
        circuit += "Vtest 1 0 " + str(0) + "V\n"
        circuit += "Rconverge 1 0 " + str(10 ** 12) + "Ohm\n"
        circuit += spice_options
        circuit += ".dc Vtest " + str(v_min) + " " + str(voc_stop) + " " + str(step) + "\n"
        circuit += ".end"

        plot = ng_sim(str(circuit))

        current = np.array(plot["vtest#branch"].to_waveform())
        voltage = np.array(plot["v-sweep"].to_waveform())

        df = pd.DataFrame(index=voltage.ravel())
        df["current"] = current
        df.index.name = "voltage"
        df = df.sort_index()

        return df


    def IVCurve(self, figsize=(15, 5), step=0.01):

        """
        This function calculates and plots the IV-Curve of the cell.

        figsize : size of the figure, given in brackets, e.g. (15,5)

        step : stepping of Voltage, as used by currentAtVoltage
        """

        df = self.calcIVCurve(step=step)
        IVPlot(df, figsize=figsize)


    def calcVoc(self):

        """
        This function simulates the cell using ngSpice and determines the current delivered at the specified voltage.

        voltage : Voltage at which to simulate the cell.

        """

        sCell, sName = self.buildModel()

        circuit = ".title pvasim\n"
        circuit += sCell
        circuit += "Xcell 1 gnd " + sName + "\n"
        circuit += spice_options
        circuit += ".op\n"
        circuit += ".end\n"

        plot = ng_sim(str(circuit))

        return plot["V(1)"].to_waveform()[0].value


    def calcIsc(self):
        """
        calculates isc
        """
        return self.currentAtVoltage(0)

    def calcMP(self, step=0.01):

        df = self.calcIVCurve(step=step)
        mpp = df[df["power"] == df["power"].max()].reset_index().to_dict("records")[0]
        return {"voltage":mpp["voltage"], "current":mpp["current"], "power":mpp["power"]}


    def calcQuad(self):

        """
        This method calculates the four important electrical-characteristic parameters -- isc, voc, vmp and imp.

        pmp = vmp * imp per definition
        """

        mp = self.calcMP()

        return {"isc": self.calcIsc(),
                "voc": self.calcVoc(),
                "vmp": mp["voltage"],
                "imp": mp["current"],
                "pmp": mp["power"]
                }

    def showTempCoefficients(self):
        for mparam in ["isc", "imp"]:
            print(mparam, self.regressors[mparam+"_dt"](self.doses["i"]) )
        for mparam in ["vmp", "voc"]:
            print(mparam, self.regressors[mparam+"_dt"](self.doses["v"]) )


    def showRemainingFactors(self):
        for mparam in ["isc", "imp"]:
            print(mparam, self.regressors["r_"+mparam](self.doses["i"]) )
        for mparam in ["vmp", "voc"]:
            print(mparam, self.regressors["r_"+mparam](self.doses["v"]) )


    def showMacroParams(self):

        # fetch all input data safely
        config = deepcopy(self.config)
        lossesI["inherited_tilt"] = deepcopy(tilt)
        lossesI["inherited_season"] = deepcopy(self.season)
        lossI = np.product(list(lossesI.values()))
        lossV = np.product(list(lossesV.values()))

        # calculate imp_acc to formula found in excel pp
        config["imp_dt"] = self.regressors["imp_dt"](doses["i"])
        config["isc_dt"] = self.regressors["isc_dt"](doses["i"])

        if temperature > 0:
            imp_dt = config["imp_dt"]
        else:
            # OCR-REPAIR PLACEHOLDER: the original imp_dt expression for the
            # temperature<=0 branch (lines 665-667) was not photographed.
            # Restore the exact formula from the authoritative repo; this
            # placeholder only keeps the module importable/runnable.
            imp_dt = config["isc_dt"]
        lossesI["inherited_season"] = deepcopy(self.season)
        lossI = np.product(list(lossesI.values()))
        lossV = np.product(list(lossesV.values()))

        # calculate imp_acc to formula found in excel pp
        config["imp_dt"] = self.regressors["imp_dt"](doses["i"])
        config["isc_dt"] = self.regressors["isc_dt"](doses["i"])

        if temperature > 0:
            imp_dt = config["imp_dt"]
        else:
            imp_dt = (config["isc_dt"] * \
                     (-temperature) + config["imp_dt"] * config["t_ref"]) / \
                     (config["t_ref"] - temperature)

        # calculate cell properties at given dose and temperature
        isc = config["isc"] * self.regressors["r_isc"](doses["i"])
        isc = isc + self.regressors["isc_dt"](doses["i"]) * (temperature - config["t_ref"])

        imp = config["imp"] * self.regressors["r_imp"](doses["i"])
        imp = imp + imp_dt * (temperature - config["t_ref"])

        vmp = config["vmp"] * self.regressors["r_vmp"](doses["v"]) * (temperature - config["t_ref"])
        vmp = vmp + self.regressors["vmp_dt"](doses["v"]) * (temperature - config["t_ref"])

        voc = config["voc"] * self.regressors["r_voc"](doses["v"]) * (temperature - config["t_ref"])
        voc = voc + self.regressors["voc_dt"](doses["v"]) * (temperature - config["t_ref"])

        # determine correction factors for voltage in line with old PP
        if self.season != 0:
            vmp_correction = (1+(self.config["isc"]-self.config["imp"])/self.config["imp"])*np.log(self.season * tilt)
            voc_correction = (1+(self.config["vmp"]/self.config["voc"])*(self.config["isc"]-self.config["imp"])/self.config["imp"])*np.log(self.season * tilt)
        else:
            vmp_correction = 1
            voc_correction = 1

        # updated application of loss factors
        isc = isc * lossI
        imp = imp * lossI
        vmp = vmp * lossV * vmp_correction
        voc = voc * lossV * voc_correction

        return isc, imp, vmp, voc

    def copy(self):
        return deepcopy(self)

