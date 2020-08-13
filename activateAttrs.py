# Copy and paste the following lines to toggle the
# DOF in all cameras:

import pymel.core as pm

huds = pm.ls("*:HUD_CTL")

for each in huds:
    each.DOF.set(not each.DOF.get())

# ================================================================
