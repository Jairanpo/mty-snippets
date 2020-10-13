import pymel.core as pm
import sgtk

result = []
app = sgtk.platform.current_engine()

context = app.context

breakdown_entity = "CustomEntity30"

filters = [
    ["sg_shot", "is", context.entity]
]

fields = ["code", "sg_asset"]

breakdown = \
    app.shotgun.find(
        breakdown_entity, filters, fields
    )