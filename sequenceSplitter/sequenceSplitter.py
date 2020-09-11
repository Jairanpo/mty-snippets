# -*- coding: utf-8 -*-
# Standard library:
import os
import sgtk
import shutil
import pprint
#   .   .   .   .   .   .   .   .   .   .   .
# Third party:
import maya.cmds as cmds
import pymel.core as pm
import maya.mel as mel
import bakeConstraints
import camera
import breakdown
#   .   .   .   .   .   .   .   .   .   .   .
# Project:
# ================================================================


class SequenceSplitter():

    def __init__(self, engine, tk, shotgun):
        self.entities = {}
        self.contexts = {}
        self.latest_shot_version_by_shot_name = {}
        self.shotgun = shotgun
        self.engine = engine
        self.tk = tk
        self.context = None
        self.file_path = self.current_file_path()

        #   .   .   .   .   .   .   .   .   .   .   .
        # Setup:

        # This one set the context for the self.Breakdown instance.
        self.validate_current_session(self.file_path)

        self.Breakdown = \
            breakdown.Breakdown(self.tk, self.shotgun, self.context)

        self.BakeConstraints = \
            bakeConstraints.BakeConstraints()

        self.Camera = camera.Camera()

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def current_file_path(self):
        result = cmds.file(query=True, sceneName=True)

        if not result \
                or not os.path.exists(result):

            message = \
                "Scene path doesn't " + \
                "exist or is not valid:\n{0}".format(result)

            raise Exception(message)

        return result

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def validate_current_session(self, file_path):

        template = \
            self.tk.templates.get("maya_sequence_publish")

        self.template_fields = \
            template.validate_and_get_fields(file_path)

        if self.template_fields is None:
            message = \
                "The current scene path is " + \
                "not a valid Maya sequence " + \
                "publish file:\n{0}".format(file_path)

            raise Exception(message)

        else:
            self.version = \
                self.template_fields['version']

            self.publish_name = \
                self.template_fields['name']

            self.tk.synchronize_filesystem_structure(
                full_sync=True
            )

            self.context = self.tk.context_from_path(file_path)

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def create_breakdown(
        self, shot_name, linked_assets
    ):
        shot_entity = self.Breakdown \
            .ensure_shot_entity(shot_name, self.entities)

        assets = []

        for node in linked_assets:
            node_type = cmds.nodeType(node)

            if node_type == 'reference':

                file_path = \
                    cmds.referenceQuery(node, filename=True)

                namespace = cmds.referenceQuery(
                    node, namespace=True).replace(':', '')

                asset_entity = \
                    self.Breakdown.ensure_entity(
                        shot_entity, file_path, namespace
                    )

                if asset_entity:
                    assets.append(asset_entity)

            if node_type == 'transform':
                # this one gets tricky, but we in theory
                # now that its a gpuCache
                # Lets first get the children
                # and verify its indeed a gpuCache

                children = \
                    cmds.listRelatives(node, children=True)

                children_type = cmds.nodeType(children[0])

                if children \
                        and children_type == 'gpuCache':

                    child = children[0]

                    file_path = \
                        cmds.getAttr("%s.cacheFileName" % child)

                    asset_entity = \
                        self.Breakdown.ensure_entity(
                            shot_entity, file_path, None
                        )

                    if asset_entity:
                        assets.append(asset_entity)

        # finally just update the assets shot field
        data = {'assets': assets}
        self.shotgun.update('Shot', shot_entity['id'], data)

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def ensure_breakdown_entity(
        self, shot_entity, dependency_path, namespace
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

            namespace = namespace or asset_entity['name']

            breakdown = {'project': publish['project'],
                         'code': namespace,
                         'sg_asset': asset_entity,
                         'sg_shot': shot_entity}

            filters = [
                ['sg_asset', 'is', asset_entity],
                ['sg_shot', 'is', shot_entity],
                ['code', 'is', namespace],
                ['project', 'is', publish['project']]
            ]

            existing = \
                self.shotgun.find_one('CustomEntity30', filters)

            if not existing:
                self.shotgun.create('CustomEntity30', breakdown)

        return asset_entity

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def shot_context(self, shot_name):
        result = None

        if shot_name not in self.contexts.keys():

            filters = [
                ['content', 'is', 'Layout'],

                [
                    'entity',
                    'is',
                    self.Breakdown.ensure_shot_entity(
                        shot_name, self.entities
                    )
                ]

            ]

            task = self.shotgun.find_one(
                'Task', filters, ['entity', 'project', 'step'])

            # context needs to have folders on disk
            self.tk.create_filesystem_structure('Task', task['id'])

            context = self.tk.context_from_entity_dictionary(task)

            self.contexts[shot_name] = context

            result = self.contexts[shot_name]

        return result

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def publish_camera(self, shot_name, camera_publish_path):

        shot_context = self.shot_context(shot_name)

        next_publish_version = \
            self.get_next_maya_shot_publish_version(shot_name)

        publish_data = {
            "tk": self.tk,
            "context": shot_context,
            "path": camera_publish_path,
            "name": self.publish_name,
            "version_number": next_publish_version,
            "comment": 'Shot split from Sequence',
            "published_file_type": "Shot Camera Cache",
            "task": shot_context.task,
            "created_by": {'type': 'HumanUser', 'id': 385},
        }

        sgtk.util.register_publish(**publish_data)

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def get_publish_camera_path(self, shot_name):

        shot_context = self.shot_context(shot_name)

        template = self.tk.templates.get("shot_camera_publish")

        template_fields = shot_context.as_template_fields(template)

        sequence_fields = self.template_fields.copy()

        sequence_fields.update(template_fields)

        template_fields = sequence_fields

        # add missing "name" and "version"
        template_fields['name'] = self.publish_name

        template_fields['version'] = \
            self.get_next_maya_shot_publish_version(shot_name)

        template_fields['Shot'] = shot_name

        camera_path = template.apply_fields(template_fields)

        sgtk.util.filesystem.ensure_folder_exists(
            os.path.dirname(camera_path)
        )

        return camera_path

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def get_next_maya_shot_publish_version(self, shot_name):
        """define version based on existing publishes
           but mantaining sequence one as fallback
        """

        if not shot_name in self.latest_shot_version_by_shot_name:
            shot_context = self.shot_context(shot_name)

            filters = [
                ['entity', 'is', shot_context.entity],
                ['task', 'is', shot_context.task],
                ['name', 'is', self.publish_name],
                ['project', 'is', shot_context.project],
                [
                    'published_file_type.PublishedFileType.code',
                    'is',
                    'Maya Scene'
                ]
            ]

            fields = ['version_number']

            order = \
                [
                    {
                        'field_name': 'version_number',
                        'direction': 'desc'
                    }
                ]

            publish = self.shotgun.find_one(
                'PublishedFile', filters, fields, order)

            if publish:
                self.latest_shot_version_by_shot_name[shot_name] = \
                    publish['version_number'] + 1

            else:
                self.latest_shot_version_by_shot_name[shot_name] = \
                    self.version

        return self.latest_shot_version_by_shot_name[shot_name]

    def get_publish_scene_path(self, shot_name, template_name):

        shot_context = self.shot_context(shot_name)

        template = self.tk.templates.get(template_name)

        # context.as_template_fields need to have folders on disk
        template_fields = shot_context.as_template_fields(template)

        sequence_fields = self.template_fields.copy()
        sequence_fields.update(template_fields)
        template_fields = sequence_fields

        version_number = \
            self.get_next_maya_shot_publish_version(shot_name)

        # add missing "name" and "version"
        template_fields['name'] = self.publish_name
        template_fields['version'] = version_number
        template_fields['Shot'] = shot_name

        scene_path = template.apply_fields(template_fields)

        sgtk.util.filesystem \
            .ensure_folder_exists(os.path.dirname(scene_path))

        return scene_path

    def publish_scene(self, shot_name):
        """
        """

        shot_context = self.shot_context(shot_name)

        work_file_path = self.get_publish_scene_path(
            shot_name, "maya_shot_work")
        publish_file_path = self.get_publish_scene_path(
            shot_name, "maya_shot_publish")

        shutil.copy(work_file_path, publish_file_path)

        next_version = \
            self.get_next_maya_shot_publish_version(shot_name)

        publish_data = {
            "tk": self.tk,
            "context": shot_context,
            "path": publish_file_path,
            "name": self.publish_name,
            "version_number": next_version,
            "comment": 'Shot split from Sequence',
            "published_file_type": "Maya Scene",
            "task": shot_context.task,
            "created_by": {
                'type': 'HumanUser', 'id': 385
            },
        }

        sgtk.util.register_publish(**publish_data)

    def run_shot_publish(self, shot_name):

        # get the publish app instance from the engine's
        # list of configured apps
        publish_app = self.engine.apps.get("tk-multi-publish2")

        shot_context = self.shot_context(shot_name)

        self.engine.change_context(shot_context)

        # create a new publish manager instance
        manager = publish_app.create_publish_manager()

        # now we can run the collector that is
        # configured for this context
        manager.collect_session()

        # validate the items to publish
        tasks_failed_validation = manager.validate()

        if tasks_failed_validation:
            raise Exception(tasks_failed_validation)

        manager.publish()
        manager.finalize()

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def split_by_shot(self, shot):
        """
        Destructuve process of demoved 
        references and animation from a sequence file 
        so that only those particuarly requiered
        for an specific shot will remain in the scene
        """

        shot_name = shot.getShotName()

        if not shot:
            message = \
                "Can't find a shot node " + \
                "with its name set to : {0}".format(shot.name())

            raise Exception(message)

        linked_assets = shot.assets.get().split(';')

        # collect info from shot node
        camera_shape = \
            pm.PyNode(shot.getCurrentCamera())

        camera_reference = pm.referenceQuery(
            camera_shape, referenceNode=True)

        camera_node = camera_shape.getParent()

        # collect dependencies
        linked_assets.append(camera_reference)
        gpu_cache_nodes = pm.ls(type='gpuCache')
        list_of_references = pm.listReferences()

        # delete all the shot nodes different that current shot
        list_of_shots = pm.ls(type='shot')
        for shot_node in list_of_shots:
            if shot_node != shot:
                pm.delete(shot_node)

        # delete all the gpu nodes if they are not required
        for gpu_cache in gpu_cache_nodes:
            gpu_cache_transform = gpu_cache.getParent()

            if gpu_cache_transform \
                    not in linked_assets:

                pm.delete(gpu_cache_transform)

        # get first and last frame for the shot
        first_frame = int(shot.getStartTime())
        last_frame = int(shot.getEndTime())

        # bake animation from constrains before removing references
        self.BakeConstraints.process(first_frame, last_frame)

        # delete all the references if they are not required
        for reference in list_of_references:

            if reference.refNode.name() \
                    not in linked_assets:

                reference.remove()

        # export the current shot camera as alembic
        camera_publish_path = \
            self.get_publish_camera_path(shot_name)

        self.Camera.as_alembic(
            camera_node, camera_publish_path,
            first_frame, last_frame
        )

        self.publish_camera(shot_name, camera_publish_path)

        # delete animation keys outside shot range
        global_infinity_range = 999999

        animation_curves = cmds.ls(
            type=[
                'animCurveTT', 'animCurveTL',
                'animCurveTA', 'animCurveTU'
            ])

        for curve in animation_curves:

            # insert new keyframes in the limit of
            # the shot range to mantain
            cmds.setKeyframe(
                curve, animated=True,
                insert=True, time=first_frame
            )

            cmds.setKeyframe(
                curve, animated=True,
                insert=True, time=last_frame
            )

            # then remove all keyframes outside of thjat range
            cmds.cutKey(
                curve, animation="objects",
                time=(-global_infinity_range, first_frame-1)
            )

            cmds.cutKey(
                curve, animation="objects",
                time=(last_frame+1, global_infinity_range)
            )

        # ready to save file
        shot_publish_scene_path = \
            self.get_publish_scene_path(
                shot_name, "maya_shot_work"
            )

        cmds.file(rename=shot_publish_scene_path)
        cmds.file(force=True, type='mayaAscii', save=True)

        self.publish_scene(shot_name)

        self.create_breakdown(shot_name, linked_assets)

    # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

    def extract_shot_shots(self):

        list_of_shots = pm.ls(type='shot')

        for shot in list_of_shots:

            self.split_by_shot(shot)

            cmds.file(new=True, force=True)

            cmds.file(
                self.file_path, open=True, force=True
            )
