"""The fsl module provides classes for interfacing with the `FSL
<http://www.fmrib.ox.ac.uk/fsl/index.html>`_ command line tools.  This
was written to work with FSL version 4.1.4.

Top-level namespace for fsl.  Perhaps should just make fsl a package!
"""

from nipype.interfaces.ants.base import Info
from nipype.interfaces.ants.preprocess import ANTS
from nipype.interfaces.ants.utils import ImageMath
