# -*- coding: utf-8 -*-
# Standard library:
#   .   .   .   .   .   .   .   .   .   .   .
# Third party:
import pymel.core as pm
#   .   .   .   .   .   .   .   .   .   .   .
# Project:
# ================================================================


class BakeConstraints(object):

    def __init__(self):
        self.list_of_constraints = self.session_constraints()

    #   . . . . . . . . . . . . . . . . . . . . . .

    def process(self, start_frame=None, end_frame=None):
        control_constraint = []
        delete_constraint = []

        for constraint in self.list_of_constraints:
            print(constraint)
            list_of_connected_nodes = \
                pm.listConnections(
                    constraint,
                    source=True,
                    skipConversionNodes=True,
                    type='transform'
                )

            self.constraint_source(
                list_of_connected_nodes,
                constraint,
                control_constraint,
                delete_constraint
            )

            self.bake(
                start_frame,
                end_frame,
                control_constraint
            )

        pm.delete(delete_constraint)

    #   . . . . . . . . . . . . . . . . . . . . . .

    def session_constraints(self):
        result = []

        list_of_constraints_types = [
            'pointConstraint',
            'orientConstraint',
            'parentConstraint',
            'poleVectorConstraint',
            'aimConstraint',
            'scaleConstraint'
        ]

        for constraint_type in list_of_constraints_types:
            result.extend(pm.ls(type=constraint_type))

        return result

    #   . . . . . . . . . . . . . . . . . . . . . .

    def constraint_source(
        self,
        list_of_connected_nodes,
        constraint,
        control_constraint,
        delete_constraint
    ):

        for transform in list_of_connected_nodes:

            if not ':' in constraint \
                    and pm.objectType(transform) == 'transform':

                list_of_sources = \
                    constraint.sources()

                list_of_destinations = \
                    constraint.destinations()

                source = None
                destination = list_of_destinations[0]

                for each in list_of_sources:
                    if not destination == each:
                        source = each
                        break

                origin_name = source.split(':')[0]
                destination_name = transform.split(':')[0]

                if \
                    not destination in control_constraint \
                        and not origin_name == destination_name:

                    control_constraint.append(destination)
                    delete_constraint.append(constraint)

    #   . . . . . . . . . . . . . . . . . . . . . .

    def bake(
        self, start_frame,
        end_frame, control_constraint
    ):

        options = {
            "simulation": True,
            "time": (start_frame, end_frame),
            "oversamplingRate": 1,
            "disableImplicitControl": True,
            "preserveOutsideKeys": True,
            "sparseAnimCurveBake": False,
            "removeBakedAttributeFromLayer": False,
            "removeBakedAnimFromLayer": False,
            "bakeOnOverrideLayer": False,
            "minimizeRotation": True,
            "controlPoints": False,
            "shape": True
        }

        if len(control_constraint) > 0:
            pm.bakeResults(control_constraint, **options)
