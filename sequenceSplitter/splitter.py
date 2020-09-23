import os
import sgtk
import shutil
import pprint

import maya.cmds as cmds
import maya.mel as mel
import pymel.core as pm


class SequenceSplitter():

    def __init__(self, engine, tk, shotgun):
        """
        """

        self.sequence_shot_entities = {}
        self.context_by_shot_name = {}
        self.latest_shot_version_by_shot_name = {}
        self.shotgun = shotgun
        self.engine = engine
        self.tk = tk

        self.validate_current_session()

    def validate_current_session(self):
        """
        """

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

    def get_top_references(self):
        """ Get the current TOP references objects in the scene
        """

        top_level_reference_nodes = []
        all_references = cmds.ls(objectsOnly=True, references=True)
        top_level_referenced_files = cmds.file(query=True, reference=True)
        for ref_node in all_references:
            ref_file = cmds.referenceQuery(ref_node, filename=True)
            if ref_file in top_level_referenced_files:
                top_level_reference_nodes.append(ref_node)

        return top_level_reference_nodes

    def bakeConstrains(self, startF, endF):
        """
        """

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

                        list_source = cmds.listConnections(_constrain,
                                                           source=True,
                                                           destination=False,
                                                           scn=True,
                                                           type='transform')

                        destination = cmds.listConnections(_constrain,
                                                           source=False,
                                                           destination=True,
                                                           scn=True,
                                                           type='transform')
                        source = None
                        for each in list_source:
                            if not destination[0] == each:
                                source = each
                                break
                        origin_name = source.split(':')[0]
                        destination_name = nodo.split(':')[0]

                        if not destination[0] in control_constrain and not origin_name == destination_name:
                            print("From "+source+" to "+destination[0])
                            control_constrain.append(destination[0])
                            delete_constrain.append(_constrain)
            except:
                print("Error: Maybe {0} is a NoneType?".format(_constrain))

        if len(control_constrain) > 0:

            cmds.bakeResults(control_constrain,
                             simulation=True,
                             t=(startF, endF),
                             oversamplingRate=1,
                             disableImplicitControl=True,
                             preserveOutsideKeys=True,
                             sparseAnimCurveBake=False,
                             removeBakedAttributeFromLayer=False,
                             removeBakedAnimFromLayer=False,
                             bakeOnOverrideLayer=False,
                             minimizeRotation=True,
                             controlPoints=False,
                             shape=True)

            cmds.delete(delete_constrain)

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
        self.shotgun.update('Shot', shot_entity['id'], data)

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

            filters = [['sg_asset', 'is', asset_entity],
                       ['sg_shot', 'is', shot_entity],
                       ['code', 'is', namespace],
                       ['project', 'is', publish['project']]]

            existing = self.shotgun.find_one('CustomEntity30', filters)

            if not existing:
                self.shotgun.create('CustomEntity30', breakdown)

        return asset_entity

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def export_camera(self, camera_node, file_path, first_frame, last_frame):
        """
        """
        camera_name = camera_node.name()

        commands = (
            'AbcExport -verbose -j ' +
            '"-frameRange {first_frame} {last_frame} ' +
            '-stripNamespaces -worldSpace -writeVisibility ' +
            '-dataFormat ogawa ' +
            '-root {0} '.format(camera_name) +
            '-file {file_path}"'
        )

        commands = commands.format(**{
            'camera_shape': camera_name,
            'file_path': file_path.replace('\\', '/'),
            'first_frame': first_frame,
            'last_frame': last_frame
        })

        mel.eval(commands)

    # ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ---- ----

    def ensure_shot_entity(self, shot_name):
        """
        """

        current = self.sequence_shot_entities.get(shot_name)
        if not current:
            filters = [['code', 'is', shot_name],
                       ['project', 'is', self.context.project],
                       ['sg_sequence', 'is', self.context.entity]]
            shot_entity = self.shotgun.find_one('Shot', filters)

            self.sequence_shot_entities['shot_name'] = shot_entity

        return self.sequence_shot_entities['shot_name']

    def get_shot_context(self, shot_name):
        """
        """

        context = self.context_by_shot_name.get(shot_name)

        if not context:

            filters = [['content', 'is', 'Layout'],
                       ['entity', 'is', self.ensure_shot_entity(shot_name)]]

            task = self.shotgun.find_one(
                'Task', filters, ['entity', 'project', 'step'])

            # context needs to have folders on disk
            self.tk.create_filesystem_structure('Task', task['id'])

            context = self.tk.context_from_entity_dictionary(task)

            self.context_by_shot_name[shot_name] = context

        return context

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

            publish = self.shotgun.find_one(
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
            "tk": self.tk,
            "context": shot_context,
            "path": publish_file_path,
            "name": self.current_publish_name,
            "version_number": self.get_next_maya_shot_publish_version(shot_name),
            "comment": 'Shot split from Sequence',
            "published_file_type": "Maya Scene",
            "task": shot_context.task,
            "created_by": {'type': 'HumanUser', 'id': 385},
        }

        sgtk.util.register_publish(**publish_data)

    def run_shot_publish(self, shot_name):

        # get the publish app instance from the engine's list of configured apps
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

    def extract_shot(self, shot_name):
        """destructuve process of demoved references and animation
        from a sequence file so that only those particualry requiered
        for an specific shot will remain in the scene
        """

        shots = cmds.ls(type='shot')
        shot_node = None

        for s in shots:
            name = cmds.getAttr('%s.shotName' % s)
            if name == shot_name:
                shot_node = s
                break

        if not shot_node:
            message = "Can't find a shot node with its name set to : %s"
            raise Exception(message % shot_name)

        split_string = cmds.getAttr('%s.assets' % shot_node)

        # --------------------------------------------------------------------------------

        requiered_nodes = []

        if split_string is not None:
            requiered_nodes.extend(cmds.getAttr(
                '%s.assets' % shot_node).split(';'))

        # --------------------------------------------------------------------------------

        # collect info from shot node
        camera_shape = cmds.shot(shot_node, query=True, currentCamera=True)
        camera_reference = cmds.referenceQuery(
            camera_shape, referenceNode=True)
        camera_node = cmds.listRelatives(camera_shape, parent=True)[0]

        # collect dependencies
        requiered_nodes.append(camera_reference)
        gpu_cache_nodes = cmds.ls(type='gpuCache')
        top_reference_nodes = self.get_top_references()

        # delete all the shot nodes different that current shot
        for shot in cmds.ls(type='shot'):
            if shot != shot_node:
                cmds.delete(shot)

        # delete all the gpu nodes if they are not required
        for gpu_cache in gpu_cache_nodes:
            gpu_cache = cmds.listRelatives(gpu_cache, parent=True)
            if gpu_cache and gpu_cache[0] not in requiered_nodes:
                cmds.delete(gpu_cache)
        # get first and last frame for the shot
        first_frame = cmds.shot(shot_node, query=True, startTime=True)
        last_frame = cmds.shot(shot_node, query=True, endTime=True)

        # bake animation from constrains before removing references
        self.bakeConstrains(first_frame, last_frame)

        # delete all the references if they are not required
        for reference_node in top_reference_nodes:
            if reference_node not in requiered_nodes:
                reference_file_path = cmds.referenceQuery(
                    reference_node, filename=True)
                cmds.file(reference_file_path, removeReference=True)

        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
        # TODO: Refactor this code, it should only be in either maya
        # cmds or pymel.
        # maya.cmds where getting the whole rig instead of the
        # camera rig tranform node, switching to pymel to
        # use the instance instead of the name.

        # export the current shot camera as alembic
        pymel_shot_node = pm.ls(shot_node, type="shot")[0]
        pymel_camera_node = pymel_shot_node.getCurrentCamera()
        pymel_camera_node = pm.PyNode(pymel_camera_node)
        print(pymel_camera_node)
        camera_publish_path = self.get_publish_camera_path(shot_name)
        self.export_camera(
            pymel_camera_node,
            camera_publish_path,
            first_frame,
            last_frame
        )
        self.publish_camera(shot_name, camera_publish_path)

        # . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .

        # delete animation keys outside shot range
        global_infinity_range = 999999
        animation_curves = cmds.ls(
            type=['animCurveTT', 'animCurveTL', 'animCurveTA', 'animCurveTU'])
        for curve in animation_curves:

            # insert new keyframes in the limit of the shot range to mantain
            cmds.setKeyframe(curve, animated=True,
                             insert=True, time=first_frame)
            cmds.setKeyframe(curve, animated=True,
                             insert=True, time=last_frame)

            # then remove all keyframes outside of that range
            cmds.cutKey(curve, animation="objects",
                        time=(-global_infinity_range, first_frame-1))
            cmds.cutKey(curve, animation="objects", time=(
                last_frame+1, global_infinity_range))

        # ready to save file
        shot_publish_scene_path = self.get_publish_scene_path(
            shot_name, "maya_shot_work")
        cmds.file(rename=shot_publish_scene_path)
        cmds.file(force=True, type='mayaAscii', save=True)

        self.publish_scene(shot_name)

        self.create_breakdown(shot_name, requiered_nodes)

    def extract_shot_shots(self):
        """
        """

        shots = cmds.ls(type='shot')

        for s in shots:

            name = cmds.getAttr('%s.shotName' % s)
            self.extract_shot(name)

            cmds.file(new=True, force=True)
            cmds.file(self.sequence_file_path, open=True, force=True)


splitter = SequenceSplitter(engine, tk, shotgun)
splitter.extract_shot_shots()
