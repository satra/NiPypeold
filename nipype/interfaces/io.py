# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
""" Set of interfaces that allow interaction with data. Currently
    available interfaces are:

    DataSource: Generic nifti to named Nifti interface
    DataSink: Generic named output from interfaces to data store
    XNATSource: preliminary interface to XNAT
    
    To come :
    XNATSink

    Change directory to provide relative paths for doctests
    >>> import os
    >>> filepath = os.path.dirname( os.path.realpath( __file__ ) )
    >>> datadir = os.path.realpath(os.path.join(filepath, '../testing/data'))
    >>> os.chdir(datadir)

"""
from copy import deepcopy
import glob
import os
import shutil
from warnings import warn

from enthought.traits.trait_errors import TraitError
try:
    from xnatlib import Interface as XNATInterface
except:
    pass

from nipype.interfaces.base import (Interface, CommandLine, Bunch,
                                    InterfaceResult, Interface,
                                    TraitedSpec, traits, File, Directory,
                                    BaseInterface, InputMultiPath,
                                    OutputMultiPath, DynamicTraitedSpec,
                                    BaseTraitedSpec, Undefined)
from nipype.utils.misc import isdefined
from nipype.utils.filemanip import (copyfile, list_to_filename,
                                    filename_to_list, FileNotFoundError)

import logging
iflogger = logging.getLogger('interface')

def add_traits(base, names, trait_type=None):
    """ Add traits to a traited class.

    All traits are set to Undefined by default
    """
    if trait_type is None:
        trait_type = traits.Any
    undefined_traits = {}
    for key in names:
        base.add_trait(key, trait_type)
        undefined_traits[key] = Undefined
    base.trait_set(trait_change_notify=False, **undefined_traits)
    # access each trait
    for key in names:
        value = getattr(base, key)
    return base

class IOBase(BaseInterface):

    def _run_interface(self, runtime):
        runtime.returncode = 0
        return runtime

    def _list_outputs(self):
        raise NotImplementedError

    def _outputs(self):
        return self._add_output_traits(super(IOBase, self)._outputs())
    
    def _add_output_traits(self, base):
        return base
    
class DataSinkInputSpec(DynamicTraitedSpec):
    base_directory = Directory( 
        desc='Path to the base directory for storing data.')
    container = traits.Str(desc = 'Folder within base directory in which to store output')
    parameterization = traits.Bool(True, usedefault=True,
                                   desc='store output in parameterized structure')
    strip_dir = Directory(desc='path to strip out of filename')
    substitutions = InputMultiPath(traits.Tuple(traits.Str,traits.Str),
                                   desc=('List of 2-tuples reflecting string'
                                         'to substitute and string to replace'
                                         'it with'))
    _outputs = traits.Dict(traits.Str, value={}, usedefault=True)
    
    def __setattr__(self, key, value):
        if key not in self.copyable_trait_names():
            self._outputs[key] = value
        else:
            super(DataSinkInputSpec, self).__setattr__(key, value)
    
class DataSink(IOBase):
    """ Generic datasink module to store structured outputs

        Primarily for use within a workflow. This interface all arbitrary
        creation of input attributes. The names of these attributes define the
        directory structure to create for storage of the files or directories.

        The attributes take the following form:
        string[[@|.]string[[@|.]string]] ...

        An attribute such as contrasts@con will create a contrasts directory to
        store the results linked to the attribute. If the @ is replaced with a
        '.', such as 'contrasts.con' a subdirectory 'con' will be created under
        contrasts.  

        Examples
        --------

        >>> ds = DataSink()
        >>> ds.inputs.base_directory = 'results_dir'
        >>> ds.inputs.container = 'subject'
        >>> ds.inputs.structural = 'structural.nii'
        >>> setattr(ds.inputs, 'contrasts@con', ['cont1.nii', 'cont2.nii'])
        >>> setattr(ds.inputs, 'contrasts.alt', ['cont1a.nii', 'cont2a.nii'])
        >>> ds.run() # doctest: +SKIP
        
    """
    input_spec = DataSinkInputSpec

    def _get_dst(self, src):
        path, fname = os.path.split(src)
        if self.inputs.parameterization:
            dst = path
            if isdefined(self.inputs.strip_dir):
                dst = dst.replace(self.inputs.strip_dir,'')
            folders = [folder for folder in dst.split(os.path.sep) if folder.startswith('_')]
            dst = os.path.sep.join(folders)
            if fname:
                dst = os.path.join(dst,fname)
        else:
            if fname:
                dst = fname
            else:
                dst = path.split(os.path.sep)[-1]
        if dst[0] == os.path.sep:
            dst = dst[1:]
        return dst

    def _substitute(self, pathstr):
        if isdefined(self.inputs.substitutions):
            for key, val in self.inputs.substitutions:
                iflogger.debug(str((pathstr, key, val)))
                pathstr = pathstr.replace(key, val)
                iflogger.debug('new: ' + pathstr)
        return pathstr
        
    def _list_outputs(self):
        """Execute this module.
        """
        outdir = self.inputs.base_directory
        if not isdefined(outdir):
            outdir = '.'
        outdir = os.path.abspath(outdir)
        if isdefined(self.inputs.container):
            outdir = os.path.join(outdir, self.inputs.container)
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        for key,files in self.inputs._outputs.items():
            iflogger.debug("key: %s files: %s"%(key, str(files)))
            files = filename_to_list(files)
            outfiles = []
            tempoutdir = outdir
            for d in key.split('.'):
                if d[0] == '@':
                    continue
                tempoutdir = os.path.join(tempoutdir,d)
            for src in filename_to_list(files):
                src = os.path.abspath(src)
                if os.path.isfile(src):
                    dst = self._get_dst(src)
                    dst = os.path.join(tempoutdir, dst)
                    dst = self._substitute(dst)
                    path,_ = os.path.split(dst)
                    if not os.path.exists(path):
                        os.makedirs(path)
                    iflogger.debug("copyfile: %s %s"%(src, dst))
                    copyfile(src, dst, copy=True)
                elif os.path.isdir(src):
                    dst = self._get_dst(os.path.join(src,''))
                    dst = os.path.join(tempoutdir, dst)
                    dst = self._substitute(dst)
                    path,_ = os.path.split(dst)
                    if not os.path.exists(path):
                        os.makedirs(path)
                    if os.path.exists(dst):
                        iflogger.debug("removing: %s"%dst)
                        shutil.rmtree(dst)
                    iflogger.debug("copydir: %s %s"%(src, dst))
                    shutil.copytree(src, dst)
        return None


class DataGrabberInputSpec(DynamicTraitedSpec): #InterfaceInputSpec):
    base_directory = Directory(exists=True,
            desc='Path to the base directory consisting of subject data.')
    template = traits.Str(mandatory=True,
             desc='Layout used to get files. relative to base directory if defined')
    template_args = traits.Dict(traits.Str,
                                traits.List(traits.List),
                                value=dict(outfiles=[]), usedefault=True,
                                desc='Information to plug into template')

class DataGrabber(IOBase):
    """ Generic datagrabber module that wraps around glob in an
        intelligent way for neuroimaging tasks to grab files


        .. note::
           Doesn't support directories currently

        Examples
        --------
        
        >>> from nipype.interfaces.io import DataGrabber

        Pick all files from current directory
        
        >>> dg = DataGrabber()
        >>> dg.inputs.template = '*'

        Pick file foo/foo.nii from current directory
        
        >>> dg.inputs.template = '%s/%s.dcm'
        >>> dg.inputs.template_args['outfiles']=[['dicomdir','123456-1-1.dcm']]

        Same thing but with dynamically created fields
        
        >>> dg = DataGrabber(infields=['arg1','arg2'])
        >>> dg.inputs.template = '%s/%s.nii'
        >>> dg.inputs.arg1 = 'foo'
        >>> dg.inputs.arg2 = 'foo'

        however this latter form can be used with iterables and iterfield in a
        pipeline.

        Dynamically created, user-defined input and output fields
        
        >>> dg = DataGrabber(infields=['sid'], outfields=['func','struct','ref'])
        >>> dg.inputs.base_directory = '.'
        >>> dg.inputs.template = '%s/%s.nii'
        >>> dg.inputs.template_args['func'] = [['sid',['f3','f5']]]
        >>> dg.inputs.template_args['struct'] = [['sid',['struct']]]
        >>> dg.inputs.template_args['ref'] = [['sid','ref']]
        >>> dg.inputs.sid = 's1'

        Change the template only for output field struct. The rest use the
        general template
        
        >>> dg.inputs.field_template = dict(struct='%s/struct.nii')
        >>> dg.inputs.template_args['struct'] = [['sid']]

    """
    input_spec = DataGrabberInputSpec
    output_spec = DynamicTraitedSpec

    def __init__(self, infields=None, outfields=None, **kwargs):
        """
        Parameters
        ----------
        infields : list of str
            Indicates the input fields to be dynamically created

        outfields: list of str
            Indicates output fields to be dynamically created

        See class examples for usage
        
        """
        super(DataGrabber, self).__init__(**kwargs)
        undefined_traits = {}
        # used for mandatory inputs check
        self._infields = infields
        if infields:
            for key in infields:
                self.inputs.add_trait(key, traits.Any)
                undefined_traits[key] = Undefined
            self.inputs.template_args['outfiles'] = [infields]
        if outfields:
            # add ability to insert field specific templates
            self.inputs.add_trait('field_template',
                                  traits.Dict(traits.Enum(outfields),
                                    desc="arguments that fit into template"))
            undefined_traits['field_template'] = Undefined
            #self.inputs.remove_trait('template_args')
            outdict = {}
            for key in outfields:
                outdict[key] = []
            self.inputs.template_args =  outdict
        self.inputs.trait_set(trait_change_notify=False, **undefined_traits)

    def _add_output_traits(self, base):
        """

        Using traits.Any instead out OutputMultiPath till add_trait bug
        is fixed.
        """
        return add_traits(base, self.inputs.template_args.keys())

    def _list_outputs(self):
        # infields are mandatory, however I could not figure out how to set 'mandatory' flag dynamically
        # hence manual check
        if self._infields:
            for key in self._infields:
                value = getattr(self.inputs,key)
                if not isdefined(value):
                    msg = "%s requires a value for input '%s' because it was listed in 'infields'" % \
                    (self.__class__.__name__, key)
                    raise ValueError(msg)
                
        outputs = {}
        for key, args in self.inputs.template_args.items():
            outputs[key] = []
            template = self.inputs.template
            if hasattr(self.inputs, 'field_template') and \
                    isdefined(self.inputs.field_template) and \
                    self.inputs.field_template.has_key(key):
                template = self.inputs.field_template[key]
            if isdefined(self.inputs.base_directory):
                template = os.path.join(os.path.abspath(self.inputs.base_directory), template)
            else:
                template = os.path.abspath(template)
            if not args:
                filelist = glob.glob(template)
                if len(filelist) == 0:
                    warn('Output key: %s Template: %s returned no files'%(key, template))
                else:
                    outputs[key] = list_to_filename(filelist)
            for argnum, arglist in enumerate(args):
                maxlen = 1
                for arg in arglist:
                    if isinstance(arg, str) and hasattr(self.inputs, arg):
                        arg = getattr(self.inputs, arg)
                    if isinstance(arg, list):
                        if (maxlen > 1) and (len(arg) != maxlen):
                            raise ValueError('incompatible number of arguments for %s' % key)
                        if len(arg)>maxlen:
                            maxlen = len(arg)
                outfiles = []
                for i in range(maxlen):
                    argtuple = []
                    for arg in arglist:
                        if isinstance(arg, str) and hasattr(self.inputs, arg):
                            arg = getattr(self.inputs, arg)
                        if isinstance(arg, list):
                            argtuple.append(arg[i])
                        else:
                            argtuple.append(arg)
                    filledtemplate = template
                    if argtuple:
                        filledtemplate = template%tuple(argtuple)
                    outfiles = glob.glob(filledtemplate)
                    if len(outfiles) == 0:
                        warn('Output key: %s Template: %s returned no files'%(key, filledtemplate))
                        outputs[key].insert(i, None)
                    else:
                        outputs[key].insert(i,list_to_filename(outfiles))
            if any([val==None for val in outputs[key]]):
                outputs[key] = []
            if len(outputs[key]) == 0:
                outputs[key] = None
            elif len(outputs[key]) == 1:
                outputs[key] = outputs[key][0]
        return outputs


class FSSourceInputSpec(TraitedSpec):
    subjects_dir = Directory(mandatory=True,
                             desc='Freesurfer subjects directory.')
    subject_id = traits.Str(mandatory=True,
                            desc='Subject name for whom to retrieve data')
    hemi = traits.Enum('both', 'lh', 'rh', usedefault=True,
                       desc='Selects hemisphere specific outputs')

class FSSourceOutputSpec(TraitedSpec):
    T1 = File(exists=True, desc='T1 image', loc='mri')
    aseg = File(exists=True, desc='Auto-seg image', loc='mri')
    brain = File(exists=True, desc='brain only image', loc='mri')
    brainmask = File(exists=True, desc='brain binary mask', loc='mri')
    filled = File(exists=True, desc='?', loc='mri')
    norm = File(exists=True, desc='intensity normalized image', loc='mri')
    nu = File(exists=True, desc='?', loc='mri')
    orig = File(exists=True, desc='original image conformed to FS space',
                loc='mri')
    rawavg = File(exists=True, desc='averaged input images to recon-all',
                  loc='mri')
    ribbon = OutputMultiPath(File(exists=True), desc='cortical ribbon', loc='mri',
                       altkey='*ribbon')
    wm = File(exists=True, desc='white matter image', loc='mri')
    wmparc = File(exists=True, desc='white matter parcellation', loc='mri')
    curv = OutputMultiPath(File(exists=True), desc='surface curvature files',
                     loc='surf')
    inflated = OutputMultiPath(File(exists=True), desc='inflated surface meshes',
                         loc='surf')
    pial = OutputMultiPath(File(exists=True), desc='pial surface meshes', loc='surf')
    smoothwm = OutputMultiPath(File(exists=True), loc='surf',
                         desc='smooth white-matter surface meshes')
    sphere = OutputMultiPath(File(exists=True), desc='spherical surface meshes',
                       loc='surf')
    sulc = OutputMultiPath(File(exists=True), desc='surface sulci files', loc='surf')
    thickness = OutputMultiPath(File(exists=True), loc='surf',
                          desc='surface thickness files')
    volume = OutputMultiPath(File(exists=True), desc='surface volume files', loc='surf')
    white = OutputMultiPath(File(exists=True), desc='white matter surface meshes',
                      loc='surf')
    label = OutputMultiPath(File(exists=True), desc='volume and surface label files',
                      loc='label', altkey='*label')
    annot = OutputMultiPath(File(exists=True), desc='surface annotation files',
                      loc='label', altkey='*annot')
    aparc_aseg = OutputMultiPath(File(exists=True), loc='mri', altkey='aparc*aseg',
                           desc='aparc+aseg file')
    sphere_reg = OutputMultiPath(File(exists=True), loc='surf', altkey='sphere.reg',
                           desc='spherical registration file')

class FreeSurferSource(IOBase):
    """Generates freesurfer subject info from their directories

    Examples
    --------

    >>> from nipype.interfaces.io import FreeSurferSource
    >>> fs = FreeSurferSource()
    >>> #fs.inputs.subjects_dir = '.'
    >>> fs.inputs.subject_id = 'PWS04'
    >>> res = fs.run() # doctest: +SKIP

    >>> fs.inputs.hemi = 'lh'
    >>> res = fs.run() # doctest: +SKIP

    """
    input_spec = FSSourceInputSpec
    output_spec = FSSourceOutputSpec

    def _get_files(self, path, key, dirval, altkey=None):
        globsuffix = ''
        if dirval == 'mri':
            globsuffix = '.mgz'
        globprefix = ''
        if key == 'ribbon' or dirval in ['surf', 'label']:
            if self.inputs.hemi != 'both':
                globprefix = self.inputs.hemi+'.'
            else:
                globprefix = '*'
        keydir = os.path.join(path,dirval)
        if altkey:
            key = altkey
        globpattern = os.path.join(keydir,''.join((globprefix,key,globsuffix)))
        return glob.glob(globpattern)
    
    def _list_outputs(self):
        subjects_dir = self.inputs.subjects_dir
        subject_path = os.path.join(subjects_dir, self.inputs.subject_id)
        output_traits = self._outputs()
        outputs = output_traits.get()
        for k in outputs.keys():
            val = self._get_files(subject_path, k,
                                  output_traits.traits()[k].loc,
                                  output_traits.traits()[k].altkey)
            if val:
                outputs[k] = list_to_filename(val)
        return outputs
        
        
        

class XNATSourceInputSpec(DynamicTraitedSpec): #InterfaceInputSpec):
    config_file = File(exists=True, mandatory=True,
                        desc='a json config file containing xnat access info: url, username and password')
    query_template = traits.Str(mandatory=True,
             desc='Layout used to get files. relative to base directory if defined')
    query_template_args = traits.Dict(traits.Str,
                                traits.List(traits.List),
                                value=dict(outfiles=[]), usedefault=True,
                                desc='Information to plug into template')

class XNATSource(IOBase):
    """ Generic XNATSource module that wraps around glob in an
        intelligent way for neuroimaging tasks to grab files

        Examples
        --------
        
        >>> from nipype.interfaces.io import XNATSource

        Pick all files from current directory
        
        >>> dg = XNATSource()
        >>> dg.inputs.template = '*'
        
        >>> dg = XNATSource(infields=['project','subject','experiment','assessor','inout'])
        >>> dg.inputs.query_template = '/projects/%s/subjects/%s/experiments/%s' \
                   '/assessors/%s/%s_resources/files'
        >>> dg.inputs.project = 'IMAGEN'
        >>> dg.inputs.subject = 'IMAGEN_000000001274'
        >>> dg.inputs.experiment = '*SessionA*'
        >>> dg.inputs.assessor = '*ADNI_MPRAGE_nii'
        >>> dg.inputs.inout = 'out'
        
        >>> dg = XNATSource(infields=['sid'],outfields=['struct','func'])
        >>> dg.inputs.query_template = '/projects/IMAGEN/subjects/%s/experiments/*SessionA*' \
                   '/assessors/*%s_nii/out_resources/files'
        >>> dg.inputs.query_template_args['struct'] = [['sid','ADNI_MPRAGE']]
        >>> dg.inputs.query_template_args['func'] = [['sid','EPI_faces']]
        >>> dg.inputs.sid = 'IMAGEN_000000001274'


    """
    input_spec = XNATSourceInputSpec
    output_spec = DynamicTraitedSpec

    def __init__(self, infields=None, outfields=None, **kwargs):
        """
        Parameters
        ----------
        infields : list of str
            Indicates the input fields to be dynamically created

        outfields: list of str
            Indicates output fields to be dynamically created

        See class examples for usage
        
        """
        super(XNATSource, self).__init__(**kwargs)
        undefined_traits = {}
        # used for mandatory inputs check
        self._infields = infields
        if infields:
            for key in infields:
                self.inputs.add_trait(key, traits.Any)
                undefined_traits[key] = Undefined
            self.inputs.query_template_args['outfiles'] = [infields]
        if outfields:
            # add ability to insert field specific templates
            self.inputs.add_trait('field_template',
                                  traits.Dict(traits.Enum(outfields),
                                    desc="arguments that fit into query_template"))
            undefined_traits['field_template'] = Undefined
            #self.inputs.remove_trait('query_template_args')
            outdict = {}
            for key in outfields:
                outdict[key] = []
            self.inputs.query_template_args =  outdict
        self.inputs.trait_set(trait_change_notify=False, **undefined_traits)

    def _add_output_traits(self, base):
        """

        Using traits.Any instead out OutputMultiPath till add_trait bug
        is fixed.
        """
        return add_traits(base, self.inputs.query_template_args.keys())

    def _list_outputs(self):
        # infields are mandatory, however I could not figure out how to set 'mandatory' flag dynamically
        # hence manual check
        config_info = load_json(self.inputs.config_file)
        cwd = os.getcwd()
        xnat = XNATInterface(config_info['url'], config_info['username'], config_info['password'], cachedir=cwd)
        if self._infields:
            for key in self._infields:
                value = getattr(self.inputs,key)
                if not isdefined(value):
                    msg = "%s requires a value for input '%s' because it was listed in 'infields'" % \
                    (self.__class__.__name__, key)
                    raise ValueError(msg)
                
        outputs = {}
        for key, args in self.inputs.query_template_args.items():
            outputs[key] = []
            template = self.inputs.query_template
            if hasattr(self.inputs, 'field_template') and \
                    isdefined(self.inputs.field_template) and \
                    self.inputs.field_template.has_key(key):
                template = self.inputs.field_template[key]
            if not args:
                file_objects = xnat.select(template).request_objects()
                if file_objects == []:
                    raise IOError('Template %s returned no files'%template)
                outputs[key] = list_to_filename([str(file_object.get()) for file_object in file_objects])
            for argnum, arglist in enumerate(args):
                maxlen = 1
                for arg in arglist:
                    if isinstance(arg, str) and hasattr(self.inputs, arg):
                        arg = getattr(self.inputs, arg)
                    if isinstance(arg, list):
                        if (maxlen > 1) and (len(arg) != maxlen):
                            raise ValueError('incompatible number of arguments for %s' % key)
                        if len(arg)>maxlen:
                            maxlen = len(arg)
                outfiles = []
                for i in range(maxlen):
                    argtuple = []
                    for arg in arglist:
                        if isinstance(arg, str) and hasattr(self.inputs, arg):
                            arg = getattr(self.inputs, arg)
                        if isinstance(arg, list):
                            argtuple.append(arg[i])
                        else:
                            argtuple.append(arg)
                    if argtuple:
                        file_objects = xnat.select(template%tuple(argtuple)).request_objects()
                        if file_objects == []:
                            raise IOError('Template %s returned no files'%(template%tuple(argtuple)))
                        outfiles = list_to_filename([str(file_object.get()) for file_object in file_objects])
                    else:
                        file_objects = xnat.select(template).request_objects()
                        if file_objects == []:
                            raise IOError('Template %s returned no files'%template)
                        outfiles = list_to_filename([str(file_object.get()) for file_object in file_objects])
                    outputs[key].insert(i,outfiles)
            if len(outputs[key]) == 0:
                outputs[key] = None
            elif len(outputs[key]) == 1:
                outputs[key] = outputs[key][0]
        return outputs


