import pathlib
# Extend package path so submodules resolve to the real implementation in backend/app
__path__.append(str(pathlib.Path(__file__).parent.parent / 'backend' / 'app'))
