# === MISSING: lines 1-3 not photographed ===

@author: o27477438
"""

from .definitions import T_0, sigma, T_Space
from scipy.optimize import fsolve

def thermal_viewfactor(P_Sun, P_Albedo, P_IR, P_Elec, front_side, rear_side, C_Cond, tilt,
                       view_planet=0, temp_planet=T_Space):

    """
    This is thermal test.
    """

    def thermalF(T_tuple):

        Tn1, Tn2 = T_tuple

        P_Front_abs = (front_side["alpha"] * front_side["area"]).sum() * P_Sun * tilt

        R_Front_emi =     view_planet * (front_side["epsilon"] * front_side["area"]).sum() * sigma * ((Tn1 - T_0) ** 4 - T_Space ** 4) + \\
                      (1 - view_planet) * (front_side["epsilon"] * front_side["area"]).sum() * sigma * ((Tn1 - T_0) ** 4 - T_Space ** 4)

        P_Rear_abs = P_Albedo * rear_side["alpha"]   * rear_side["area"] * tilt + \\
                          | P_IR     * rear_side["epsilon"] * rear_side["area"] * tilt

        R_Rear_emi = sigma * rear_side["epsilon"] * rear_side["area"] * ((Tn2 - T_0) ** 4 - T_Space ** 4)

        R_Cond     = C_Cond * rear_side["area"] * (Tn2 - Tn1)

        node1 = P_Front_abs - R_Front_emi - P_Elec + R_Cond
        node2 = P_Rear_abs - R_Rear_emi - R_Cond

        return (node1, node2)

    Res_tuple, infodict, ier, mesg = fsolve(thermalF, (0, 0), full_output=True)

    T1, T2 = Res_tuple

    return {"T_Front": T1, "T_Rear": T2}

def thermal_extracted_viewfactor(Tn1, P_Sun, P_Albedo, P_IR, front_side, rear_side, C_Cond, tilt):
def thermal_extracted_viewfactor(Tn1, P_Sun, P_Albedo, P_IR, front_side, rear_side, C_Cond, tilt):

    """
    This is thermal test.
    """

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
