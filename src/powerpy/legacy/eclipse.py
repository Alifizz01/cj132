# -*- coding: utf-8 -*-


from astropy import units as u
from astropy.time import Time, TimeDelta
from astropy.coordinates import get_body_barycentric, ICRS, CartesianRepresentation
import numpy as np
import pandas as pd
import itertools
import math
from poliastro.twobody.propagation import propagate
from .definitions import L_Sun


def systemFrame(sat, bodies, start, steps, stepsize):

    tStep = TimeDelta(stepsize, scale="tdb", format="sec")
    tRunning = Time(start, scale="tdb")

    times = np.arange(0, steps, 1) * tStep + Time(start, scale="tdb")
    idx = [t.value for t in times]
    df = pd.DataFrame(idx, columns=["time"])
    df["time"] = pd.to_datetime(df["time"])

    pos_sat = []
    for x in range(steps):
        newPos = sat.propagate(tRunning)
        pos_sat.append(ICRS(newPos.represent_as(CartesianRepresentation)).cartesian)
        tRunning = tRunning + tStep

    psx = [p.x.to(u.m).value for p in pos_sat]
    psy = [p.y.to(u.m).value for p in pos_sat]
    psz = [p.z.to(u.m).value for p in pos_sat]

    psx = pd.DataFrame(psx, columns=["sat_x"])
    psy = pd.DataFrame(psy, columns=["sat_y"])
    psz = pd.DataFrame(psz, columns=["sat_z"])

    df = pd.concat((df, psx, psy, psz), axis=1)

    pos_sun = get_body_barycentric("sun", times)
    pos_sun = [ICRS(m).cartesian for m in pos_sun]

    psx = [p.x.to(u.m).value for p in pos_sun]
    psy = [p.y.to(u.m).value for p in pos_sun]
    psz = [p.z.to(u.m).value for p in pos_sun]

    psx = pd.DataFrame(psx, columns=["sun_x"])
    psy = pd.DataFrame(psy, columns=["sun_y"])
    psz = pd.DataFrame(psz, columns=["sun_z"])

    df = pd.concat((df, psx, psy, psz), axis=1)

    for x in range(len(bodies)):

        pos_obj = get_body_barycentric(bodies.index[x], times)

        pos_obj = [ICRS(m).cartesian for m in pos_obj]

        psx = [p.x.to(u.m).value for p in pos_obj]
        psy = [p.y.to(u.m).value for p in pos_obj]
        psz = [p.z.to(u.m).value for p in pos_obj]

        psx = pd.DataFrame(psx, columns=[bodies.index[x]+"_x"])
        psy = pd.DataFrame(psy, columns=[bodies.index[x]+"_y"])
        psz = pd.DataFrame(psz, columns=[bodies.index[x]+"_z"])

        df = pd.concat((df, psx, psy, psz), axis=1)

    df = df.set_index("time")

    return df



def eclipses(df, bodies):

    for x in range(len(bodies)):

        shader = bodies.index[x]
        R = bodies["radius"][shader]

        for idx, val in df.iterrows():

            p_sat = np.array((val["sat_x"], val["sat_y"], val["sat_z"]))
            p_sun = np.array((val["sun_x"], val["sun_y"], val["sun_z"]))
            p_bdy = np.array((val[shader+"_x"], val[shader+"_y"], val[shader+"_z"]))

            dist = np.linalg.norm(np.cross(p_sun-p_bdy,p_sat - p_sun)) / np.linalg.norm(p_sat - p_sun)

            print(dist)

def eclipses2hist(df, bodies):

    bundle = []

    for x in range(len(bodies)):

        body = bodies.index[x]
        condition = (df[body+"_eclipse"].values == 1)
        hist = np.array([ sum( 1 for _ in group ) for key, group in itertools.groupby( condition ) if key ])
        bundle.append(hist)

    bundle = [item for sublist in bundle for item in sublist]
    bundle = np.array(bundle)

    step = df.index[1] - df.index[0]

    hist_values, hist_counts = np.unique(bundle, return_counts=True)
    hist = pd.DataFrame(hist_counts, index=hist_values*step, columns=["Count"])
    hist.index.name = "Duration"

    return hist

def solarIntensity(df, bodies=None):

    df["sun_dist"] = ((df["sat_x"] - df["sun_x"])**2 + \
                     (df["sat_y"] - df["sun_y"])**2 + \
                     (df["sat_z"] - df["sun_z"])**2 )**0.5

    df["sun_dist"] = df["sun_dist"]

    df["sun_intensity"] = L_Sun / (4 * np.pi * (df["sun_dist"]**2))

    if bodies is not None:
        for x in range(len(bodies)):
            df.loc[df[bodies.index[x] + "_eclipse"]==1, "sun_intensity"] = 0

    #df = df.drop(columns=["sun_dist"])

    return df


def albedoIntensity(df, bodies):

    print("FUNCTION ERRONEOUS!!!!!")
    for x in range(len(bodies)):

        body = bodies.index[x]

        radius = bodies["radius"][body] * 1000
        albedo = bodies["albedo"][body]

        df["dist_body_sun"] = (df[body+"_x"] - df["sun_x"])**2 + \
                              (df[body+"_y"] - df["sun_y"])**2 + \
                              (df[body+"_z"] - df["sun_z"])**2

        df["dist_body_sat"] = (df["sat_x"] - df[body+"_x"])**2 + \
                              (df["sat_y"] - df[body+"_y"])**2 + \
                              (df["sat_z"] - df[body+"_z"])**2

        df["dist_body_sun"] = df["dist_body_sun"]**0.5
        df["dist_body_sat"] = df["dist_body_sat"]**0.5

        df["dist_body_sun"] = df["dist_body_sun"]
        df["dist_body_sat"] = df["dist_body_sat"]

        df["sun_intensity_body"] = L_Sun / (df["dist_body_sun"]**2)

        df[body+"_albedo"] = albedo * df["sun_intensity_body"] * (radius**2 / df["dist_body_sat"]**2 )
