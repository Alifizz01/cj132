# -*- coding: utf-8 -*-
"""
Created on Fri Jan 18 07:53:39 2019

@author: o27477438
"""

import pandas as pd
import numpy as np
import math

from copy import deepcopy

from scipy.optimize import minimize
from .definitions import spice_options, V_J_Spice
from .electric import IVPlot, ng_sim
from .datamgmt import getDiodeData

import pkg_resources

class string():

    def __init__(self, tCells, diode_type, tResistance=0, n_diodes_series=1, n_diodes_parallel=1, localDiodeFile=False):

        """
        The string constructor
        """

        self.cells = tCells
        self.resistance = tResistance

        if not localDiodeFile:
            filename = pkg_resources.resource_filename(__name__, "data/diodes/" + diode_type + ".json")
            dCfg = getDiodeData(filename)
        else:
            dCfg = getDiodeData(diode_type+".json")

        self.diode = dCfg
        self.n_diodes_series = n_diodes_series
        self.n_diodes_parallel = n_diodes_parallel

    @classmethod
    def fromSingleCell(cls, tCell, n_series, resistance=0, diodeType="LaRoche", n_diodes_series=1, n_diodes_parallel=1):

        """

        This function creates a string by cloning a pre-defined cell.

        tCell : cell instance

        n_serial : number of cells in series

        tResistance : intra-string resistance in Ohm.

        n_dioes : Number of blocking diodes in series.


        As an example, a string of 54 3G30 cells, with 0.5 Ohm resistance and 1 blocking diode in series is created
        using the following:

        >>> protoCell = cell("3G30", model="RSeriesModel")
        >>> protoString = string.fromSingleCell(protoCell, 54, 0.5, 1)

        Important: When adding a cell to a string, the reference is broken. That means, when adding the following line:

        >>> protoCell.addLossI("Random", 0.9)

        this will add a loss factor to the cell, but it is not going to change the parameters of
        the cells in the string (despite them originating from protoCell). The same behaviour applies when adding a string to a section and
        when adding a section to a panel.


        """

        tNames = [str(x) for x in range(n_series)]
        tCells = [deepcopy(tCell) for x in range(n_series)]
        return cls(tCells=dict(zip(tNames, tCells)), diode_type=diodeType,
                   tResistance=resistance, n_diodes_series=n_diodes_series,
                   n_diodes_parallel=n_diodes_parallel)

    @classmethod
    def fromCells(cls, cells, resistance=0, diodeType="LaRoche", n_diodes_series=1, n_diodes_parallel=1, cellNames=None):

        """
        This function creates a string by adding individual cells. This function has to be used when the string is homogeneous.
        As an example, consider a string that shall consist out of 10 cells of type 1 and 20 cells of type two. First, these cells
        are created on their own.

        >>> cell_1 = cell("...")
        >>> cell_2 = cell("...")

        Next, a list has to be created that contains the respective cells in the desired quantities. First, an empty list is created:

        >>> cell_list = []

        Then, using a loop, 10 cells of type 1 are added to the list:

        >>> for x in range(10):
        >>>     cell_list.append(cell_1)

        Then, 20 cells of type 2 are added to the same list:

        >>> for x in range(20):
        >>>     cell_list.append(cell_2)

        Now, the cell list can be used to create a new string of 0.5 Ohm resistance and 1 blocking diode:

        >>> protoString = string.fromCells(cell_list, 0.5, 1)

        The strings are named automatically starting with 0. That means, the cells of type 1 can be addressed by

        >>> protoString.cells["0"]

        to

        >>> protoString.cells["9"]

        and cells of type 2 by using

        >>> protoString.cells["10"]

        to

        >>> protoString.cells["29"]

        """

        if cellNames is None:
            tNames = [str(x) for x in range(len(cells))]
        else:
            tNames = cellNames

        tCells = cells

        return cls(tCells=dict(zip(tNames, tCells)), diode_type=diodeType,
                   tResistance=resistance, n_diodes_series=n_diodes_series,
                   n_diodes_parallel=n_diodes_parallel)

    def addLossI(self, name, factor, verbose=True):

        """

        This function adds a current loss factor to all cells of the string. Its interface is the same
        as the interface of the respective function on cell level.

        """

        for tCell in self.cells:
            self.cells[tCell].addLossI(name=name, factor=factor, verbose=verbose)

    def addLossV(self, name, factor, verbose=True):

        """

        This function adds a current loss factor to all cells of the string. Its interface is the same
        as the interface of the respective function on cell level.

        """

        for tCell in self.cells:
            self.cells[tCell].addLossV(name=name, factor=factor, verbose=verbose)

    def removeLosses(self):

        """
        This function removes all current loss factors of all cells in the string.
        """

        for tCell in self.cells:
            self.cells[tCell].removeLosses()

    def setDose(self, dose_i, dose_v):

        """

        This function sets the doses for all cells in the string. Its interface is the same as the interface of the
        respective function on cell level.

        """

        for tCell in self.cells:
            self.cells[tCell].setDose(dose_i=dose_i, dose_v=dose_v)

    def setTemperature(self, temperature):

        """

        This function sets the temperature for all cells in the string. Its interface is the same as the interface of the
        respective function on cell level.

        """

        for tCell in self.cells:
            self.cells[tCell].setTemperature(temperature)

    def setModel(self, model):

        """

        This function sets the simulation model for all cells in the string. Its interface is the same as the interface of the

        """
        This function sets the tilting angles, alpha and beta, for all cells in the string. Its interface is the same as the interface of the
        respective function on cell level.
        """

        for tCell in self.cells:
            self.cells[tCell].setAngles(alpha, beta)

    def setSeasonAngle(self, season_angle):
        for tCell in self.cells:
            self.cells[tCell].setSeasonAngle(season_angle)

    def setCell(self, cell_type):

        """
        This function sets the cell type for all cells in the string. Its interface is the same as the interface of the
        respective function on cell level.
        """

        for tCell in self.cells:
            self.cells[tCell].setCell(cell_type)

    def setDiode(self, diode_type):
        for tCell in self.cells:
            self.cells[tCell].setDiode(diode_type)

    def setSeason(self, season):

        """
        This function sets the season for all cells in the string. Its interface is the same as the interface of the
        respective function on cell level.
        """

        for tCell in self.cells:
            self.cells[tCell].setSeason(season)

    def renameCell(self, name, newName):

        """

        This function changes the name of a cell

        name : current name of the cell

        newName : future name of the cell

        As an effect of this function, a cell is no longer addressed by:

        >>> protoString.cells[name]

        but by

        >>> protoString.cells[newName]


        """

        self.cells[newName] = self.cells[name]
        self.cells.pop(name)

    def removeCell(self, name):

        """

        This function removes a cell from a string using its name.

        """

        self.cells.pop(name)

    def buildModel(self, short=False, dark=False):

        """
        Just like buildModel from cell.py -- the method generates a string which is the input for ngspice simulation.
        """

        resistance = deepcopy(self.resistance)

        circuit = ".title pvasim\n"
        tNames = []

        cNode = 0

        # append set of cells according to string length
        for tCell in self.cells.values():

            tName = "x" + str(id(tCell))

            if tName not in tNames:
                tModel, _ = tCell.buildModel(name=tName, dark=dark)
                circuit += tModel
                tNames.append(tName)

            circuit += "XCell_No_" + str(cNode) + " " + str(cNode + 1) + " " + str(cNode) + " " + str(tName) + "\n"

            cNode += 1


        if not dark:

            # prepare prototype of blocking_diode
            circuit += ".model DBlock D (IS=" + str(self.diode["diode_i0"]) + " \
                A n=" + str(self.diode["diode_n"]) + ") + RS="+str(self.diode["diode_rs"])+")\n"

            # append as many diodes as there are
            for d_counter in range(self.n_diodes_series):

                diode_start_node = "BD_intermed_" + str(d_counter)
                diode_stop_node = "BD_intermed_" + str(d_counter + 1)

                if d_counter == 0:
                    diode_start_node = str(cNode)

                if d_counter == self.n_diodes_series - 1:
                    diode_stop_node = "BD"

                for dp_counter in range(self.n_diodes_parallel):
                    circuit += "DDBlock_" + str(d_counter) + "_" + str(dp_counter) + " \
                    " + " + diode_start_node + " " + diode_stop_node + " DBlock\n"

            # if the string shall have resistance, consider it
            if short:
                circuit = circuit.replace(" BD ", " " + str(0) + " ")
            else:
                circuit += "RString1 0 out1 " + str(resistance / 2) + "Ohm\n"
                if self.n_diodes_series > 0:
                    circuit += "RString2 BD out2 " + str(resistance / 2) + "Ohm\n"
                else:
                    circuit += "RString2 "+str(cNode)+" out2 " + str(resistance / 2) + "Ohm\n"

        return circuit

    def currentAtVoltage(self, voltage):

        """
        This function returns the string current at a certain voltage. It considers the string's resistance (and blocking diodes),
        but despite that is equal in its functioning to the respective method on string level.
        """

        circuit = self.buildModel()

        circuit += "Vtest out2 out1 " + str(voltage) + "  \n"
        circuit += "Rconverge out2 out1 " + str(10 ** 9) + " \n"
        circuit += ".op \n"
        circuit += ".end \n\n"

        plot = ng_sim(circuit)

        return plot["vtest#branch"].to_waveform()[0].value

    def powerAtVoltage(self, voltage):
        return self.currentAtVoltage(voltage) * voltage

    def currentAtVoltageDark(self, voltage, verbose=True):


        """
        This function returns the string current at a certain voltage. It considers the string's resistance (and blocking diodes),
        but despite that is equal in its functioning to the respective method on string level.
        """

        if verbose:
            print("DIV Calculation ignores blocking diode!")

        last_node = str(len(self.cells))

        circuit = self.buildModel(dark=True)
        circuit += "Vtest "+last_node+" 0 " + str(voltage) + "  \n"
        #circuit += "Rconverge "+last_node+" 0 " + str(10 ** 9) + " \n"
        circuit += ".op \n"
        circuit += ".end \n\n"

        plot = ng_sim(circuit)

        return plot["vtest#branch"].to_waveform()[0].value

    def calcIVCurve(self, step=0.01):

        """
        This function calculates the IV-curve of the string as pandas DataFrame. It considers (blocking diodes and) string resistance, but despite
        that is the same as the respective function on cell level.
        """
        This function calculates the IV-curve of the string as pandas DataFrame. It considers (blocking diodes and) string resistance, but despite
        that is the same as the respective function on cell level.
        """

        circuit = self.buildModel()

        # determine voc
        voc = self.calcVoc()
        voc_stop = math.ceil(voc / step) * step

        # simulate circuit
        circuit += "Vtest out2 out1 0V \n"
        circuit += "Rconverge out2 out1 " + str(10 ** 9) + "Ohm\n"
        circuit += ".dc Vtest 0 " + str(voc_stop) + " " + str(step) + " \n"
        circuit += ".end"

        plot = ng_sim(str(circuit))

        i = plot["vtest#branch"].to_waveform().tolist()
        v = np.array(plot["out2"].to_waveform().tolist()) - np.array(plot["out1"].to_waveform().tolist())
        v = list(v)

        df = pd.DataFrame()
        df["current"] = i
        df["voltage"] = v
        df["power"] = df["voltage"] * df["current"]
        df = df.set_index("voltage")

        return df

    def calcIVCurveDark(self, v_min, v_max, step=0.01, verbose=True):

        """
        This function calculates the IV-curve of the string as pandas DataFrame. It considers (blocking diodes and) string resistance, but despite
        that is the same as the respective function on cell level.
        """

        if verbose:
            print("DIV Calculation ignores blocking diode!")

        circuit = self.buildModel(dark=True)
        last_node = str(len(self.cells))

        # determine max voltage step
        voc_stop = math.ceil(v_max / step) * step

        # simulate circuit
        circuit += "Vtest "+last_node+" 0 0V \n"
        circuit += "Rconverge "+last_node+" 0 " + str(10 ** 5) + "Ohm\n"
        circuit += ".dc Vtest "+str(v_min)+" " + str(voc_stop) + " " + str(step) + "\n"
        circuit += ".end"

        plot = ng_sim(str(circuit))

        i = plot["vtest#branch"].to_waveform().tolist()
        v = plot["V("+last_node+")"].to_waveform().tolist()

        df = pd.DataFrame()
        df["current"] = i
        df["voltage"] = v
        df = df.set_index("voltage")

        return df


    def calcMP(self, step=0.1):

        """
        This function finds the maximum power point of the string. It considers (blocking diode and) string resistance.
        For further reference see the same method on cell level.
        """

        df = self.calcIVCurve(step=step)
        mpp = df[df["power"] == df["power"].max()].reset_index().to_dict("records")[0]
        return {"voltage":mpp["voltage"], "current":mpp["current"], "power":mpp["power"]}


    def IVCurve(self, step=0.01, figsize=(15, 5)):

        """
        This function plots the IV curve of the string. It considers (blocking diode and) string resistance.
        For further reference see the same method on cell level.
        """

        df = self.calcIVCurve(step=step)
        IVPlot(df, figsize=figsize)
        This function plots the IV curve of the string. It considers (blocking diode and) string resistance.
        For further reference see the same method on cell level.
        """

        df = self.calcIVCurve(step=step)
        IVPlot(df, figsize=figsize)

    def calcQuad(self, step=0.1):

        mp = self.calcMP(step=step)

        return {"isc": self.calcIsc(),
                "voc": self.calcVoc(),
                "vmp": mp["voltage"],
                "imp": mp["current"],
                "pmp": mp["power"]
                }

    def calcVoc(self):
        circuit = self.buildModel()
        circuit += ".op \n"
        circuit += ".end \n"
        plot = ng_sim(str(circuit))
        return plot["out2"].to_waveform()[0].value

    def guessVoc(self):
        guessed_voc = 0
        for tCell in self.cells:
            model, config, isc, imp, vmp, voc = self.cells[tCell].prepareModel()
            guessed_voc += voc
        return guessed_voc


    def calcIsc(self):
        return self.currentAtVoltage(0)
