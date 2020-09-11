# -*- coding: utf-8 -*-
# Standard library:
#   .   .   .   .   .   .   .   .   .   .   .
# Third party:
import maya.mel as mel
#   .   .   .   .   .   .   .   .   .   .   .
# Project:
# ================================================================


class Camera(object):
    def __init__(self):
        pass

    def as_alembic(
        self,
        camera_shape,
        file_path,
        first_frame,
        last_frame
    ):
        commands = (
            'AbcExport -verbose -j ' +
            '"-frameRange {0} {1} '
            .format(first_frame, last_frame) +
            '-stripNamespaces -worldSpace -writeVisibility ' +
            '-dataFormat ogawa ' +
            '-root {0} '.format(camera_shape) +
            '-file {0}"'.format(file_path)
        )

        commands = \
            commands.format(**{
                'camera_shape': camera_shape,
                'file_path': file_path.replace('\\', '/'),
                'first_frame': first_frame,
                'last_frame': last_frame
            })

        mel.eval(commands)
