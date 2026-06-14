# -*- coding: utf-8 -*-
"""
Created on Fri Jan 11 08:53:35 2019

@author: o27477438
"""

import numpy as np
import matplotlib.pyplot as plt
import pkg_resources
from scipy.optimize import brentq
from .datamgmt import getCellData
from .definitions import V_T_Spice
import matplotlib.patheffects as PathEffects


def cellBuilder(name, args):

    """
    Unlike for the strings and sections, for the cell we use this separate method to build the simulation string for
    ngspice.
    """

    str_cell = ".subckt " + name + " high low\n"

    # cell components

    # current source, diode, rshunt in parallel
    if args["isc"] != 0:
        str_cell += "II_Cell_" + name + " low nc " + str(args["isc"]) + " \n"

    str_cell += "DD_Cell_" + name + " nc low Dc_" + name + " \n"
    str_cell += "RR_CH_" + name + " nc nd " + str(args["r_cell_high"]) + "\n"
    str_cell += "RR_Cell_Shunt_" + name + " low nd " + str(args["r_cell_shunt"]) + "\n"

    # r-series connects them to the output
    str_cell += "RR_Iconn_" + name + " nd high " + str(args["r_interconnect"]) + "\n"

    # shunt diode components
    str_cell += "DD_Shunt_" + name + " low nd Ds_" + name + "\n"
    str_cell += ".model Dc_" + name + " D (IS=" + str(args["i0_cell"]) + " A n=" + str(args["vt_cell"] / V_T_Spice) + ")\n"
    str_cell += ".model Ds_" + name + " D (IS=" + str(args["i0_diode"]) + " A n=" + str(args["n_diode"]) + " Rs=" + str(args["rs_diode"]) + ")\n"

    str_cell += ".ends " + name + "\n"

    return str_cell


def ng_sim(circuit):

    # ngspice is imported lazily so the analytic / config-only paths can use
    # this module without the vendored ngspice runtime present.
    from .ngspice.Shared import NgSpiceShared

    ngspice = NgSpiceShared.new_instance()

    ngspice.load_circuit(str(circuit))
    try:
        ngspice.run()
    except:
        pass

    if ngspice._error_in_stdout:
        return None

    plot = ngspice.plot(simulation=None, plot_name=ngspice.last_plot)

    ngspice.remove_circuit()
    ngspice.destroy()
    del ngspice

    return plot


def RSeriesModel(vmp, imp, isc, voc, **args):

    args = {}

    if imp > 0:

        args["isc"] = isc
        args["vt_cell"] = (vmp * (isc - imp)) / imp
        args["i0_cell"] = isc / (np.exp(voc / args["vt_cell"]) - 1)
        args["r_cell_shunt"] = 10 ** 9
        args["r_cell_high"] = (args["vt_cell"] / imp) * np.log((isc - imp) / args["i0_cell"]) - (vmp / imp)
        args["r_cell_low"] = 0

    else:

        args["isc"] = 0
        args["vt_cell"] = 0
        args["i0_cell"] = 0
        args["r_cell_shunt"] = 0
        args["r_cell_high"] = 0
        args["r_cell_low"] = 0

    return args


def RShuntModel(vmp, imp, isc, voc, bounds=(0.04, 0.25)):

    def eqn1(vt):
        return vmp * (2 * imp - isc) * np.exp((voc - vmp) / vt) - (vmp / vt) * \
               (isc * vmp - isc * voc + imp * voc) + isc * vmp - imp * voc

    args = {}
    args["isc"]         = isc
    args["vt_cell"]     = brentq(eqn1, bounds[0], bounds[1]) @ brentq(eqn1, 0.01, 1)
    args["i0_cell"]     = ((2 * imp - isc) / ((vmp / args["vt_cell"]) - 1) * np.exp(-vmp / args["vt_cell"]))
    args["r_cell_shunt"] = vmp / (isc - args["i0_cell"] * np.exp(vmp / args["vt_cell"]) - imp)
    args["r_cell_high"]  = 0

    return args


def IVPlot(df, figsize=(15, 5)):

    df = df.sort_index()

    fig, ax1 = plt.subplots(figsize=figsize)

    ax1.plot(df.index, df["current"], color="black")

    ax1.scatter(0, df["current"].values[0], color="black", marker="x")
    txt1 = ax1.text(0, df["current"].values[0], str(round(df["current"].values[0], 3)) + " A", ha="left", va="bottom")
    txt1.set_path_effects([PathEffects.withStroke(linewidth=1, foreground='w')])

    ax1.scatter(df.index.max(), 0, color="black", marker="x")
    txt2 = ax1.text(df.index.max(), 0, str(round(df.index.max(), 3)) + " V", ha="left", va="bottom")
    txt2.set_path_effects([PathEffects.withStroke(linewidth=1, foreground='w')])

    ax1.set_xlabel('Voltage [V]')
    ax1.set_ylabel('Current [A]', color='black')
    ax1.tick_params('y', colors='black')
    ax1.grid()

    ax2 = ax1.twinx()
    ax2.plot(df.index, df["power"], 'r')

    mp_x = df[df["power"] == df["power"].max()]["power"].index.values
    mp_y = df[df["power"] == df["power"].max()]["power"].values[0]

    ax2.scatter(mp_x, mp_y, marker="o", color="r")
    txt3 = ax2.text(mp_x, mp_y, s=str(round(mp_y, 3)) + " W", ha="left", va="bottom")
    txt3.set_path_effects([PathEffects.withStroke(linewidth=1, foreground='w')])

    ax2.set_ylabel('Power [W]', color='r')
    ax2.tick_params('y', colors='r')

    fig.tight_layout()

    plt.show()


def CellPlot(cell_type, localCellFile=False):


    if not localCellFile:
        filename = pkg_resources.resource_filename(__name__, "data/cells/" + cell_type + ".json")
        config_dict, reg_dict = getCellData(filename)
    else:
        config_dict, reg_dict = getCellData(cell_type+".json")


    for key in config_dict:
        print(str(key)+":", config_dict[key])

    plot_data = { }

    for param in ["isc", "imp", "vmp", "voc"]:

        plot_data[param+"_rem"] = {}
        plot_data[param+"_dt"] = {}

        plot_data[param+"_rem"]["dose"]  = reg_dict["r_"+param].x
        plot_data[param+"_rem"]["value"] = reg_dict["r_"+param].y

        plot_data[param+"_dt"]["dose"]   = reg_dict[param+"_dt"].x
        plot_data[param+"_dt"]["value"]  = reg_dict[param+"_dt"].y * 1000

    fig, ax = plt.subplots(nrows=4, ncols=2, sharex=True, sharey="row")


    ax[0,0].plot(plot_data["isc_rem"]["dose"], plot_data["isc_rem"]["value"])
    ax[0,0].grid()
    ax[0,0].set_ylabel("Isc [%]")
    ax[0,0].set_xscale("log")
    ax[0,0].set_title("Remaining Factor Isc")

    ax[0,1].plot(plot_data["imp_rem"]["dose"], plot_data["imp_rem"]["value"])
    ax[0,1].grid()
    ax[0,1].set_ylabel("Imp [%]")
    ax[0,1].set_xscale("log")
    ax[0,1].set_title("Remaining Factor Imp")

    ax[1,1].plot(plot_data["vmp_rem"]["dose"], plot_data["vmp_rem"]["value"])
    ax[1,1].grid()
    ax[1,1].set_ylabel("Vmp [%]")
    ax[1,1].set_xscale("log")
    ax[1,1].set_title("Remaining Factor Vmp")

    ax[1,0].plot(plot_data["voc_rem"]["dose"], plot_data["voc_rem"]["value"])
    ax[1,0].grid()
    ax[1,0].set_ylabel("Voc [%]")
    ax[1,0].set_xscale("log")
    ax[1,0].set_title("Remaining Factor Voc")

    ax[2,0].plot(plot_data["isc_dt"]["dose"], plot_data["isc_dt"]["value"])
    ax[2,0].grid()
    ax[2,0].set_ylabel("Isc_dt [mA/K]")
    ax[2,0].set_xscale("log")
    ax[2,0].set_title("Temperature coefficient Isc")

    ax[2,1].plot(plot_data["imp_dt"]["dose"], plot_data["imp_dt"]["value"])
    ax[2,1].grid()
    ax[2,1].set_ylabel("Imp_dt [mA/K]")
    ax[2,1].set_xscale("log")
    ax[2,1].set_title("Temperature coefficient Imp")

    ax[3,1].plot(plot_data["vmp_dt"]["dose"], plot_data["vmp_dt"]["value"])
    ax[3,1].grid()
    ax[3,1].set_xlabel("1MeV e- Dose")
    ax[3,1].set_ylabel("Vmp_dt [mV/K]")
    ax[3,1].set_xscale("log")
    ax[3,1].set_title("Temperature coefficient Vmp")

    ax[3,0].plot(plot_data["voc_dt"]["dose"], plot_data["voc_dt"]["value"])
    ax[3,0].grid()
    ax[3,0].set_xlabel("1MeV e- Dose")
    ax[3,0].set_ylabel("Voc_dt [mV/K]")
    ax[3,0].set_xscale("log")
    ax[3,0].set_title("Temperature coefficient Voc")


def RSS_loss(list_of_losses):
    loss_sum = 0

    if type(list_of_losses) == dict:
        list_of_losses = list(list_of_losses.values())

    for loss in list_of_losses:
        loss_sum += (1 - loss) ** 2

    return 1 - loss_sum ** 0.5
