"""Utilities for converting the opt_map code to Traits code.

Currently this just parses the opt_map and returns the traited version
as a string.

"""

char_map = {'f': 'Float',
            'd': 'Int',
            's': 'Str',
            }

# opt_map from Bet to use as test
opt_map = {
    'outline':            '-o', # Bool
    'mask':               '-m',
    'skull':              '-s',
    'nooutput':           '-n',
    'frac':               '-f %.2f', # Float
    'vertical_gradient':  '-g %.2f',
    'radius':             '-r %d', # Int
    'center':             '-c %d %d %d', # List
    'threshold':          '-t',
    'mesh':               '-e',
    'verbose':            '-v',
    'functional':         '-F',
    'flags':              '%s',
    'reduce_bias':        '-B',
    'infile':             None, # Str, position=XXX, mandatory=True
    'outfile':            None,
    }

def trait_type(argstr):
    """Given an argument string, return the trait type as a string."""
    try:
        cnt = argstr.count('%')
    except AttributeError:
        # argstr is None
        return 'Str'
    if cnt == 0:
        return 'Bool'
    elif cnt == 1:
        indx = argstr.find('%')
        for ch in argstr[indx:]:
            if ch.isalpha():
                trt = char_map[ch]
                return trt
    elif cnt > 1:
        return 'List'
    else:
        return 'Unknown'

def build_expression(opt, val):
    trait = trait_type(val)
    attr = "%s = traits.%s(argstr=" % (opt, trait)
    if val is None:
        # argstr should be '%s', add position and mandatory
        attr += "\'%s\', position=XXX, mandatory=True"
    else:
        attr += "\'%s\'" % val
    attr += ')'
    #attr = '%s = traits.%s(argstr=\'%s\')' % (opt, trait, val)
    return attr

def main():
    for opt, val in sorted(opt_map.items()):
        attr = build_expression(opt, val)
        #print opt, val
        print attr

def test_opts():
    from nipype.testing import assert_equal

    optmap = {
            'mask':               '-m',
            'radius':             '-r %d',
            'frac':               '-f %.2f',
            'infile':             None,
            'center':             '-c %d %d %d',
            }

    mask = "mask = traits.Bool(argstr='-m')"
    radius = "radius = traits.Int(argstr='-r %d')"
    frac = "frac = traits.Float(argstr='-f %.2f')"
    infile = "infile = traits.Str(argstr='%s', position=0, mandatory=True)"
    center = "center = traits.List(argstr='-c %s', trait=traits.Int)"

    for opt, val in sorted(optmap.items()):
        exp = build_expression(opt, val)
        assert_equal, exp, eval(opt)

if __name__ == '__main__':
    main()
