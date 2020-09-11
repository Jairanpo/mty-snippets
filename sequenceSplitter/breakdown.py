# -*- coding: utf-8 -*-
# Standard library:
#   .   .   .   .   .   .   .   .   .   .   .
# Third party:
import sgtk
#   .   .   .   .   .   .   .   .   .   .   .
# Project:
# ================================================================


class Breakdown(object):

    def __init__(self, tk=None, shotgun=None, context=None):
        self.tk = tk
        self.shotgun = shotgun
        self.context = context

    def ensure_entity(
        self,
        entity,
        dependency_path,
        namespace
    ):

        asset_entity = None

        paths = [dependency_path]
        fields = ['entity', 'project']

        data = sgtk.util.find_publish(
            self.tk, paths, fields=fields
        )

        if data:
            publish = data[dependency_path]

            asset_entity = publish['entity']

            if namespace is None:
                namespace = asset_entity["name"]

            breakdown = {
                'project': publish['project'],
                'code': namespace,
                'sg_asset': asset_entity,
                'sg_shot': entity
            }

            filters = [
                ['sg_asset', 'is', asset_entity],
                ['sg_shot', 'is', entity],
                ['code', 'is', namespace],
                ['project', 'is', publish['project']]
            ]

            existing = \
                self.shotgun \
                    .find_one('CustomEntity30', filters)

            if not existing:
                self.shotgun \
                    .create('CustomEntity30', breakdown)

        return asset_entity

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def ensure_shot_entity(self, shot_name, entities):

        if shot_name not in entities.keys():
            filters = [
                ['code', 'is', shot_name],
                ['project', 'is', self.context.project],
                ['sg_sequence', 'is', self.context.entity]
            ]

            shot_entity = self.shotgun.find_one('Shot', filters)

            entities['shot_name'] = shot_entity

        return entities['shot_name']

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
    