import pymel.core as pm

# --------------------------------------
# Variables to replace:
prefix = "e000_cyc010"
number = "0010"
# --------------------------------------

shotcode = "{0}_{1}".format(prefix, number)

old_namespace = shotcode
new_namespace = "delete_{0}".format(number)

shot = pm.ls("*{0}*".format(old_namespace), type="shot")
shot[0].rename(shot[0].name().replace(old_namespace, new_namespace))


pm.namespace(rename=[old_namespace, new_namespace])

extra = ref_node = pm.ls("{0}*".format(old_namespace))
for each in extra:
    each.unlock()
    each.rename(each.name().replace(old_namespace, new_namespace))
