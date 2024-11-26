from collections import namedtuple

Flow = namedtuple(
    "Flow", ["cc", "cc_src_local", "cc_src_remote", "run_first", "run_second"]
)
