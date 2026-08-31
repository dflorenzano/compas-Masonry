def threedec_blocker(version=None, executable=""):
    from compas_dem.problem import Solver

    if not hasattr(Solver, "ThreeDEC"):
        msg = "This compas_dem has no Solver.ThreeDEC, so a 3DEC solve would fail. Upgrade compas_dem."
        return msg

    try:
        from compas_3dec import find_3dec_executable
    except Exception:
        msg = "compas_3dec is not importable here, so a 3DEC solve would fail. It is a base requirement, so this environment is incomplete: reinstall compas_masonry."
        return msg

    if executable:
        return ""

    if find_3dec_executable(version) is None:
        return (
            "No Itasca 3DEC installation was found on this machine, so a 3DEC solve would fail. "
            "3DEC is a licensed Windows software: install it, or set the Executable field "
            "(or COMPAS_3DEC_EXECUTABLE) to a reachable 3DEC binary."
        )

    return ""
