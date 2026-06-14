
import numpy as np
import matplotlib.pyplot as plt

rE     = 6378 # km
dSun   = 149600000
sat    = np.array([rE+200, 0, 0])
sun    = np.array([dSun*np.cos(30*np.pi/180), dSun*np.sin(30*np.pi/180), 0])
albedo = 0.3
p_sun  = 1370
acc    = int((10*10**6)**0.5) # deg per step
dA     = 4 * np.pi * rE * rE / acc / acc # größe flächenelement in km2
Ap     = 10/(1000**2) # 10 m2 in km2

pts = []
cs  = []

albedos = []

def check_sphere_crossing(start, target, radius):
    return np.dot(start, target - start) > 0

for lon in np.linspace(0, 360, acc, endpoint=False):
    for lat in np.linspace(0, 360, acc, endpoint=False): ## value of latitude only cover until 180 degress and 90 to -90.

        x = rE * np.cos(lat*np.pi/180) * np.cos(lon*np.pi/180)
        y = rE * np.cos(lat*np.pi/180) * np.sin(lon*np.pi/180)
        z = rE * np.sin(lat*np.pi/180)
        seg = np.array([x,y,z])

        sees_satellite  = check_sphere_crossing(seg, sat, rE)
        if not sees_satellite:
            continue

        sees_sun        = check_sphere_crossing(seg, sun, rE)
        if not sees_sun:
            continue

        cos_sun         = np.dot(seg, sun-seg) / ( np.linalg.norm(seg) * np.linalg.norm(sun-seg) )
        p_albedo_seg    = p_sun * cos_sun * albedo * dA / (2*np.pi) # can be / pi only, lambertian equation only need to be divided by 1 pi
        omega           = Ap / (np.linalg.norm(seg-sat)**2)
        irr_panel       = p_albedo_seg * omega

        albedos.append(irr_panel)
        pts.append(seg)
        cs.append(omega)


pts = np.array(pts)
sun_projection = rE * sun / np.linalg.norm(sun)

fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
radiators = ax.scatter(pts[:,0], pts[:,1], pts[:,2], c=cs, cmap="Reds")
ax.scatter(sat[0], sat[1], sat[2], color="red", marker="x")
ax.scatter(0, 0, 0, marker="o", color="black")
ax.plot([0, sun_projection[0]], [0, sun_projection[1]], [0, sun_projection[2]])
ax.plot([0, sat[0]], [0, sat[1]], [0, sat[2]])

fig.colorbar(radiators, shrink=0.85)

print("irr_received", sum(albedos))
