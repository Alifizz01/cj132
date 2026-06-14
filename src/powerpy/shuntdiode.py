# -*- coding: utf-8 -*-
"""
Created on Thu Sep 19 11:53:58 2024

@author: o27477438
"""

from power.cell import cell
import hashlib

class shuntdiode(cell):

    def __init__(self, diode_type="open", localDiodeFile=False):
        super().__init__(cell_type=None, model="RSeriesModel", diode_type=diode_type,
                         localCellFile=False, localDiodeFile=localDiodeFile)

        self.type = "shuntdiode"


    def prepareModel(self):

        """
        This method compiles all the needed parameters needed to build the simulation model in ngspice into the output
        """

        return None, None, None, None, None, None

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
        # add interconnectors
        args["i0_diode"] = self.config["diode_i0"]
        args["n_diode"] = self.config["diode_n"]
        args["rs_diode"] = self.config["diode_rs"]

        # create hash for cell name
        if name is None:
            name = [str(args[key]) for key in args] + [self.diode]
            name = hashlib.md5(str.encode(",".join(name))).hexdigest()

        # create spice model as string
        model = ".subckt " + name + " high low\n"
        model += "DD_Shunt_" + name + " low high Ds_" + name + "\n"
        model += ".model Ds_" + name + " D (IS=" + str(args["i0_diode"]) + " A n=" + str(args["n_diode"]) + \
                " Rs=" + str(args["rs_diode"]) + ")\n"
        model += ".ends " + name + "\n"

        return model, name

    def buildModel(self, name=None, dark=False):

        """
        This function is basically 'prepareModel' and 'modelToArguments' in a single step.
        """

        model, config, isc, imp, vmp, voc = self.prepareModel()
        model, cName = self.modelToArguments(model, config, isc, imp, vmp, voc, name=name, dark=dark)

        return model, cName



    def currentAtVoltageDark(self, voltage):
        return None

    def calcIVCurve(self, step=0.01):
        return None

    def calcIVCurveDark(self, v_min, v_max, step=0.01):
        return None

    def IVCurve(self, figsize=(15, 5), step=0.01):
        return None

    def calcVoc(self):
        return None

    def calcIsc(self):
        return None

    def calcMP(self, step=0.01):
        return None

    def calcQuad(self):
        return None
