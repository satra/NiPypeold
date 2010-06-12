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

class ImageMathInputSpec(ANTSBaseInputSpec):
    image_dimension = traits.Enum(3, 2, position=1,
                                  argstr='%d', usedefault=True,
                                  desc='Image dimension')
    out_file = File(argstr="%s", position=2, genfile=True)
    
    in_file1 = File(exists=True, argstr="%s", mandatory=True, position=-2)
    in_file2 = traits.Either(traits.Float,
                             File(exists=True),argstr='%s',
                             position=-1)
    op_string = traits.Enum('*', '+', '-', '/', '^', 'exp', 'addtozero',
                            'overadd', 'abs', 'Decision',
                            argstr='%s',position=3)
    """
                            -- computes  result=1./(1.+exp(-1.0*( pix1-0.25)/pix2))  
   Neg (Produce Image Negative ) , 
   G Image1.ext s  (Smooth with Gaussian of sigma = s )  
 MD Image1.ext  s ( Morphological Dilation with radius s ) , 
  
 ME Image1.ext s ( Morphological Erosion with radius s ) , 
 
 MO Image1.ext s ( Morphological Opening with radius s ) 
 
 MC Image1.ext ( Morphological Closing with radius s ) 
 
  GD Image1.ext  s ( Grayscale Dilation with radius s ) , 
  
 GE Image1.ext s ( Grayscale Erosion with radius s ) , 
 
 GO Image1.ext s ( Grayscale Opening with radius s ) 
 
 GC Image1.ext ( Grayscale Closing with radius s ) 

 D (DistanceTransform) , 
   
 Segment Image1.ext N-Classes LocalityVsGlobalityWeight-In-ZeroToOneRange  OptionalPriorImages  ( Segment an Image  with option of Priors ,  weight 1 => maximally local/prior-based )  
 
 Grad Image.ext S ( Gradient magnitude with sigma s -- if normalize, then output in range [0, 1] ) , 
    
 Laplacian Image.ext S normalize? ( laplacian computed with sigma s --  if normalize, then output in range [0, 1] ) , 
    
 Normalize image.ext opt ( Normalize to [0,1] option instead divides by average value ) 
  
 PH (Print Header) , 
   Byte ( Convert to Byte image in [0,255] ) 
 
  LabelStats labelimage.ext valueimage.nii ( compute volumes / masses of objects in a label image -- write to text file ) 

  ROIStatistics labelimage.ext valueimage.nii ( see the code ) 

 DiceAndMinDistSum  LabelImage1.ext LabelImage2.ext OptionalDistImage  -- outputs DiceAndMinDistSum and Dice Overlap to text log file + optional distance image 
 
  Lipschitz   VectorFieldName  -- prints to cout  & writes to image   
 
  InvId VectorFieldName  VectorFieldName   -- prints to cout  & writes to image 
 
  GetLargestComponent InputImage {MinObjectSize}  -- get largest object in image 
 
  ThresholdAtMean  Image  %ofMean 
 
  FlattenImage  Image  %ofMax -- replaces values greater than %ofMax*Max to the value %ofMax*Max 
 
  CorruptImage Image  NoiseLevel Smoothing 
  TileImages NumColumns  ImageList* 
  RemoveLabelInterfaces ImageIn 
  EnumerateLabelInterfaces ImageIn ColoredImageOutname NeighborFractionToIgnore 
  FitSphere GM-ImageIn {WM-Image} {MaxRad-Default=5}
  PadImage ImageIn Pad-Number ( if Pad-Number is negative, de-Padding occurs ) 
  Where Image ValueToLookFor maskImage-option tolerance --- the where function from IDL 
  TensorFA DTImage  
  MakeImage  SizeX  SizeY {SizeZ}  
  SetOrGetPixel  ImageIn Get/Set-Value  IndexX  IndexY {IndexZ}  -- for example 
  ImageMath 2 outimage.nii SetOrGetPixel Image  Get 24 34 -- gets the value at 24, 34 
   ImageMath 2 outimage.nii SetOrGetPixel Image 1.e9  24 34  -- this sets 1.e9 as the value at 23 34  
 you can also pass a boolean at the end to force the physical space to be used 
  TensorMeanDiffusion DTImage  
  CompareHeadersAndImages Image1 Image2 --- tries to find and fix header error! output is the repaired image with new header 
  CountVoxelDifference Image1 Image2 Mask --- the where function from IDL 
  stack image1 image2  --- stack image2 onto image1  
  CorrelationUpdate Image1 Image2  RegionRadius --- in voxels , Compute update that makes Image2  more like Image1 
  ConvertImageToFile  imagevalues.nii {Optional-ImageMask.nii} -- will write voxel values to a file  
  PValueImage  TValueImage  dof  
  ConvertToGaussian  TValueImage  sigma-float  
  ConvertImageSetToMatrix  rowcoloption Mask.nii  *images.nii --  each row/column contains image content extracted from mask applied to images in *img.nii 
  ConvertVectorToImage   Mask.nii vector.nii  -- the vector contains image content extracted from a mask - here we return the vector to its spatial origins as image content 
  TriPlanarView  ImageIn.nii.gz PercentageToClampLowIntensity  PercentageToClampHiIntensity x-slice y-slice z-slice  
  FillHoles Image parameter : parameter = ratio of edge at object to edge at background = 1 is a definite hole bounded by object only, 0.99 is close -- default of parameter > 1 will fill all holes 
 PropagateLabelsThroughMask   speed/binaryimagemask.nii.gz   initiallabelimage.nii.gz Optional-Stopping-Value  -- final output is the propagated label image  
 optional stopping value -- higher values allow more distant propagation
 """

class ImageMathOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc="path/name of output file")

class ImageMath(ANTSBase):
    input_spec = ImageMathInputSpec
    output_spec = ImageMathOutputSpec
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
