import os
from glob import glob
import warnings

import numpy as np

from nipype.interfaces.ants.base import (ANTSBase, ANTSBaseInputSpec)
from nipype.interfaces.base import (traits, TraitedSpec,
                                    InputMultiPath, OutputMultiPath, File)
from nipype.utils.misc import isdefined

warn = warnings.warn
warnings.filterwarnings('always', category=UserWarning)

class ANTSInputSpec(ANTSBaseInputSpec):
    image_dimension = traits.Enum(3, 2, position=1,
                                  argstr='%d', usedefault=True,
                                  desc='Image dimension')
    out_file = File(argstr="--output-naming=%s", genfile=True,
                    desc='output file name')
    mask_file = File(exists=True, argstr='--mask-image=%s',
                     desc='mask file name in target image space')
    target_file = File(exists=True, argstr='%s', mandatory=True,
                       desc='target file name')
    source_file = File(exists=True, argstr='%s', mandatory=True,
                       desc='source file name')
    image_metric = traits.Enum('PR', 'MI', 'CC', 'MSQ', 'PSE', 'JTB',
                               argstr='%s',
                               desc='image metric')
    metric_options = traits.Str('1,4', usedefault=True,
                                desc='additional options')
    level_iterations = traits.List(traits.Int,
                                    argstr='%d', mandatory=True,
                                    desc='number of iterations per level e.g. [100,100,20]')
    transformation_model = traits.Enum('Syn','Diff', 'Elast', 'Exp',
                                       usedefault=True,
                                       argstr='', desc='transformation model')
    gradient_step_length = traits.Float(0.25, argstr='', usedefault=True,
                                        desc='gradient step length')
    num_time_steps = traits.Int(argstr='',desc='number of time steps')
    delta_time = traits.Float(argstr='', desc='number of time steps')
    symmetry_type = traits.Enum(0,1,argstr='',desc='what is symmetry type??')
    regularization = traits.Enum('Gauss', 'DMFFD', usedefault=True
                                 argstr='--regularization=%s',
                                 desc='type of regularization')
    gradient_field_sigma = traits.Float(3, argstr='',
                                        desc='gradient field sigma')
    def_field_sigma = traits.Float(0, argstr='',
                                   desc='def field sigma')
    source_init_affine_file = File(exists=True, argstr='--initial-affine=%s',
                            desc='initial affine transformation file')
    target_init_affine_file = File(exists=True, argstr='--fixed-image-initial-affine=%s',
                                   desc='target file init affine')
    compute_thickness = traits.Bool(argstr='--compute-thickness',
                                    desc='compute the Euclidean length of the
    diffeomorphism and write to an image -- OutputNamethick.nii.gz -- This is a
    Beta version of thickness computation -- Not Full-Blown DiReCT , Das, 2009,
    Neuroimage ---  syn with time is the only model that can be used with this
    option'
                                    )
    compute_affine = traits.Bool(argstr='--continue-affine',
                                 desc='compute affine (after applying init affine files if any)') 
    num_affine_iterations =  traits.Tuple(traits.Int, traits.Int, traits.Int,
                                    argstr='%dx%dx%d', mandatory=True,
                                    desc='number of iterations per level e.g. (100,100,20)')
    """
       --number-of-affine-iterations: 
              number of iterations per level -- a 'vector' e.g.  :  100x100x20 
       --use-NN: 
       --use-Histogram-Matching: 
       --affine-metric-type: 
       --MI-option: 
       --rigid-affine: 
       --affine-gradient-descent-option: 
       --use-rotation-header: 
       --ignore-void-origin: 
 """
    
    
Intensity-Based Metrics: 
		CC/cross-correlation/CrossCorrelation[fixedImage,movingImage,weight,radius/OrForMI-#histogramBins]
		MI/mutual-information/MutualInformation[fixedImage,movingImage,weight,radius/OrForMI-#histogramBins]
		PR/probabilistic/Probabilistic[fixedImage,movingImage,weight,radius/OrForMI-#histogramBins]
		MSQ/mean-squares/MeanSquares[fixedImage,movingImage,weight,radius/OrForMI-#histogramBins]
	      Point-Set-Based Metrics: 
		PSE/point-set-expectation/PointSetExpectation[fixedImage,movingImage,fixedPoints,movingPoints,weight,pointSetPercentage,pointSetSigma,boundaryPointsOnly,kNeighborhood, PartialMatchingIterations=100000]   
 the partial matching option assumes the complete labeling is in the first set of label parameters ... more iterations leads to more symmetry in the matching  - 0 iterations means full asymmetry 
		JTB/jensen-tsallis-bspline/JensenTsallisBSpline[fixedImage,movingImage,fixedPoints,movingPoints,weight,pointSetPercentage,pointSetSigma,boundaryPointsOnly,kNeighborhood,alpha,meshResolution,splineOrder,numberOfLevels,useAnisotropicCovariances]    

class ANTSOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc="path/name of output file")

class ANTS(ANTSBase):
    input_spec = ANTSInputSpec
    output_spec = ANTSOutputSpec
    _cmd = 'ImageMath'

    def _format_arg(self, name, spec, value):
        if name == 'in_file2':
            return spec.argstr % str(value)
        return super(ImageMath, self)._format_arg(name, spec, value)
    
    def _gen_filename(self, name):
        if name == 'out_file':
            return self._list_outputs()[name]
        return None
    
    def _list_outputs(self):
        suffix = '_maths'
        outputs = self._outputs().get()
        outputs['out_file'] = self.inputs.out_file
        if not isdefined(outputs['out_file']):
            outputs['out_file'] = self._gen_fname(self.inputs.in_file1,
                                              suffix=suffix)
        return outputs
