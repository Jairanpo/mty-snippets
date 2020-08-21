import pymel.core as pm


list_of_shots = pm.ls(type="shot")
list_of_references = pm.listReferences()


def reference_node_exists(name, gpu_cache=True):
    result = True

    list_of_asset_nodes = []

    for reference in list_of_references:
        list_of_asset_nodes.append(reference.refNode)

    if gpu_cache:
        list_of_gpu_caches = pm.ls(type="gpuCache")
        for gpu_cache in list_of_gpu_caches:
            list_of_asset_nodes.append(gpu_cache.getParent())

    if name not in list_of_asset_nodes:
        result = False

    return result


def unknown_assets(shot, result):
    list_of_assets = shot.assets.get().split(";")
    for asset in list_of_assets:
        if not reference_node_exists(asset):
            shot_name = shot.name()
            result.append({
                shot_name: {"unknown": asset}
            })


def validate_assets_in_shots():
    result = []
    for shot in list_of_shots:
        unknown_assets(shot, result)

    return result


print(validate_assets_in_shots())
