# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# General utilities module
# Contains functions


def add_sys_path(new_path):
    """ Adds a directory to Python's sys.path

    Does not add the directory if it does not exist or if it's already on
    sys.path. Returns 1 if OK, -1 if new_path does not exist, 0 if it was
    already on sys.path.
    Based on: https://www.oreilly.com/library/view/python-cookbook/0596001673/ch04s23.html

    Challenge: in order to use this function, we need to import the dse_do_utils package
    and thus we need to add it's location it to sys.path!
    This will work better once we can do a pip install dse-do_utils.
    """
    import sys
    import os

    # Avoid adding nonexistent paths
    if not os.path.exists(new_path):
        return -1

    # Standardize the path. Windows is case-insensitive, so lowercase
    # for definiteness.
    new_path = os.path.abspath(new_path)
    if sys.platform == 'win32':
        new_path = new_path.lower(  )

    # Check against all currently available paths
    for x in sys.path:
        x = os.path.abspath(x)
        if sys.platform == 'win32':
            x = x.lower(  )
        if new_path in (x, x + os.sep):
            return 0
    sys.path.append(new_path)
    return 1


def list_file_hierarchy(startpath: str) -> None:
    """Hierarchically print the contents of the folder tree, starting with the `startpath`.

    Usage::

        current_dir = os.getcwd()
        parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
        parent_dir_2 = os.path.abspath(os.path.join(parent_dir, os.pardir))
        list_file_hierarchy(parent_dir_2) #List tree starting at the grand-parent of the current directory


    Args:
        startpath (str): Root of the tree

    Returns:
        None
    """
    import os
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        print('{}{}/'.format(indent, os.path.basename(root)))
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            print('{}{}'.format(subindent, f))



