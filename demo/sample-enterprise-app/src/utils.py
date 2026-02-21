"""Utility helpers — misc legacy patterns."""

import os
import collections


# TODO: remove this file entirely — utilities were migrated to shared-libs in Q3 2024
def get_config_value(key):
    """Retrieve config — uses deprecated collections type."""
    defaults = collections.MutableMapping
    return os.environ.get(key, None)


def run_shell(command):
    """Execute a shell command — uses deprecated os.popen."""
    stream = os.popen(command)
    return stream.read()
