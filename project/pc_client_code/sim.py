import mujoco
import mujoco.viewer
import numpy as np
import matplotlib.pyplot as plt
import time

incline = np.pi/36
gz = -9.81*np.cos(incline)
gy = -9.81*np.sin(incline)

xml = f"""
<mujoco model="omni_robot">
    <compiler angle="degree" coordinate="local" inertiafromgeom="true"/>
    
    <option timestep="0.001" gravity="0 {gy} {gz}" integrator="RK4"/>

    <default>
        <geom contype="1" conaffinity="1" condim="3" friction="0 0 0"/>
    </default>
  
    <asset>
        <texture name="grid" type="2d" builtin="checker" width="512" height="512" rgb1=".1 .2 .3" rgb2=".2 .3 .4"/>
        <material name="grid" texture="grid" texrepeat="1 1" texuniform="true" reflectance=".2"/>
    </asset>
  
    <worldbody>
        <light directional="true" diffuse=".8 .8 .8" specular=".2 .2 .2" pos="0 0 5" dir="0 0 -1"/>
        <geom name="floor" type="plane" size="5 5 .1" material="grid"/>

        <body name="base">
            <geom name="table" type="box" size="0.975 0.41 0.015" pos="0.975 -0.41 0.015" rgba=".5 .5 .5 1" />
            <geom name="l_sigma" type="box" size="0.015 0.375 0.015" pos="0.015 -0.405 0.045" rgba="1 0 0 1" />
            <geom name="r_sigma" type="box" size="0.015 0.375 0.015" pos="0.925 -0.405 0.045" rgba="1 0 0 1" />
            <geom name="t_sigma" type="box" size="0.47 0.015 0.015" pos="0.47 -0.015 0.045" rgba="1 0 0 1" />
            <geom name="wood" type="box" size="0.47 0.02 0.02" pos="0.47 -0.8 0.05" rgba="0 1 0 1" />
            <geom name="seperator" type="box" size="0.01 0.3 0.01" pos="0.47 -0.480 0.04" rgba="0 0 1 1" />
        </body>

        <body name="pinpon">
            <freejoint/>
            <geom name="ball" type="sphere" size="0.02" pos="0.27 -0.3 0.05"/>
        </body name="pinpon">

  </worldbody>
</mujoco>
"""
            # <geom name="left_sigma" type="box" size="0.03 0.75 0.03" pos="0.015 -0.375 0.25" />

m = mujoco.MjModel.from_xml_string(xml)
d = mujoco.MjData(m)

with mujoco.viewer.launch_passive(m, d, show_right_ui=False) as viewer:
  start = time.time()
  while viewer.is_running():
    step_start = time.time()

    mujoco.mj_step(m, d)

    viewer.sync()

    time_until_next_step = m.opt.timestep - (time.time() - step_start)
    if time_until_next_step > 0:
      time.sleep(time_until_next_step)
  