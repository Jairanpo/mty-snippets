import pymel.core as pm

try:
    pm.delete("sequencer1")
except:
    pass

sequencer = pm.createNode("sequencer")
manager = pm.ls(type="sequenceManager")[0]

list_of_shots = pm.ls(type="shot")

for index, shot in enumerate(list_of_shots):
    shot.message.disconnect()
    shot.message.connect(sequencer.shots[index])

sequencer.message.connect(manager.sequences[0])
