"""Define base classes for the ANTS package
"""

import os
import warnings

from nipype.utils.filemanip import fname_presuffix
from nipype.interfaces.base import CommandLine, traits, CommandLineInputSpec
from nipype.utils.misc import isdefined

warn = warnings.warn
warnings.filterwarnings('always', category=UserWarning)

class Info(object):
    """Return information about ANTS

    """

    ftypes = {'NIFTI': '.nii',
              'NIFTI_PAIR': '.img',
              'NIFTI_GZ': '.nii.gz',
              'NIFTI_PAIR_GZ': '.img.gz'}
    
    @staticmethod
    def version():
        """Check for ANTS version on system

        Parameters
        ----------
        None

        Returns
        -------
        None
        #version : str
        #   Version number as string or None if ANTS not found

        """
        raise Exception("Please ask brian to print out version info")

    @staticmethod
    def check():
        """Check if ANTS is available
        """
        ver = Info.version()
        if ver:
            return 0
        else:
            return 1
        
    @classmethod
    def output_type_to_ext(cls, output_type):
        """Get the file extension for the given output type.

        Parameters
        ----------
        output_type : {'NIFTI', 'NIFTI_GZ', 'NIFTI_PAIR', 'NIFTI_PAIR_GZ'}
            String specifying the output type.

        Returns
        -------
        extension : str
            The file extension for the output type.
        """

        try:
            return cls.ftypes[output_type]
        except KeyError:
            msg = 'Invalid ANTSOUTPUTTYPE: ', output_type
            raise KeyError(msg)

class ANTSBaseInputSpec(CommandLineInputSpec):
    """
    Base Input Specification for all ANTS Commands

    All command support specifying ANTSOUTPUTTYPE dynamically
    via output_type.
    
    Example
    -------
    ANTS.ExtractRoi(tmin=42, tsize=1, output_type='NIFTI')
    """
    output_type =  traits.Enum('NIFTI_GZ', Info.ftypes.keys(),
                              desc='ANTS output type')
    
class ANTSBase(CommandLine):
    """Base support for ANTS commands.
    
    """
    
    input_spec = ANTSBaseInputSpec
    _output_type = None

    def __init__(self, **inputs):
        super(ANTSBase, self).__init__(**inputs)

        if not isdefined(self.inputs.output_type) and \
                self._output_type:
            self.inputs.output_type = self._output_type
    
    @classmethod
    def set_default_output_type(cls, output_type):
        """Set the default output type for ANTS classes.

        This method is used to set the default output type for all ANTS
        subclasses.  However, setting this will not update the output
        type for any existing instances.  For these, assign the
        <instance>.inputs.output_type.
        """

        if output_type in Info.ftypes:
            cls._output_type = output_type
        else:
            raise AttributeError('Invalid ANTS output_type: %s' % output_type)

    def _gen_fname(self, basename, cwd=None, suffix=None, change_ext=True, ext=None):
        """Generate a filename based on the given parameters.

        The filename will take the form: cwd/basename<suffix><ext>.
        If change_ext is True, it will use the extentions specified in
        <instance>intputs.output_type.

        Parameters
        ----------
        basename : str
            Filename to base the new filename on.
        cwd : str
            Path to prefix to the new filename. (default is os.getcwd())
        suffix : str
            Suffix to add to the `basename`.  (defaults is '' )
        change_ext : bool
            Flag to change the filename extension to the ANTS output type.
            (default True)

        Returns
        -------
        fname : str
            New filename based on given parameters.

        """

        if basename == '':
            msg = 'Unable to generate filename for command %s. ' % self.cmd
            msg += 'basename is not set!'
            raise ValueError(msg)
        if cwd is None:
            cwd = os.getcwd()
        if ext is None:
            if isdefined(self.inputs.output_type):
                ext = Info.output_type_to_ext(self.inputs.output_type)
        if change_ext and ext:
            if suffix:
                suffix = ''.join((suffix, ext))
            else:
                suffix = ext
        if ext:
            fname = fname_presuffix(basename, suffix = suffix,
                                    use_ext = False, newpath = cwd)
        else:
            fname = fname_presuffix(basename, suffix = suffix, newpath = cwd)
        return fname

