# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""The spm module provides basic functions for interfacing with SPM  tools."""


from nipype.interfaces.traits import Directory
__docformat__ = 'restructuredtext'

# Standard library imports
import os
from copy import deepcopy
import re

# Third-party imports
import numpy as np
from scipy.io import savemat

# Local imports
from nipype.interfaces.base import BaseInterface, traits, TraitedSpec,\
    InputMultiPath
from nipype.utils.misc import isdefined
from nipype.externals.pynifti import load
from nipype.interfaces.matlab import MatlabCommand

import nipype.utils.spm_docs as sd
                                    
import logging
logger = logging.getLogger('iflogger')

def func_is_3d(in_file):
    """Checks if input functional files are 3d."""
    
    if isinstance(in_file, list):
        return func_is_3d(in_file[0])
    else:
        img = load(in_file)
        shape = img.get_shape() 
        if len(shape) == 3 or (len(shape)==4 and shape[3]==1):
            return True
        else:
            return False
        
def get_first_3dfile(in_files):
    if not func_is_3d(in_files):
        return None
    if isinstance(in_files[0], list):
        return in_files[0]
    return in_files    

def scans_for_fname(fname):
    """Reads a nifti file and converts it to a numpy array storing
    individual nifti volumes.
    
    Opens images so will fail if they are not found.
    
    """
    if isinstance(fname,list):
        scans = np.zeros((len(fname),),dtype=object)
        for sno,f in enumerate(fname):
            scans[sno] = '%s,1'%f
        return scans
    img = load(fname)
    if len(img.get_shape()) == 3:
        return np.array(('%s,1'%fname,),dtype=object)
    else:
        n_scans = img.get_shape()[3]
        scans = np.zeros((n_scans,),dtype=object)
        for sno in range(n_scans):
            scans[sno] = '%s,%d'% (fname, sno+1)
        return scans

def scans_for_fnames(fnames,keep4d=False,separate_sessions=False):
    """Converts a list of files to a concatenated numpy array for each
    volume.

    keep4d : boolean
        keeps the entries of the numpy array as 4d files instead of
        extracting the individual volumes.
    separate_sessions: boolean
        if 4d nifti files are being used, then separate_sessions
        ensures a cell array per session is created in the structure.
        
    """
    flist = None
    if not isinstance(fnames[0], list):
        if func_is_3d(fnames[0]):
            fnames = [fnames]
    if separate_sessions or keep4d:
        flist = np.zeros((len(fnames),),dtype=object)
    for i,f in enumerate(fnames):
        if separate_sessions:
            if keep4d:
                if isinstance(f,list):
                    flist[i] = np.array(f, dtype=object)
                else:
                    flist[i] = np.array([f],dtype=object)
            else:
                flist[i] = scans_for_fname(f)
        else:
            if keep4d:
                flist[i] = f
            else:
                scans = scans_for_fname(f)
                if flist is None:
                    flist = scans
                else:
                    flist = np.concatenate((flist,scans))
    return flist

class Info(object):
    """Handles SPM version information
    """
    @staticmethod
    def version( matlab_cmd = None ):
        """Returns the path to the SPM directory in the Matlab path
        If path not found, returns None.

        Parameters
        ----------
        matlab_cmd : String specifying default matlab command
        
            default None, will look for environment variable MATLABCMD
            and use if found, otherwise falls back on MatlabCommand
            default of 'matlab -nodesktop -nosplash'

        Returns
        -------
        spm_path : string representing path to SPM directory

            returns None of path not found
        """
        if matlab_cmd is None:
            try:
                matlab_cmd = os.environ['MATLABCMD']
            except:
                matlab_cmd = 'matlab -nodesktop -nosplash'
        mlab = MatlabCommand(matlab_cmd = matlab_cmd)
        mlab.inputs.script_file = 'spminfo'
        mlab.inputs.script = """
        if isempty(which('spm')),
        throw(MException('SPMCheck:NotFound','SPM not in matlab path'));
        end;
        spm_path = spm('dir');
        fprintf(1, 'NIPYPE  %s', spm_path);
        """
        out = mlab.run()
        if out.runtime.returncode == 0:
            spm_path = sd._strip_header(out.runtime.stdout)
        else:
            logger.debug(out.runtime.stderr)
            return None
        return spm_path


def no_spm():
    """ Checks if SPM is NOT installed
    used with nosetests skipif to skip tests
    that will fail if spm is not installed"""

    if Info.version() == None:
        return True
    else:
        return False

    
class SPMCommandInputSpec(TraitedSpec):
    matlab_cmd = traits.Str()
    paths = InputMultiPath(Directory(), desc='Paths to add to matlabpath')
    mfile = traits.Bool(True, desc='Run m-code using m-file',
                          usedefault=True)

class SPMCommand(BaseInterface):
    """Extends `BaseInterface` class to implement SPM specific interfaces.
    
    WARNING: Pseudo prototype class, meant to be subclassed
    """
    input_spec = SPMCommandInputSpec

    _jobtype = 'basetype'
    _jobname = 'basename'
    
    def __init__(self, **inputs):
        super(SPMCommand, self).__init__(**inputs)
        self.inputs.on_trait_change(self._matlab_cmd_update, 'matlab_cmd')
        self._matlab_cmd_update()
        
    def _matlab_cmd_update(self):
        # MatlabCommand has to be created here,
        # because matlab_cmb is not a proper input
        # and can be set only during init
        self.mlab = MatlabCommand(matlab_cmd=self.inputs.matlab_cmd,
                                      mfile=self.inputs.mfile,
                                      paths=self.inputs.paths)
        self.mlab.inputs.script_file = 'pyscript_%s.m' % \
        self.__class__.__name__.split('.')[-1].lower()
        
    @property
    def jobtype(self):
        return self._jobtype

    @property
    def jobname(self):
        return self._jobname

    def use_mfile(self, use_mfile):
        """boolean,
        if true generates a matlab <filename>.m file
        if false generates a binary .mat file
        """
        self.inputs.mfile = use_mfile

    def _run_interface(self, runtime):
        """Executes the SPM function using MATLAB."""
        
        if isdefined(self.inputs.mfile):
            self.mlab.inputs.mfile = self.inputs.mfile
        if isdefined(self.inputs.paths):
            self.mlab.inputs.paths = self.inputs.paths
        self.mlab.inputs.script = self._make_matlab_command(deepcopy(self._parse_inputs()))
        results = self.mlab.run()
        runtime.returncode = results.runtime.returncode
        runtime.stdout = results.runtime.stdout
        runtime.stderr = results.runtime.stderr
        return runtime
    
    def _list_outputs(self):
        """Determine the expected outputs based on inputs."""
        
        raise NotImplementedError
    
        
    def _format_arg(self, opt, spec, val):
        """Convert input to appropriate format for SPM."""
        
        return val
    
    def _parse_inputs(self, skip=()):
        spmdict = {}
        metadata=dict(field=lambda t : t is not None)
        for name, spec in self.inputs.traits(**metadata).items():
            if skip and name in skip:
                continue
            value = getattr(self.inputs, name)
            if not isdefined(value):
                continue
            field = spec.field
            if '.' in field:
                fields = field.split('.')
                dictref = spmdict
                for f in fields[:-1]:
                    if f not in dictref.keys():
                        dictref[f] = {}
                    dictref = dictref[f]
                dictref[fields[-1]] = self._format_arg(name, spec, value)
            else:
                spmdict[field] = self._format_arg(name, spec, value)
        return [spmdict]
    
    def _reformat_dict_for_savemat(self, contents):
        """Encloses a dict representation within hierarchical lists.

        In order to create an appropriate SPM job structure, a Python
        dict storing the job needs to be modified so that each dict
        embedded in dict needs to be enclosed as a list element.

        Examples
        --------
        >>> a = SPMCommand()._reformat_dict_for_savemat(dict(a=1,b=dict(c=2,d=3)))
        >>> print a
        [{'a': 1, 'b': [{'c': 2, 'd': 3}]}]
        
        """
        newdict = {}
        try:
            for key, value in contents.items():
                if isinstance(value, dict):
                    if value:
                        newdict[key] = self._reformat_dict_for_savemat(value)
                    # if value is None, skip
                else:
                    newdict[key] = value
                
            return [newdict]
        except TypeError:
            print 'Requires dict input'

    def _generate_job(self, prefix='', contents=None):
        """Recursive function to generate spm job specification as a string

        Parameters
        ----------
        prefix : string
            A string that needs to get  
        contents : dict
            A non-tuple Python structure containing spm job
            information gets converted to an appropriate sequence of
            matlab commands.
            
        """
        jobstring = ''
        if contents is None:
            return jobstring
        if isinstance(contents, list):
            for i,value in enumerate(contents):
                newprefix = "%s(%d)" % (prefix, i+1)
                jobstring += self._generate_job(newprefix, value)
            return jobstring
        if isinstance(contents, dict):
            for key,value in contents.items():
                newprefix = "%s.%s" % (prefix, key)
                jobstring += self._generate_job(newprefix, value)
            return jobstring
        if isinstance(contents, np.ndarray):
            if contents.dtype == np.dtype(object):
                if prefix:
                    jobstring += "%s = {...\n"%(prefix)
                else:
                    jobstring += "{...\n"
                for i,val in enumerate(contents):
                    if isinstance(val, np.ndarray):
                        jobstring += self._generate_job(prefix=None,
                                                        contents=val)
                    elif isinstance(val,str):
                        jobstring += '\'%s\';...\n'%(val)
                    else:
                        jobstring += '%s;...\n'%str(val)
                jobstring += '};\n'
            else:
                for i,val in enumerate(contents):
                    for field in val.dtype.fields:
                        if prefix:
                            newprefix = "%s(%d).%s"%(prefix, i+1, field)
                        else:
                            newprefix = "(%d).%s"%(i+1, field)
                        jobstring += self._generate_job(newprefix,
                                                        val[field])
            return jobstring
        if isinstance(contents, str):
            jobstring += "%s = '%s';\n" % (prefix,contents)
            return jobstring
        jobstring += "%s = %s;\n" % (prefix,str(contents))
        return jobstring
    
    def _make_matlab_command(self, contents, postscript=None):
        """Generates a mfile to build job structure
        Parameters
        ----------

        contents : list
            a list of dicts generated by _parse_inputs
            in each subclass

        cwd : string
            default os.getcwd()

        Returns
        -------
        mscript : string
            contents of a script called by matlab
            
        """
        cwd = os.getcwd()
        mscript  = """
        %% Generated by nipype.interfaces.spm
        if isempty(which('spm')),
             throw(MException('SPMCheck:NotFound','SPM not in matlab path'));
        end
        fprintf('SPM version: %s\\n',spm('ver'));
        fprintf('SPM path: %s\\n',which('spm'));
        spm('Defaults','fMRI');
                  
        if strcmp(spm('ver'),'SPM8'), spm_jobman('initcfg');end\n
        """
        if self.mlab.inputs.mfile:
            if self.jobname in ['st','smooth','preproc','preproc8','fmri_spec','fmri_est',
                                'factorial_design'] :
                # parentheses
                mscript += self._generate_job('jobs{1}.%s{1}.%s(1)' %
                                              (self.jobtype,self.jobname), contents[0])
            else:
                #curly brackets
                mscript += self._generate_job('jobs{1}.%s{1}.%s{1}' %
                                              (self.jobtype,self.jobname), contents[0])
        else:
            jobdef = {'jobs':[{self.jobtype:[{self.jobname:self.reformat_dict_for_savemat
                                         (contents[0])}]}]}
            savemat(os.path.join(cwd,'pyjobs_%s.mat'%self.jobname), jobdef)
            mscript += "load pyjobs_%s;\n\n" % self.jobname
        mscript += """ 
        if strcmp(spm('ver'),'SPM8'), 
           jobs=spm_jobman('spm5tospm8',{jobs});
        end 
        spm_jobman(\'run\',jobs);\n
        """
        if postscript is not None:
            mscript += postscript
        return mscript
