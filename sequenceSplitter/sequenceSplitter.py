# Standard library:
import pprint
import os
import shutil
#   .   .   .   .   .   .   .   .   .   .   .
# Third party:
import sgtk
import maya.cmds as cmds
import maya.mel as mel
import pymel.core as pm
#   .   .   .   .   .   .   .   .   .   .   .
# Project:
# ================================================================
pp = pprint.PrettyPrinter(indent=3).pprint


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

    def move_animation_with_cutItem_data(
        self, start, shot
    ):

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


# ================================================================


class SequenceSplitter():

    def __init__(self, engine, tk):
        self.keyframesManager = KeyframesManager(engine, tk)
        self.sequence_shot_entities = {}
        self.context_by_shot_name = {}
        self.latest_shot_version_by_shot_name = {}
        self.engine = engine
        self.tk = tk

        self.validate_current_session()

    def validate_current_session(self):
        current_path = cmds.file(query=True, sceneName=True)

        if not current_path or not os.path.exists(current_path):
            message = "Scene path doesn't exist or is not valid:\n%s"
            raise Exception(message % current_path)

        self.sequence_file_path = current_path

        template = self.tk.templates.get("maya_sequence_publish")
        self.current_template_fields = template.validate_and_get_fields(
            self.sequence_file_path)

        if not self.current_template_fields:
            message = "The current scene path is not a valid Sequence Maya Publish file:\n%s"
            raise Exception(message % self.sequence_file_path)

        self.current_version_number = self.current_template_fields['version']
        self.current_publish_name = self.current_template_fields['name']

        self.tk.synchronize_filesystem_structure(full_sync=True)
        self.context = self.tk.context_from_path(self.sequence_file_path)

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def create_breakdown(self, shot_name, requiered_nodes):
        """
        """

        shot_entity = self.ensure_shot_entity(shot_name)

        assets = []

        for node in requiered_nodes:
            node_type = cmds.nodeType(node)

            if node_type == 'reference':
                file_path = cmds.referenceQuery(node, filename=True)
                namespace = cmds.referenceQuery(
                    node, namespace=True).replace(':', '')

                asset_entity = self.ensure_breakdown_entity(
                    shot_entity, file_path, namespace)
                if asset_entity:
                    assets.append(asset_entity)

            if node_type == 'transform':
                # this one gets tricky, but we in theory now that its a gpuCache
                # Lets first get the children and verify its indeed a gpuCache
                children = cmds.listRelatives(node, children=True)
                if children and cmds.nodeType(children[0]) == 'gpuCache':
                    child = children[0]
                    file_path = cmds.getAttr("%s.cacheFileName" % child)

                    asset_entity = self.ensure_breakdown_entity(
                        shot_entity, file_path, None)
                    if asset_entity:
                        assets.append(asset_entity)

        # finally just update the assets shot field
        data = {'assets': assets}
        self.tk.shotgun.update('Shot', shot_entity['id'], data)

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def ensure_breakdown_entity(self, shot_entity, dependency_path, namespace):
        """
        """

        asset_entity = None

        paths = [dependency_path]
        fields = ['entity', 'project']
        data = sgtk.util.find_publish(self.tk, paths, fields=fields)

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
                self.tk.shotgun.find_one(
                    'CustomEntity30', filters
                )

            if not existing:
                self.tk.shotgun.create('CustomEntity30', breakdown)

        return asset_entity

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def bake_constraints(self, start, end):

        all_constrains = cmds.ls(type='pointConstraint')
        all_constrains.extend(cmds.ls(type='orientConstraint'))
        all_constrains.extend(cmds.ls(type='parentConstraint'))
        all_constrains.extend(cmds.ls(type='poleVectorConstraint'))
        all_constrains.extend(cmds.ls(type='aimConstraint'))
        all_constrains.extend(cmds.ls(type='scaleConstraint'))

        control_constrain = []
        delete_constrain = []

        for _constrain in all_constrains:
            try:
                conections = cmds.listConnections(_constrain,
                                                  source=True,
                                                  scn=True,
                                                  type='transform')
                for nodo in conections:
                    # and cmds.attributeQuery('fbControl',node = nodo, exists = True):
                    if not ':' in _constrain and cmds.objectType(nodo) == 'transform':

                        list_source = cmds.listConnections(
                            _constrain,
                            source=True,
                            destination=False,
                            scn=True,
                            type='transform'
                        )

                        destination = cmds.listConnections(
                            _constrain,
                            source=False,
                            destination=True,
                            scn=True,
                            type='transform'
                        )

                        source = None
                        for each in list_source:
                            if not destination[0] == each:
                                source = each
                                break
                        origin_name = source.split(':')[0]
                        destination_name = nodo.split(':')[0]

                        if not destination[0] in control_constrain \
                                and not origin_name == destination_name:
                            print("From "+source+" to "+destination[0])
                            control_constrain.append(destination[0])
                            delete_constrain.append(_constrain)
            except:
                print("Error: Maybe {0} is a NoneType?".format(_constrain))

        if len(control_constrain) > 0:

            cmds.bakeResults(
                control_constrain,
                simulation=True,
                t=(start, end),
                oversamplingRate=1,
                disableImplicitControl=True,
                preserveOutsideKeys=True,
                sparseAnimCurveBake=False,
                removeBakedAttributeFromLayer=False,
                removeBakedAnimFromLayer=False,
                bakeOnOverrideLayer=False,
                minimizeRotation=True,
                controlPoints=False,
                shape=True
            )

            cmds.delete(delete_constrain)
    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def export_camera(self, camera_node, file_path, first_frame, last_frame):
        camera_name = camera_node.name()

        mel_command = \
            '-frameRange {0} {1} -uvWrite -worldSpace \
                -writeVisibility -dataFormat \
                    ogawa -root {2} -file {3}'.format(
                first_frame,
                last_frame,
                camera_name,
                file_path
            )

        pm.AbcExport(j=mel_command)

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def ensure_shot_entity(self, shot_name):
        """
        """

        current = self.sequence_shot_entities.get(shot_name)
        if not current:
            filters = [['code', 'is', shot_name],
                       ['project', 'is', self.context.project],
                       ['sg_sequence', 'is', self.context.entity]]
            shot_entity = self.tk.shotgun.find_one('Shot', filters)

            self.sequence_shot_entities['shot_name'] = shot_entity

        return self.sequence_shot_entities['shot_name']

    def get_shot_context(self, shot_name):
        """
        """

        context = self.context_by_shot_name.get(shot_name)

        if not context:

            filters = [['content', 'is', 'Layout'],
                       ['entity', 'is', self.ensure_shot_entity(shot_name)]]

            task = self.tk.shotgun.find_one(
                'Task', filters, ['entity', 'project', 'step'])

            # context needs to have folders on disk
            self.tk.create_filesystem_structure('Task', task['id'])

            context = self.tk.context_from_entity_dictionary(task)

            self.context_by_shot_name[shot_name] = context

        return context

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def publish_camera(self, shot_name, camera_publish_path):
        """
        """

        shot_context = self.get_shot_context(shot_name)

        publish_data = {
            "tk": self.tk,
            "context": shot_context,
            "path": camera_publish_path,
            "name": self.current_publish_name,
            "version_number": self.get_next_maya_shot_publish_version(shot_name),
            "comment": 'Shot split from Sequence',
            "published_file_type": "Shot Camera Cache",
            "task": shot_context.task,
            "created_by": {'type': 'HumanUser', 'id': 385},
        }

        sgtk.util.register_publish(**publish_data)

    def get_publish_camera_path(self, shot_name):
        """
        """

        shot_context = self.get_shot_context(shot_name)

        template = self.tk.templates.get("shot_camera_publish")

        template_fields = shot_context.as_template_fields(template)

        sequence_fields = self.current_template_fields.copy()
        sequence_fields.update(template_fields)
        template_fields = sequence_fields

        # add missing "name" and "version"
        template_fields['name'] = self.current_publish_name
        template_fields['version'] = \
            self.get_next_maya_shot_publish_version(shot_name)

        template_fields['Shot'] = shot_name

        camera_path = template.apply_fields(template_fields)

        sgtk.util.filesystem.ensure_folder_exists(os.path.dirname(camera_path))

        return camera_path

    def get_next_maya_shot_publish_version(self, shot_name):
        """define version based on existing publishes
           but mantaining sequence one as fallback
        """

        if not shot_name in self.latest_shot_version_by_shot_name:
            shot_context = self.get_shot_context(shot_name)

            filters = [['entity', 'is', shot_context.entity],
                       ['task', 'is', shot_context.task],
                       ['name', 'is', self.current_publish_name],
                       ['project', 'is', shot_context.project],
                       ['published_file_type.PublishedFileType.code', 'is', 'Maya Scene']]

            fields = ['version_number']
            order = [{'field_name': 'version_number', 'direction': 'desc'}]

            publish = self.tk.shotgun.find_one(
                'PublishedFile', filters, fields, order)

            if publish:
                self.latest_shot_version_by_shot_name[shot_name] = publish['version_number'] + 1
            else:
                self.latest_shot_version_by_shot_name[shot_name] = self.current_version_number

        return self.latest_shot_version_by_shot_name[shot_name]

    def get_publish_scene_path(self, shot_name, template_name):
        """
        """

        shot_context = self.get_shot_context(shot_name)

        template = self.tk.templates.get(template_name)

        # context.as_template_fields need to have folders on disk
        template_fields = shot_context.as_template_fields(template)

        sequence_fields = self.current_template_fields.copy()
        sequence_fields.update(template_fields)
        template_fields = sequence_fields

        version_number = self.get_next_maya_shot_publish_version(shot_name)

        # add missing "name" and "version"
        template_fields['name'] = self.current_publish_name
        template_fields['version'] = version_number
        template_fields['Shot'] = shot_name

        scene_path = template.apply_fields(template_fields)

        sgtk.util.filesystem.ensure_folder_exists(os.path.dirname(scene_path))

        return scene_path

    def publish_scene(self, shot_name):
        """
        """

        shot_context = self.get_shot_context(shot_name)

        work_file_path = self.get_publish_scene_path(
            shot_name, "maya_shot_work")
        publish_file_path = self.get_publish_scene_path(
            shot_name, "maya_shot_publish")

        shutil.copy(work_file_path, publish_file_path)

        publish_data = {
            "tk":
                self.tk,
            "context":
                shot_context,
            "path":
                publish_file_path,
            "name":
                self.current_publish_name,
            "version_number":
                self.get_next_maya_shot_publish_version(shot_name),
            "comment":
                'Shot split from Sequence',
            "published_file_type":
                "Maya Scene",
            "task":
                shot_context.task,
            "created_by": {'type': 'HumanUser', 'id': 385},
        }

        sgtk.util.register_publish(**publish_data)

    def run_shot_publish(self, shot_name):

        publish_app = self.engine.apps.get("tk-multi-publish2")

        shot_context = self.get_shot_context(shot_name)

        self.engine.change_context(shot_context)

        # create a new publish manager instance
        manager = publish_app.create_publish_manager()

        # now we can run the collector that is configured for this context
        manager.collect_session()

        # validate the items to publish
        tasks_failed_validation = manager.validate()

        if tasks_failed_validation:
            raise Exception(tasks_failed_validation)

        manager.publish()
        manager.finalize()

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def extract_shot(self, shot_node_name):
        shot_node = pm.ls(shot_node_name, type="shot")[0]
        shot_name = shot_node.getShotName()
        split_string = shot_node.assets.get()
        requiered_nodes = []

        if split_string is not None:
            requiered_nodes.extend(split_string.split(";"))

        #   . . . . . . . . . . . . . . . . . . . . . .

        # collect info from shot node
        camera_shape = pm.PyNode(shot_node.getCurrentCamera())
        camera_reference = \
            pm.referenceQuery(camera_shape, referenceNode=True)
        camera_node = None

        if isinstance(camera_shape, pm.nt.Camera):
            camera_node = camera_shape.getParent()
        else:
            camera_node = camera_shape

        requiered_nodes.append(camera_reference)
        top_reference_nodes = pm.listReferences(recursive=False)

        for shot_element in pm.ls(type='shot'):
            if shot_element != shot_node:
                pm.delete(shot_element)

        gpu_cache_nodes = pm.ls(type='gpuCache')
        for gpu_cache in gpu_cache_nodes:
            gpu_cache_transform = gpu_cache.getParent()
            if gpu_cache_transform.name() not in requiered_nodes:
                pm.delete(gpu_cache_transform)

        first_frame = shot_node.getStartTime()
        last_frame = shot_node.getEndTime()

        self.bake_constraints(first_frame, last_frame)

        print("finish baking constraints")

        for reference_node in top_reference_nodes:
            if reference_node.refNode.name() not in requiered_nodes:
                reference_node.remove()

        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

        self.keyframesManager \
            .limit_animation_curves(first_frame, last_frame)

        self.keyframesManager \
            .move_animation_with_cutItem_data(first_frame, shot_node)

        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

        camera_publish_path = self.get_publish_camera_path(shot_name)

        self.export_camera(
            camera_node,
            camera_publish_path,
            first_frame,
            last_frame
        )

        self.publish_camera(shot_name, camera_publish_path)

        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

        shot_publish_scene_path = self.get_publish_scene_path(
            shot_name, "maya_shot_work")
        pm.renameFile(shot_publish_scene_path)
        pm.saveFile(force=True, type='mayaAscii')

        self.publish_scene(shot_name)
        self.create_breakdown(shot_name, requiered_nodes)

    def extract_shot_shots(self):

        list_of_shots = pm.ls(type='shot')

        for shot in list_of_shots:

            #   . . . . . . . . . . . . . . . . . . . . . .
            shot_node_name = shot.name()
            print("Exporting: {0}".format(shot_node_name))
            self.extract_shot(shot_node_name)
            #   . . . . . . . . . . . . . . . . . . . . . .

            pm.newFile(force=True)

            pm.openFile(self.sequence_file_path, force=True)


# splitter = SequenceSplitter(engine, tk)
# splitter.extract_shot_shots()
