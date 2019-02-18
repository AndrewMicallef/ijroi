# Copyright: Luis Pedro Coelho <luis@luispedro.org>, 2012
#            Tim D. Smith <git@tim-smith.us>, 2015
# License: MIT

from io import BytesIO
import zipfile

import numpy as np


def read_roi(fileobj):
    '''
    points = read_roi(fileobj)

    Read ImageJ's ROI format. Points are returned in a nx2 array. Each row
    is in [row, column] -- that is, (y,x) -- order.
    '''
    # This is based on:
    # http://rsbweb.nih.gov/ij/developer/source/ij/io/RoiDecoder.java.html
    # http://rsbweb.nih.gov/ij/developer/source/ij/io/RoiEncoder.java.html

    SPLINE_FIT = 1
    DOUBLE_HEADED = 2
    OUTLINE = 4
    OVERLAY_LABELS = 8
    OVERLAY_NAMES = 16
    OVERLAY_BACKGROUNDS = 32
    OVERLAY_BOLD = 64
    SUB_PIXEL_RESOLUTION = 128
    DRAW_OFFSET = 256

    class RoiType:
        POLYGON = 0
        RECT = 1
        OVAL = 2
        LINE = 3
        FREELINE = 4
        POLYLINE = 5
        NOROI = 6
        FREEHAND = 7
        TRACED = 8
        ANGLE = 9
        POINT = 10

    def get8():
        s = fileobj.read(1)
        if not s:
            raise IOError('readroi: Unexpected EOF')
        return ord(s)

    def get16():
        b0 = get8()
        b1 = get8()
        return (b0 << 8) | b1

    def get32():
        s0 = get16()
        s1 = get16()
        return (s0 << 16) | s1

    def getfloat():
        v = np.int32(get32())
        return v.view(np.float32)

    #===========================================================================
    #Read Header data
    
    magic = fileobj.read(4)
    if magic != b'Iout':
        raise ValueError('Magic number not found')
    version = get16()

    # It seems that the roi type field occupies 2 Bytes, but only one is used
    roi_type = get8()
    # Discard second Byte:
    get8()
    
    top = get16()
    left = get16()
    bottom = get16()
    right = get16()
    n_coordinates = get16()
    x1 = getfloat()
    y1 = getfloat()
    x2 = getfloat()
    y2 = getfloat()
    stroke_width = get16()
    shape_roi_size = get32()
    stroke_color = get32()
    fill_color = get32()
    subtype = get16()
    
    options = get16()
    arrow_style = get8()
    arrow_head_size = get8()
    rect_arc_size = get16()
    position = get32()
    header2offset = get32()

    # End Header data
    #===========================================================================

    #RoiDecoder.java#L177
    subPixelResolution = ((options&SUB_PIXEL_RESOLUTION)!=0) and (version>=222)
    
    # Check exceptions
    
    if roi_type not in [RoiType.FREEHAND, RoiType.TRACED, RoiType.POLYGON, RoiType.RECT, RoiType.POINT]:
        raise NotImplementedError('roireader: ROI type %s not supported' % roi_type)
        
    if subtype != 0:
        raise NotImplementedError('roireader: ROI subtype %s not supported (!= 0)' % subtype)
    
    #Composite ROI
    if shape_roi_size > 0:
        coords_bytes = file_obj.read()
        buffer = np.frombuffer(coords_bytes, dtype='>f4', count=shape_roi_size)
        
        segments = []
        
        # the number of units to read depens on the type of segement...
        # this only works with basic line segemnts (ie type 1, type 2 is quadratic
        # and type 3 is cubic
        
        rc = {4:1, 0:3, 1:3, 2:5, 3:7}

        # scrolls through the buffer one line segment at a time,
        # line segments are stored as x,y tuples, I reverse the
        # segment, in order to remain consitant with the other return types
        i = 0
        these_points = []
        while i < buffer.size:
            _type = buffer[i]
            read_len = rc[_type]
            seg = buffer[i+1:i+read_len]
            if seg.size == 0:
                segments.append(np.r_[these_points])
                these_points = []
                
            else:
                these_points.append(seg[::-1])
            
            i = i+read_len
        
        return segments
        
        
    if roi_type == RoiType.RECT:
        if subPixelResolution:
            return np.array(
                [[y1, x1], [y1, x1+x2], [y1+y2, x1+x2], [y1+y2, x1]],
                dtype=np.float32)
        else:
            return np.array(
                [[top, left], [top, right], [bottom, right], [bottom, left]],
                dtype=np.int16)

    if subPixelResolution:
        getc = getfloat
        points = np.empty((n_coordinates, 2), dtype=np.float32)
        fileobj.seek(4*n_coordinates, 1)
    else:
        getc = get16
        points = np.empty((n_coordinates, 2), dtype=np.int16)

    points[:, 1] = [getc() for i in range(n_coordinates)]
    points[:, 0] = [getc() for i in range(n_coordinates)]

    if subPixelResolution == 0:
        points[:, 1] += left
        points[:, 0] += top

    return points


def read_roi_zip(fname):
    with zipfile.ZipFile(fname) as zf:
        return[(n, read_roi(BytesIO(zf.read(n)))) for n in zf.namelist()]
