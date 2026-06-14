# -*- coding: utf-8 -*-
"""
Created on Fri Jan 18 07:54:06 2019

@author: o27477438
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import math

from copy import deepcopy

from scipy.optimize import minimize

from .string import string
from .electric import IVPlot, ng_sim
from .definitions import spice_options, V_T_Spice


class section():

    def __init__(self, tStrings=None, tResistance=None):
        """
        The constructor for sections
        """
        self.strings = tStrings
        self.resistance = tResistance

    @classmethod
    def fromSingleCell(cls, tCell, n_parallel, n_serial, resistance, diodeType):

        """
        This function creates a section from a defined cell. It therefore skips the need of creating strings, but does not allow
        for specifying intra-string resistances (these are all set to 0 Ohm here).

        tCell : Cell model

        n_parallel : Number of strings in parallel

        n_serial : Number of cell in series for each string

        resistance : Section resistance in Ohm.

        n_diodes : Number of blocking diodes per string.

        Strings are named numerically, starting from 0.
        Again, once a section has been created, changing properties of the cell has no effect on the section.

        """

        tString = string.fromSingleCell(tCell, n_serial, diodeType=diodeType)

        tNames = [str(x) for x in range(n_parallel)]
        tStrings = [deepcopy(tString) for x in range(n_parallel)]
        return cls(tStrings=dict(zip(tNames, tStrings)), tResistance=resistance)

    @classmethod
    def fromSingleString(cls, tstring, n_parallel, resistance):

        """

        This function creates a section by cloning a string.

        tString : String model

        n_parallel : Number of strings in parallel

        resistance : Section resistance in Ohm.

        Strings are named numerically, starting from 0.
        Again, once a section has been created, changing properties of the string has no effect on the section.

        """

        tNames = [str(x) for x in range(n_parallel)]
        tStrings = [deepcopy(tstring) for x in range(n_parallel)]
        return cls(tStrings=dict(zip(tNames, tStrings)), tResistance=resistance)

    @classmethod
    def fromStrings(cls, strings, resistance, names=None):
        """
        if names is None:
            tNames = [str(x) for x in range(len(strings))]
        else:
            tNames = names

        tStrings = strings  # deepcopy(strings)

        return cls(tStrings=dict(zip(tNames, tStrings)), tResistance=resistance)

    def addLossI(self, name, factor, verbose=True):
        for tString in self.strings:
            self.strings[tString].addLossI(name=name, factor=factor, verbose=verbose)

    def addLossV(self, name, factor, verbose=True):
        for tString in self.strings:
            self.strings[tString].addLossV(name=name, factor=factor, verbose=verbose)

    def removeLosses(self):
        for tString in self.strings:
            self.strings[tString].removeLosses()

    def setDose(self, dose_i, dose_v):
        for tString in self.strings:
            self.strings[tString].setDose(dose_i=dose_i, dose_v=dose_v)

    def setTemperature(self, temperature):
        for tString in self.strings:
            self.strings[tString].removeLosses()

    def setDose(self, dose_i, dose_v):
        for tString in self.strings:
            self.strings[tString].setDose(dose_i=dose_i, dose_v=dose_v)

    def setTemperature(self, temperature):
        for tString in self.strings:
            self.strings[tString].setTemperature(temperature)

    def setModel(self, model):
        for tString in self.strings:
            self.strings[tString].setModel(model)

    def setAngles(self, alpha, beta):
        for tString in self.strings:
            self.strings[tString].setAngles(alpha, beta)

    def setCell(self, cell_type):
        for tString in self.strings:
            self.strings[tString].setCell(cell_type)

    def setDiode(self, diode_type):
        for tString in self.strings:
            self.strings[tString].setDiode(diode_type)

    def setSeason(self, season):
        for tString in self.strings:
            self.strings[tString].setSeason(season)

    def setSeasonAngle(self, season_angle):
        for tString in self.strings:
            self.strings[tString].setSeasonAngle(season_angle)

    def renameString(self, name, newName):
        self.strings[newName] = self.strings[name]
        self.strings.pop(name)

    def removeString(self, name):
        self.strings.pop(name)

    def buildModel(self):

        circuit = ".title pvasim\n"
        resistance = deepcopy(self.resistance)
        tNames = []


        for tString in self.strings:

            tStringProt = str(tString).replace(" ", "_")

            cell_names_raw = list(self.strings[tString].cells.keys())
            cell_names = [x.replace(" ", "_") for x in cell_names_raw]

            diode_n = self.strings[tString].diode["diode_n"]
            diode_i0 = self.strings[tString].diode["diode_i0"]
            diode_n_series = self.strings[tString].n_diodes_series
            diode_n_parallel = self.strings[tString].n_diodes_parallel

            string_resistance = self.strings[tString].resistance

            for nCell in range(len(cell_names)):

                local_cell = self.strings[tString].cells[cell_names_raw[nCell]]
                tModel, tName = local_cell.buildModel(name=None)

                if tName not in tNames:
                    circuit += tModel
                    tNames.append(tName)

                if nCell == 0:
                    node_stop = "bottom"
                    node_start = "n_" + tStringProt + "_" + cell_names[nCell + 1]

                elif nCell == len(cell_names) - 1:
                    node_start = "top_" + tStringProt
                    node_stop = "n_" + tStringProt + "_" + cell_names[nCell]

                else:
                    node_stop = "n_" + tStringProt + "_" + cell_names[nCell]
                    node_start = "n_" + tStringProt + "_" + cell_names[nCell + 1]

                local_cell_name = "XCell_" + tStringProt + "_" + cell_names[nCell]
                circuit += local_cell_name + " " + str(node_start) + " " + str(node_stop) + " " + str(tName) + "\n"

            circuit += "RStringres_" + tStringProt + " " + "top_" + tStringProt + " " + "top_res_" + tStringProt + " " + str(
                string_resistance) + " \n"
            circuit += ".model DBlock_" + tStringProt + " D (IS=" + str(diode_i0) + " A n=" + str(diode_n) + ")\n"

            # append as many diodes as there are
            for d_counter in range(diode_n_series):
                diode_start_node = "BD_intermed_" + tStringProt + "_" + str(d_counter)
                diode_stop_node = "BD_intermed_" + tStringProt + "_" + str(d_counter + 1)

                if d_counter == 0:
                    diode_start_node = "top_res_" + tStringProt

                if d_counter == diode_n_series - 1:
                    diode_stop_node = "top"

                for dp_counter in range(diode_n_parallel):
                    local_diode_name = "DDBlock_" + tStringProt + "_" + str(d_counter) + "_" + str(dp_counter)
                    circuit += local_diode_name + " " + diode_start_node + " " + diode_stop_node + " DBlock_" + tStringProt + " \n"
                    circuit += "RP_" + local_diode_name + " " + " " + diode_start_node + " " + diode_stop_node + " 1.0e10 \n"

        circuit += "RSec_RTN bottom 0 " + str(resistance / 2) + " Ohm\n"
        circuit += "RSec_PWR top    out " + str(resistance / 2) + " Ohm\n"

        circuit += spice_options

        return circuit

    def currentAtVoltage(self, voltage):

        circuit = self.buildModel()
        circuit += "Vtest out 0 " + str(voltage) + " \n"
        circuit += "Rconverge out 0 " + str(10 ** 9) + " \n"
        circuit += ".op \n"
        circuit += ".end\n"

        plot = ng_sim(circuit)

        return plot["vtest#branch"].to_waveform()[0].value

    def powerAtVoltage(self, voltage):
        return self.currentAtVoltage(voltage) * voltage

    def calcIVCurve(self, step=0.1):

        circuit = self.buildModel()

        # determine voc
        voc = self.calcVoc()
        voc_stop = math.ceil(voc / step) * step

        # simulate circuit
        circuit += "Vtest out 0 0V \n"
        circuit += "Rconverge out 0 " + str(10 ** 9) + " Ohm\n"
        circuit += ".dc Vtest 0 " + str(voc_stop) + " " + str(step) + " \n"
        circuit += ".end"

        plot = ng_sim(str(circuit))

        i = plot["vtest#branch"].to_waveform().tolist()
        v = plot["out"].to_waveform().tolist()

        df = pd.DataFrame()
        df["current"] = i
        df["voltage"] = v
        df["power"] = df["voltage"] * df["current"]
        df = df.set_index("voltage")
        return df

    def calcMP(self, step=0.1):
        df = self.calcIVCurve(step=step)
        mpp = df[df["power"] == df["power"].max()].reset_index().to_dict("records")[0]
        return {"voltage": mpp["voltage"], "current": mpp["current"], "power": mpp["power"]}

    def IVCurve(self, step=0.1, figsize=(15, 5)):
        df = self.calcIVCurve(step=step)
        IVPlot(df, figsize=figsize)

    def guessVoc(self):
        guessed_vocs = []
        for tString in self.strings:
            guessed_vocs.append(self.strings[tString].guessVoc())
        return max(guessed_vocs)


    def calcVoc(self):

        voc_guess = self.guessVoc()
        circuit = self.buildModel()
        circuit += "Rconverge out 0 " + str(10 ** 8) + " \n"
        circuit += ".nodeset v(out)="+str(voc_guess)+" \n"
        circuit += ".op \n"
        circuit += ".end \n"
        plot = ng_sim(str(circuit))
        return plot["out"].to_waveform()[0].value

    def calcQuad(self, step=0.1):

        mp = self.calcMP(step=step)

        return {"isc": self.calcIsc(),
                "voc": self.calcVoc(),
                "vmp": mp["voltage"],
                "imp": mp["current"],
                "pmp": mp["power"],
                }

    def calcIsc(self):
        return self.currentAtVoltage(0)


    def cellArea(self):
        cellArea = 0
        for tString in self.strings:
            for tCell in self.strings[tString].cells:
                cellArea += self.strings[tString].cells[tCell].config["area"]

        return cellArea
