"""Drop-in for the `cython_bbox` package (does not build with numpy 2): same +1 pixel convention as the original."""
import numpy as np


def bbox_overlaps(boxes, query_boxes):
    boxes = np.asarray(boxes, dtype=np.float64)
    query_boxes = np.asarray(query_boxes, dtype=np.float64)
    if boxes.size == 0 or query_boxes.size == 0:
        return np.zeros((len(boxes), len(query_boxes)), dtype=np.float64)
    b = boxes[:, None, :]
    q = query_boxes[None, :, :]
    iw = np.minimum(b[..., 2], q[..., 2]) - np.maximum(b[..., 0], q[..., 0]) + 1
    ih = np.minimum(b[..., 3], q[..., 3]) - np.maximum(b[..., 1], q[..., 1]) + 1
    inter = np.clip(iw, 0, None) * np.clip(ih, 0, None)
    area_b = (b[..., 2] - b[..., 0] + 1) * (b[..., 3] - b[..., 1] + 1)
    area_q = (q[..., 2] - q[..., 0] + 1) * (q[..., 3] - q[..., 1] + 1)
    ua = area_b + area_q - inter
    return np.where(inter > 0, inter / ua, 0.0)
