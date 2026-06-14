# -*- coding: utf-8 -*-
"""
Created on Tue Nov 27 15:30:10 2018

@author: o27477438
"""

import numpy as np
import pandas as pd

# definitions for thermal model
T_0 = np.float64(-273.15)
T_Space = np.float64(2.7)
sigma = np.float64(5.670367 * 10 ** -8)

# definitions for circuit simulation
kB = np.float64(1.38064852 * 10 ** -23)  # J/K
e = np.float64(1.60217662 * 10 ** -19)   # C
T_Circuit = 300 # K
V_T_Spice = kB * T_Circuit / e

# spice_options = ""
# spice_options += ".option rseries = 1.0e-4 \n"
# spice_options += ".options savecurrents \n"
# spice_options += ".option itl1=1000 \n"
# spice_options += ".option itl2=10000 \n"
# spice_options += ".option rshunt = 1.0e9 \n"

spice_options = ""
spice_options += ".option rseries = 1.0e-4 \n"
spice_options += ".options savecurrents \n"
spice_options += ".option itl1=1000 \n"
spice_options += ".option itl2=10000 \n"
spice_options += ".option rshunt = 1.0e7 \n"

# general definitions
B_0 = 1367

gCases = {}
gCases["SS"] = {"P_Sun": 0.967, "P_Albedo": 0, "angle": -23.45}
gCases["WS"] = {"P_Sun": 1.034, "P_Albedo": 0, "angle":  23.45}
gCases["VEX"] = {"P_Sun": 1.008, "P_Albedo": 0, "angle": 0}
gCases["AEX"] = {"P_Sun": 0.993, "P_Albedo": 0, "angle": 0}

# definitions for eclipses and orbits
L_Sun = (3.828 * 10 ** 26)


def bodies(names):
    bodies = ["earth", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune"]

    bodies = pd.DataFrame(index=bodies)

    bodies.loc["earth", "radius"] = 6378.14
    bodies.loc["moon", "radius"] = 1738
    bodies.loc["mercury", "radius"] = 2400
    bodies.loc["venus", "radius"] = 6052
    bodies.loc["mars", "radius"] = 3390
    bodies.loc["jupiter", "radius"] = 71492
    bodies.loc["saturn", "radius"] = 60268
    bodies.loc["uranus", "radius"] = 25559
    bodies.loc["neptune", "radius"] = 24766

    # bond albedo
    bodies.loc["earth", "albedo"] = 0.306
    bodies.loc["moon", "albedo"] = 0.123
    bodies.loc["mercury", "albedo"] = 0.119
    bodies.loc["venus", "albedo"] = 0.750
    bodies.loc["mars", "albedo"] = 0.250
    bodies.loc["jupiter", "albedo"] = 0.343
    bodies.loc["saturn", "albedo"] = 0.342
    bodies.loc["uranus", "albedo"] = 0.290
    bodies.loc["neptune", "albedo"] = 0.310

    return bodies.loc[names, :]

