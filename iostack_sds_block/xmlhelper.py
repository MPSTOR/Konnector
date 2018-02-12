# -*- coding: utf-8 -*-
# Michael Breen
# Copyright (C) 2013 MPSTOR mpstor.com

import xml.dom.minidom as minidom


def get_versioned_message(xml_message, supported_versions):
    """Returns (dom, version) where 'dom' is the parsed XML
    excluding those elements for versions other than 'version',
    and 'version' is the first version in the 'version' attribute
    of the document (root) element which is also in the sequence
    'supported_versions'.
    Versions are positive integers; version 0 indicates the absence
    of a version number, i.e., an unversioned message.
    Raises an exception in the event of an error, or if none of
    the document element's versions are in 'supported_versions'.
    (The string representation of the exception can be used as the
    text of an 'error' element's 'message' attribute in a response
    message.)
    """
    supported = [str(x) for x in supported_versions]
    dom = minidom.parseString(xml_message)
    root = dom.childNodes[0]
    try:
        all = root.attributes['version'].value.split(',')
    except:
        all = ['0']
    try:
        version = [x for x in all if x in supported][0]
    except:
        raise Exception('XML protocol version not supported.')
    _keep_only(version, root)
    return root, int(version)


def _keep_only(version, node):
    """Remove from 'node' any descendent element which has a version list
    which does not include 'version'.
    """
    to_remove = []
    for child in node.childNodes:
        versions = None
        try:
            versions = child.attributes['version'].value.split(',')
        except:
            versions = None
        if versions and version not in versions:
            to_remove.append(child)
        else:
            _keep_only(version, child)
    for child in to_remove:
        node.removeChild(child)
