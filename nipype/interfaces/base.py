"""
Package contains interfaces for using existing functionality in other packages

Exaples  FSL, matlab/SPM , afni

Requires Packages to be installed
"""

import os
import subprocess
from copy import deepcopy
from socket import gethostname
from string import Template
from time import time
from warnings import warn

from nipype.utils.filemanip import md5
from nipype.utils.misc import is_container

 
__docformat__ = 'restructuredtext'

def load_template(name):
    """Load a template from the script_templates directory

    Parameters
    ----------
    name : str
        The name of the file to load

    Returns
    -------
    template : string.Template

    """

    full_fname = os.path.join(os.path.dirname(__file__),
                              'script_templates', name)
    template_file = open(full_fname)
    template = Template(template_file.read())
    template_file.close()
    return template

class Bunch(object):
    """Dictionary-like class that provides attribute-style access to it's items.

    A `Bunch` is a simple container that stores it's items as class
    attributes.  Internally all items are stored in a dictionary and
    the class exposes several of the dictionary methods.

    Examples
    --------
    >>> from nipype.interfaces.base import Bunch
    >>> inputs = Bunch(infile='subj.nii', fwhm=6.0, register_to_mean=True)
    >>> inputs
    Bunch(fwhm=6.0, infile='subj.nii', register_to_mean=True)
    >>> inputs.register_to_mean = False
    >>> inputs
    Bunch(fwhm=6.0, infile='subj.nii', register_to_mean=False)
    

    Notes
    -----
    The Bunch pattern came from the Python Cookbook:
    
    .. [1] A. Martelli, D. Hudgeon, "Collecting a Bunch of Named
           Items", Python Cookbook, 2nd Ed, Chapter 4.18, 2005.

    """
    def __init__(self, *args, **kwargs):
        self.__dict__.update(*args, **kwargs)

    def update(self, *args, **kwargs):
        """update existing attribute, or create new attribute
        
        Note: update is very much like HasTraits.set"""
        self.__dict__.update(*args, **kwargs)

    def items(self):
        """iterates over bunch attributes as key,value pairs"""
        return self.__dict__.items()

    def iteritems(self):
        """iterates over bunch attributes as key,value pairs"""
        warn('iteritems is deprecated, use items instead')
        return self.items()

    def get(self, *args):
        '''Support dictionary get() functionality 
        '''
        return self.__dict__.get(*args)

    def dictcopy(self):
        """returns a deep copy of existing Bunch as a dictionary"""
        return deepcopy(self.__dict__)

    def __repr__(self):
        """representation of the sorted Bunch as a string

        Currently, this string representation of the `inputs` Bunch of
        interfaces is hashed to determine if the process' dirty-bit
        needs setting or not. Till that mechanism changes, only alter
        this after careful consideration.
        """
        outstr = ['Bunch(']
        first = True
        for k, v in sorted(self.items()):
            if not first:
                outstr.append(', ')
            outstr.append('%s=%r' % (k, v))
            first = False
        outstr.append(')')
        return ''.join(outstr)

    def _hash_infile(self,adict, key):
        # Inject file hashes into adict[key]
        stuff = adict[key]
        if not is_container(stuff):
            stuff = [stuff]
        file_list = []
        for afile in stuff:
            if os.path.isfile(afile):
                md5obj = md5()
                fp = file(afile, 'rb')
                while True:
                    data = fp.read(8192)
                    if not data:
                        break
                    md5obj.update(data)
                fp.close()
                md5hex = md5obj.hexdigest()
            else:
                md5hex = None
            file_list.append((afile,md5hex ))
        return file_list

    def _get_bunch_hash(self):
        """Return a dictionary of our items with hashes for each file.

        Searches through dictionary items and if an item is a file, it
        calculates the md5 hash of the file contents and stores the
        file name and hash value as the new key value.

        However, the overall bunch hash is calculated only on the hash
        value of a file. The path and name of the file are not used in
        the overall hash calculation.

        Returns
        -------
        dict_withhash : dict
            Copy of our dictionary with the new file hashes included
            with each file.
        hashvalue : str
            The md5 hash value of the `dict_withhash`

        """

        infile_list = []
        for key, val in self.items():
            if is_container(val):
                # XXX - SG this probably doesn't catch numpy arrays
                # containing embedded file names either. 
                if isinstance(val,dict):
                    # XXX - SG should traverse dicts, but ignoring for now
                    item = None
                else:
                    if len(val) == 0:
                        raise AttributeError('%s attribute is empty'%key)
                    item = val[0]
            else:
                item = val
            try:
                if os.path.isfile(item):
                    infile_list.append(key)
            except TypeError:
                # `item` is not a file or string.
                continue
        dict_withhash = self.dictcopy()
        dict_nofilename = self.dictcopy()
        for item in infile_list:
            dict_withhash[item] = self._hash_infile(dict_withhash, item)
            dict_nofilename[item] = [val[1] for val in dict_withhash[item]]
        # Sort the items of the dictionary, before hashing the string
        # representation so we get a predictable order of the
        # dictionary.
        sorted_dict = str(sorted(dict_nofilename.items()))
        return (dict_withhash, md5(sorted_dict).hexdigest())
            
    def __pretty__(self, p, cycle):
        '''Support for the pretty module
        
        pretty is included in ipython.externals for ipython > 0.10'''
        if cycle:
            p.text('Bunch(...)')
        else:
            p.begin_group(6, 'Bunch(')
            first = True
            for k, v in sorted(self.items()):
                if not first:
                    p.text(',')
                    p.breakable()
                p.text(k + '=')
                p.pretty(v)
                first = False
            p.end_group(6, ')')
    

class InterfaceResult(object):
    """Object that contains the results of running a particular Interface.
    
    Attributes
    ----------
    interface : object
        A copy of the `Interface` that was run to generate this result.
    outputs : Bunch
        An `Interface` specific Bunch that contains all possible files
        that are generated by the interface.  The `outputs` are used
        as the `inputs` to another node in when interfaces are used in
        the pipeline.
    runtime : Bunch

        Contains attributes that describe the runtime environment when
        the `Interface` was run.  Contains the attributes:

        * cmdline : The command line string that was executed
        * cwd : The directory the ``cmdline`` was executed in.
        * stdout : The output of running the ``cmdline``.
        * stderr : Any error messages output from running ``cmdline``.
        * returncode : The code returned from running the ``cmdline``.

    """

    # We could actually call aggregate_outputs in here...
    def __init__(self, interface, runtime, outputs=None):
        self.interface = interface
        self.runtime = runtime
        self.outputs = outputs


class Interface(object):
    """This is the template for Interface objects.

    It provides no functionality.  It defines the necessary attributes
    and methods all Interface objects should have.

    Everything in inputs should also be a possible (explicit?) argument to
    .__init__()
    """

    in_spec = None
    out_spec = None

    def __init__(self, **inputs):
        """Initialize command with given args and inputs."""
        raise NotImplementedError

    def run(self, cwd=None):
        """Execute the command."""
        raise NotImplementedError

    def aggregate_outputs(self):
        """Called to populate outputs"""
        raise NotImplementedError

    def get_input_info(self):
        """ Provides information about file inputs to copy or link to cwd.
            Necessary for pipeline operation
        """
        raise NotImplementedError

class BaseInterface(Interface):
    """Basic interface class to merge inputs into a single list

    Parameters
    ----------
    
    in_spec : dict
        Minimally this is a dictionary of the form
        in_spec = {'field' : ('one line desc', optional, default)}
        default is the default value of the field, None if not set or known
        optional is a boolean flag that indicates whether the input field is optional
    out_spec : dict
        Minimally this is a dictionary of the form
        out_spec = {'field' : 'one line desc'}
    
    """
    
    def __init__(self, **inputs):
        self.inputs = Bunch()
        if self.in_spec:
            for k,v in self.in_spec.items():
                if len(v) < 3:
                    setattr(self.inputs, k, None)
                else:
                    setattr(self.inputs, k, v[2])
        self.inputs.update(inputs)
        self._mandatory_args = [k for k,v in self.in_spec.items() if not v[1]]

    @classmethod
    def help(cls):
        """ Prints class help
        """
        cls._inputs_help()
        print ''
        cls._outputs_help()
        
    @classmethod
    def _inputs_help(cls):
        """ Prints the help of inputs
        """
        if not self.in_spec:
            return
        helpstr = ['Inputs','------']
        opthelpstr = None
        manhelpstr = None
        for k,v in sorted(cls.in_spec.items()):
            if v[1]:
                if not opthelpstr:
                    opthelpstr = ['','Optional:']
                default = v[2]
                if not default:
                    default = 'Unknown'
                opthelpstr += ['%s: %s (default=%s)' % (k,
                                                        v[0],
                                                        default)]
            else:
                if not manhelpstr:
                    manhelpstr = ['','Mandatory:']
                manhelpstr += ['%s: %s'%(k,v[0])]
        if manhelpstr:
            helpstr += manhelpstr
        if opthelpstr:
            helpstr += opthelpstr
        print '\n'.join(helpstr)
        return helpstr
        
    @classmethod
    def _outputs_help(cls):
        """ Prints the help of outputs
        """
        if not self.out_spec:
            return
        helpstr = ['Outputs','-------']
        for k,v in sorted(cls.out_spec.items()):
            helpstr += ['%s: %s' % (k, v)]
        print '\n'.join(helpstr)

    @classmethod
    def _outputs(cls):
        """ Returns a bunch containing output fields for the class
        """
        outputs = Bunch()
        if cls.out_spec:
            for k in cls.out_spec.keys():
                setattr(outputs, k, None)
        return outputs

    def _check_mandatory_inputs(self):
        if not self._mandatory_args:
            return
        inkeys = []
        for key, value in self.inputs.items():
            if value:
                inkeys.append(key)
        if not inkeys and self._mandatory_args:
            for arg in self._mandatory_args:
                print "Mandatory arg: %s not provided" % arg
            raise ValueError("All inputs have not been provided")
        # mandatory check 
        input_missing = False
        for arg in self._mandatory_args:
            if inkeys and arg not in inkeys:
                print "Mandatory arg: %s not provided" % arg
                input_missing = True
        if input_missing:
            raise ValueError("All inputs have not been provided")
            
    
    def run(self):
        """Execute this module.
        """
        self._check_mandatory_inputs()
        runtime = Bunch(returncode=0,
                        stdout=None,
                        stderr=None)
        outputs=self.aggregate_outputs()
        return InterfaceResult(deepcopy(self), runtime, outputs=outputs)

    def get_input_info(self):
        """ Provides information about file inputs to copy or link to cwd.
            Necessary for pipeline operation
        """
        return []    

class CommandLine(BaseInterface):
    """Encapsulate a command-line function along with the arguments and options.

    Provides a convenient mechanism to build a command line with it's
    arguments and options incrementally.  A `CommandLine` object can
    be reused, and it's arguments and options updated.  The
    `CommandLine` class is the base class for all nipype.interfaces
    classes.

    Parameters
    ----------
    in_spec : dict
        Minimally this is a dictionary of the form
        in_spec = {'field' : ('one line desc', optional, default,
                              mapping, position)}
        default is the default value of the field, None if not set or known
        optional is a boolean flag that indicates whether the input field is
        optional. default provides the default value of the field. mapping
        provides a template for the value, position is an optional input that
        indicates which place to put that input (0, 1, 2, ...) for inputs
        immediately following the command or [-1, -2, ...] for inputs after the
        optional commands.

    out_spec : dict
        Minimally this is a dictionary of the form
        out_spec = {'field' : 'one line desc'}

    Returns
    -------
    
    cmd : CommandLine
        A `CommandLine` object that can be run and/or updated.

    Examples
    --------
    >>> from nipype.interfaces.base import CommandLine
    >>> cmd = CommandLine('echo')
    >>> cmd.cmdline
    'echo'
    >>> res = cmd.run(None, 'foo')
    >>> print res.runtime.stdout
    foo
    <BLANKLINE>

    You could pass arguments in the following ways and all result in
    the same command.
    >>> lscmd = CommandLine('ls', args='-l -t')
    >>> lscmd.cmdline
    'ls -l -t'

    Notes
    -----
    
    When subclassing CommandLine, you will generally override at least:
        _compile_command, and run

    Also quite possibly __init__ but generally not  _runner

    """

    in_spec = {'args' : ('additional arguments for the command', True, None, \
                             '%s')}

    def __init__(self, command=None, **inputs):
        super(CommandLine, self).__init__(**inputs)
        self._environ = {}
        self._cmd = command

    @property
    def cmd(self):
        """sets base command, immutable"""
        return self._cmd

    @property
    def cmdline(self):
        """validates fsl options and generates command line argument"""
        allargs = self._parse_inputs()
        allargs.insert(0, self.cmd)
        return ' '.join(allargs)

    def run(self, cwd=None, **inputs):
        """Execute the command.
        
        Parameters
        ----------
        cwd : path
            Where do we effectively execute this command? (default: os.getcwd())
        inputs : mapping
            additional key,value pairs will update inputs
            it will overwrite existing key, value pairs
           
        Returns
        -------
        results : InterfaceResult Object
            A `Bunch` object with a copy of self in `interface`
        
        """
        self.inputs.update(inputs)
        if cwd is None:
            cwd = os.getcwd()
        # initialize provenance tracking
        runtime = Bunch(cmdline=self.cmdline, cwd=cwd,
                        stdout = None, stderr = None,
                        returncode = None, duration = None,
                        environ=deepcopy(os.environ.data),
                        hostname = gethostname())
        
        t = time()
        if hasattr(self, '_environ') and self._environ != None:
            env = deepcopy(os.environ.data)
            env.update(self._environ)
            runtime.environ = env
            proc  = subprocess.Popen(runtime.cmdline,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     shell=True,
                                     cwd=cwd,
                                     env=env)
        else:
            proc  = subprocess.Popen(runtime.cmdline,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     shell=True,
                                     cwd=cwd)

        runtime.stdout, runtime.stderr = proc.communicate()
        runtime.duration = time()-t
        runtime.returncode = proc.returncode

        results = InterfaceResult(deepcopy(self), runtime)
        if results.runtime.returncode == 0:
            results.outputs = self.aggregate_outputs()
        return results

    def _gen_outfiles(self, check = False):
        return self._outputs()
        
    def aggregate_outputs(self):
        return self._gen_outfiles(check = True)

    def _convert_inputs(self, opt, val):
        """Convert input to appropriate format. Override this function for
        class specific modifications that do not fall into general format:

        For example fnirt should implement this:

                elif isinstance(value, list) and self.__class__.__name__ == 'Fnirt':
                    # XXX Hack to deal with special case where some
                    # parameters to Fnirt can have a variable number
                    # of arguments.  Splitting the argument string,
                    # like '--infwhm=%d', then add as many format
                    # strings as there are values to the right-hand
                    # side.
                    argparts = argstr.split('=')
                    allargs.append(argparts[0] + '=' +
                                   ','.join([argparts[1] % y for y in value]))

        """
        return val

    def _parse_inputs(self, skip=()):
        """Parse all inputs and format options using the opt_map format string.

        Any inputs that are assigned (that are not None) are formatted
        to be added to the command line.

        Parameters
        ----------
        skip : tuple or list
            Inputs to skip in the parsing.  This is for inputs that
            require special handling, for example input files that
            often must be at the end of the command line.  Inputs that
            require special handling like this should be handled in a
            _parse_inputs method in the subclass.

        Returns
        -------
        allargs : list
            A list of all inputs formatted for the command line.

        """
        self._check_mandatory_inputs()

        allargs = []
        preargs = {}
        postargs = {}
        inputs = []
        for opt, value in self.inputs.items():
            if opt not in skip:
                value = self._convert_inputs(opt, value)
                if value is not None:
                    inputs.append((opt, value))
        inputs = sorted(inputs)
        for opt, value in inputs:
            try:
                argstr = self.in_spec[opt][3]
                pos = None
                val2append = None
                if len(self.in_spec[opt]) == 5:
                    pos = self.in_spec[opt][4]
                if argstr.find('%') == -1:
                    # Boolean options have no format string.  Just
                    # append options if True.
                    if value is True:
                        val2append = [argstr]
                    elif value is not False:
                        raise TypeError('Boolean option %s set to %s' %
                                         (opt, str(value)) )
                elif argstr.endswith('...'):
                    # repeatable option
                    # --id %d... will expand to
                    # --id 1 --id 2 --id 3 etc.,.
                    if not isinstance(value, list):
                        value = [value]
                    val2append = []
                    newargstr = argstr.replace('...','')
                    for val in value:
                        val2append.append(newargstr % val)
                elif isinstance(value, list):
                    val2append = [argstr % tuple(value)]
                else:
                    # Append options using format string.
                    val2append = [argstr % value]
                if pos is not None:
                    if pos>=0:
                        preargs[pos] = val2append[0]
                    else:
                        postargs[pos] = val2append[0]
                else:
                    allargs.extend(val2append)
            except TypeError, err:
                msg = 'Error when parsing option %s in class %s.\n%s' % \
                    (opt, self.__class__.__name__, err.message)
                warn(msg)
            except KeyError:
                warn("Option '%s' is not supported!" % (opt))
                raise
        for key, value in sorted(preargs.items()):
            allargs.insert(key, value)
        for key, value in sorted(postargs.items()):
            allargs.append(value)
        return allargs
