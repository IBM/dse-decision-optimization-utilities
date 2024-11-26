# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
from collections import namedtuple

import pandas as pd


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


def convert_size(size_bytes: int):
    """Returns string describing file size.

    Args:
        size_bytes (int): size if file in bytes

    From https://stackoverflow.com/questions/5194057/better-way-to-convert-file-sizes-in-python
    """
    import math
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


def df_itertuples_with_index_names(df: pd.DataFrame):
    """Alternative for df.itertuples() where we add the index as named attributes to the tuple.
    This allows access to the index column in the same way as a regular column.
    This will make it much easier to access the values of the named index.

    Normally with df.itertuples() one must access the values of the Index by position, e.g.::

        for row in df.itertuples():
            (index_a, index_b) = row.Index
            print(index_a)

    One would have to ensure to extract all index columns and know the order in the Index.
    However, with this function we can do::

        for row in df_itertuples_with_index_names(df):
            print(row.index_a)

    Test::

        # Create a sample df
        index = pd.MultiIndex.from_product([range(2), range(3)], names=['index_a', 'index_b'])
        df = pd.DataFrame({'my_column': range(len(index))}, index=index)
        # Loop over itertuples alternative:
        for row in df_itertuples_with_index_names(df):
            print(row.index_a)

    Index columns are added at the tail of the tuple, so to be compatible with code that uses the position of the fields in the tuple.
    Inspired by https://stackoverflow.com/questions/46151666/iterate-over-pandas-dataframe-with-multiindex-by-index-names.

    Notes:
        * Does NOT work when df.Index has no names
    TODO: does not work if only Index and no columns
    TODO: test the combinations where row or Index are not tuples. Is row always a tuple?
    """
    Row = namedtuple("Row", ['Index', *df.columns, *df.index.names])
    for row in df.itertuples():
        # Option1 - Fails when Index is not a tuple
        # yield Row(*(row + row.Index))

        # Option 2 - In case the df has no columns?
        if isinstance(row.Index, tuple):
            yield Row(*(row + row.Index))
        else:
            yield Row(*row, row.Index)

        # Option 3 - not necessary?
        # if isinstance(row, tuple):
        #     if isinstance(row.Index, tuple):
        #         yield Row(*(row + row.Index))
        #     else:
        #         yield Row(*row,row.Index)
        # else:
        #     if isinstance(row.Index, tuple):
        #         yield Row(row, *row.Index)
        #     else:
        #         yield Row(row,row.Index)


        # if isinstance(row, tuple):
        # #
        # yield Row(*((row) + (row.Index)))
        # if isinstance(row, tuple):

