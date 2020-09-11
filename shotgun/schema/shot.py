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


pp = pprint.PrettyPrinter(indent=2, width=70)

sg = shotgun_api3.Shotgun(
    "https://mightyanimation.shotgunstudio.com",
    login="jair.anguiano",
    password="$MightyAnimation7362891!"
)

schema = sg.schema_field_read("Shot")

path = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(path, "log.json"), "w") as outfile:
    json.dump(schema, outfile, indent=4, sort_keys=True)


print(path)
# pp.pprint(schema)
