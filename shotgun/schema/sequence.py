# -*- coding: utf-8 -*-
# Standard library:
import pprint
import json
import os
#   .   .   .   .   .   .   .   .   .   .   .
# Third party:
import shotgun_api3
#   .   .   .   .   .   .   .   .   .   .   .
# Project:
# ================================================================

"""    

        The following snippet of code gets the assets
        and shots associated with a sequence code:

"""


pp = pprint.PrettyPrinter(indent=2, width=70)

sg = shotgun_api3.Shotgun(
    "https://mightyanimation.shotgunstudio.com",
    login="jair.anguiano",
    password="$MightyAnimation7362891!"
)


entity = "Sequence"
code = "e105_drt010"
filters = [["code", "is", code]]
fields = ["assets", "shots"]

schema = sg.find(entity, filters, fields)

path = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(path, entity, code, "linked_entities.json")
os.makedirs(os.path.dirname(path))
with open(path, "w") as outfile:
    json.dump(schema, outfile, indent=4, sort_keys=True)
