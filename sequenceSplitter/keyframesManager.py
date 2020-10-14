class KeyframesManager(object):
    def __init__(self, engine, tk):
        self.engine = engine
        self.tk = tk
        self.context = self.engine.context
        self.latest_cutItems = \
            self.context_latest_cutItems(self.context)

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    @property
    def list_of_animCurves(self):
        return pm.ls(
            type=[
                'animCurveTT',
                'animCurveTL',
                'animCurveTA',
                'animCurveTU'
            ]
        )

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def context_latest_cut(self):
        result = None

        entity = "Cut"
        filters = [
            ["entity", "is", self.context.entity]
        ]
        fields = ["revision_number"]
        order = [
            {
                "field_name": "revision_number",
                "direction": "desc"
            }
        ]

        result = self.tk.shotgun.find_one(
            entity,
            filters,
            fields,
            order
        )
        return result

    #   . . . . . . . . . . . . . . . . . . . . . .

    def context_latest_cutItems(self, context):
        result = {}

        latest_cut = self.context_latest_cut()

        entity = "CutItem"
        filter = [
            ["cut", "is", latest_cut]
        ]

        fields = [
            "cut_item_in",
            "cut_item_out",
            "code",
            "cut_item_duration"
        ]

        list_of_cutItems = self.tk.shotgun.find(
            entity,
            filter,
            fields
        )

        for element in list_of_cutItems:
            result.update({
                element["code"]: {
                    "start": element["cut_item_in"],
                    "end": element["cut_item_out"],
                    "duration": element["cut_item_duration"]
                }
            })

        return result

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def limit_animation_curves(self, start, end):
        for animCurve in self.list_of_animCurves:
            self.insert_range_limit_keyframes(animCurve, start, end)
            self.remove_not_required_animation(animCurve, start, end)

    #   . . . . . . . . . . . . . . . . . . . . . .

    def insert_range_limit_keyframes(self, curve, start, end):

        pm.setKeyframe(
            curve, animated=True,
            insert=True, time=start
        )

        pm.setKeyframe(
            curve, animated=True,
            insert=True, time=end
        )

    #   . . . . . . . . . . . . . . . . . . . . . .

    def remove_not_required_animation(self, curve, start, end):
        global_infinity_range = 999999

        pm.cutKey(
            curve, animation="objects",
            time=(-global_infinity_range, start-1)
        )

        pm.cutKey(
            curve, animation="objects",
            time=(end+1, global_infinity_range)
        )

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def move_animation_with_cutItem_data(self, start, shot):

        shot_start = shot.getStartTime()
        shot_name = shot.getShotName()
        cutItem_start = \
            self.latest_cutItems[shot_name]["start"]

        amount = None

        if shot_start > cutItem_start:
            amount = cutItem_start - shot_start
        else:
            amount = shot_start - cutItem_start

        shot.sequenceStartFrame.set(
            shot.sequenceStartFrame.get() + amount)
        shot.sequenceEndFrame.set(
            shot.sequenceEndFrame.get() + amount)
        shot.startFrame.set(
            shot.startFrame.get() + amount)
        shot.endFrame.set(
            shot.endFrame.get() + amount)

        if amount == 0:
            message = "Shot node match cutItem data"
            print(message)
        else:
            message = \
                "Difference between shot data " + \
                "and cutItem data: {0}\n".format(amount) + \
                "animation curves will proceed to be moved."
            print(message)

            for animCurve in self.list_of_animCurves:
                pm.keyframe(
                    animCurve,
                    edit=True,
                    includeUpperBound=True,
                    relative=True,
                    option="insert",
                    timeChange=amount
                )
        