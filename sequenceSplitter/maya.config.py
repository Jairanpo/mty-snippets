import sys

env = "dev"

path = None

if env == "dev":
    path = "C:\Development\Mighty\mty-snippets\sequenceSplitter"

if path in sys.path:
    pass
else:
    sys.path.insert(0, path)


import sequenceSplitter as sq

splitter = sq.SequenceSplitter(engine, tk, shotgun)
splitter.extract_shot_shots()
