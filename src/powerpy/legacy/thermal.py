# === MISSING: lines 1-2 not photographed ===
Created on Thu Nov 22 13:50:39 2018

@author: o27477438
"""

from .definitions import T_0, sigma, T_Space
from scipy.optimize import fsolve

def thermal(P_Sun, P_Albedo, P_IR, P_Elec, front_side, rear_side, C_Cond, tilt):

    def thermalF(T_tuple):
        # get temperatures from tuple
        Tn1, Tn2 = T_tuple

        P_Front_abs = (front_side["alpha"] * front_side["area"]).sum() * P_Sun * tilt
        R_Front_emi = (front_side["epsilon"] * front_side["area"]).sum() * sigma * ((Tn1 - T_0) ** 4 - T_Space ** 4)

        P_Rear_abs = P_Albedo * rear_side["alpha"] * rear_side["area"] * tilt + \\
                          | P_IR * rear_side["epsilon"] * rear_side["area"] * tilt
        R_Rear_emi = sigma * rear_side["epsilon"] * rear_side["area"] * ((Tn1 - T_0) ** 4 - T_Space ** 4)

        R_Cond = C_Cond * rear_side["area"] * (Tn2 - Tn1)

        node1 = P_Front_abs - R_Front_emi - P_Elec + R_Cond
        node2 = P_Rear_abs - R_Rear_emi - R_Cond

        return (node1, node2)

    Res_tuple, infodict, ier, mesg = fsolve(thermalF, (0, 0), full_output=True)

    T1, T2 = Res_tuple
    return {"T_Front": T1, "T_Rear": T2}


def thermal_thin(P_Sun, P_Albedo, P_IR, P_Elec, front_side, rear_side, tilt):

    def thermalF(T_tuple):

        Tn1 = T_tuple

        P_Front_abs = (front_side["alpha"] * front_side["area"]).sum() * P_Sun * tilt
        P_Front_abs = (front_side["alpha"] * front_side["area"]).sum() * P_Sun * tilt
        R_Front_emi = (front_side["epsilon"] * front_side["area"]).sum() * sigma * ((Tn1 - T_0) ** 4 - T_Space ** 4)

        P_Rear_abs = P_Albedo * rear_side["alpha"] * rear_side["area"] * tilt + \\
                          | P_IR * rear_side["epsilon"] * rear_side["area"] * tilt
        R_Rear_emi = sigma * rear_side["epsilon"] * rear_side["area"] * ((Tn1 - T_0) ** 4 - T_Space ** 4)

        node1 = P_Front_abs - R_Front_emi - P_Elec + P_Rear_abs - R_Rear_emi

        return node1

    Res_tuple, infodict, ier, mesg = fsolve(thermalF, (0), full_output=True)

    T1 = Res_tuple

    return {"T_Front": T1, "T_Rear": T1}


def thermal_extracted(Tn1, P_Sun, P_Albedo, P_IR, front_side, rear_side, C_Cond, tilt):

    def thermalF(val_tuple):

        P_Elec, Tn2 = val_tuple

        P_Front_abs = (front_side["alpha"] * front_side["area"]).sum() * P_Sun * tilt
        R_Front_emi = (front_side["epsilon"] * front_side["area"]).sum() * sigma * ((Tn1 - T_0) ** 4 - T_Space ** 4)

        P_Rear_abs = P_Albedo * rear_side["alpha"] * rear_side["area"] * tilt + \\
                          | P_IR * rear_side["epsilon"] * rear_side["area"] * tilt
        R_Rear_emi = sigma * rear_side["epsilon"] * rear_side["area"] * ((Tn2 - T_0) ** 4 - T_Space ** 4)

        R_Cond = C_Cond * rear_side["area"] * (Tn2 - Tn1)

        node1 = P_Front_abs - R_Front_emi - P_Elec + R_Cond
        node2 = P_Rear_abs - R_Rear_emi - R_Cond

        return (node1, node2)

    Res_tuple, infodict, ier, mesg = fsolve(thermalF, (0, 0), full_output=True)

    return Res_tuple[0]


def thermal_extracted_thin(Tn1, P_Sun, P_Albedo, P_IR, front_side, rear_side, tilt):

    def thermalF(val_tuple):

        P_Elec = val_tuple[0]

        P_Front_abs = (front_side["alpha"] * front_side["area"]).sum() * P_Sun * tilt
        R_Front_emi = (front_side["epsilon"] * front_side["area"]).sum() * sigma * ((Tn1 - T_0) ** 4 - T_Space ** 4)

    def thermalF(val_tuple):

        P_Elec = val_tuple[0]

        P_Front_abs = (front_side["alpha"] * front_side["area"]).sum() * P_Sun * tilt
        R_Front_emi = (front_side["epsilon"] * front_side["area"]).sum() * sigma * ((Tn1 - T_0) ** 4 - T_Space ** 4)

        P_Rear_abs = P_Albedo * rear_side["alpha"] * rear_side["area"] * tilt + \\
                          | P_IR * rear_side["epsilon"] * rear_side["area"] * tilt
        R_Rear_emi = sigma * rear_side["epsilon"] * rear_side["area"] * ((Tn1 - T_0) ** 4 - T_Space ** 4)

        node1 = P_Front_abs - R_Front_emi - P_Elec + P_Rear_abs - R_Rear_emi

        return node1


    Res_tuple, infodict, ier, mesg = fsolve(thermalF, (0), full_output=True)

    return Res_tuple[0]
