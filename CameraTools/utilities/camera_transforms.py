"""
CameraTransforms Utility
Role: Pure math for document <-> canonical space conversions.
Handles all transforms between document and canonical spaces, and their inverses.
No UI or controller logic.

Canonical space is defined as Y-up (Fusion's default), so all transforms map the document's up vector to canonical Y.
This allows all camera math to be performed consistently, regardless of the document's orientation.
"""

import adsk
import traceback
LOG_MODULE = 'camera_transforms'

from ..utilities import log_utils
log_utils.set_module_logging(LOG_MODULE, False)

app = adsk.core.Application.get()
ui = app.userInterface

def derive_document_up(design):
    """
    Derive the document's up vector from the front named view.
    This is much more reliable than guessing or using the root component orientation.
    Returns a normalized Vector3D.
    """
    try:           
        if not isinstance(design, adsk.fusion.Design):
            # No design context, fallback to Z-up (Fusion default)
            log_utils.log(app,'No active design - using default Z-up vector', level='INFO', module=LOG_MODULE)
            return adsk.core.Vector3D.create(0, 0, 1)
        
        # Use the front named view's camera up vector
        named_views = design.namedViews
        front_named_view = named_views.frontNamedView
        front_camera = front_named_view.camera
        up_axis = front_camera.upVector
        up_axis.normalize()

        log_utils.log(app,f'Derived up vector from front named view: ({up_axis.x:.3f}, {up_axis.y:.3f}, {up_axis.z:.3f})', level='DEBUG', module=LOG_MODULE)
        return up_axis
        
    except Exception as e:
        log_utils.log(app,f'❌ Failed to derive document up vector from named view: {str(e)}', level='ERROR', module=LOG_MODULE)
        # Fallback to Z-up
        log_utils.log(app,'Using default Z-up vector fallback', level='INFO', module=LOG_MODULE)
        return adsk.core.Vector3D.create(0, 0, 1)

def get_to_canonical_matrix(doc_up, adsk):
    """
    Returns a Matrix3D that rotates the document's up vector to canonical Y-up.
    This matrix can be used to transform points/vectors from document space to canonical space.
    """
    canonical_up = adsk.core.Vector3D.create(0, 1, 0)
    m = adsk.core.Matrix3D.create()
    m.setToRotateTo(doc_up, canonical_up)
    return m

def get_from_canonical_matrix(doc_up, adsk):
    """
    Returns a Matrix3D that rotates canonical Y-up to the document's up vector.
    This matrix can be used to transform points/vectors from canonical space back to document space.
    """
    canonical_up = adsk.core.Vector3D.create(0, 1, 0)
    m = adsk.core.Matrix3D.create()
    m.setToRotateTo(canonical_up, doc_up)
    return m

def transform_vector(vec, matrix, adsk):
    """
    Applies a Matrix3D transform to a Vector3D.
    Returns a new Vector3D in the transformed space.
    """
    v = adsk.core.Vector3D.create(vec.x, vec.y, vec.z)
    v.transformBy(matrix)
    return v

def transform_point(pt, matrix, adsk):
    """
    Applies a Matrix3D transform to a Point3D.
    Returns a new Point3D in the transformed space.
    """
    p = adsk.core.Point3D.create(pt.x, pt.y, pt.z)
    p.transformBy(matrix)
    return p

def to_canon_point(pt, doc_up, adsk):
    """
    Transform a Point3D from document space to canonical space.
    This rotates the point so that document up aligns with canonical Y.
    """
    to_canonical = get_to_canonical_matrix(doc_up, adsk)
    return transform_point(pt, to_canonical, adsk)

def to_canon_vector(vec, doc_up, adsk):
    """
    Transform a Vector3D from document space to canonical space.
    This rotates the vector so that document up aligns with canonical Y.
    """
    to_canonical = get_to_canonical_matrix(doc_up, adsk)
    return transform_vector(vec, to_canonical, adsk)

def from_canon_point(pt, doc_up, adsk):
    """
    Transform a Point3D from canonical space back to document space.
    This rotates the point so that canonical Y aligns with document up.
    """
    from_canonical = get_from_canonical_matrix(doc_up, adsk)
    return transform_point(pt, from_canonical, adsk)

def from_canon_vector(vec, doc_up, adsk):
    """
    Transform a Vector3D from canonical space back to document space.
    This rotates the vector so that canonical Y aligns with document up.
    """
    from_canonical = get_from_canonical_matrix(doc_up, adsk)
    return transform_vector(vec, from_canonical, adsk)