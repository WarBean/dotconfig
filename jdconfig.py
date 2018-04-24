import re
import json5

###############################################################
# utility functions
###############################################################

def consume_dots(config, key, create_default):
    sub_keys = key.split('.', 1)
    sub_key = sub_keys[0]

    if not dict.__contains__(config, sub_key) and len(sub_keys) == 2:
        if create_default:
            dict.__setitem__(config, sub_key, Config())
        else:
            raise KeyError('%s not exists' % str(key))

    if len(sub_keys) == 1:
        return config, sub_key
    else:
        sub_config = dict.__getitem__(config, sub_key)
        return consume_dots(sub_config, sub_keys[1], create_default)

def traverse_dfs(root, mode, continue_type, key_prefix = ''):
    for key, value in root.items():
        full_key = '.'.join([key_prefix, key]).strip('.')
        yield { 'key': full_key, 'value': value, 'item': (full_key, value) }[mode]
        if type(value) == continue_type:
            for kv in traverse_dfs(value, mode, continue_type, full_key):
                yield kv

def traverse_bfs(root, mode):
    q = [(root, '')]
    while len(q) > 0:
        child, key_prefix = q.pop(0)
        for key, value in child.items():
            full_key = '.'.join([key_prefix, key]).strip('.')
            yield { 'key': full_key, 'value': value, 'item': (full_key, value) }[mode]
            if type(value) == continue_type:
                q.append((value, full_key))

def init_assign(config, d, traverse):
    for full_key, value in traverse_dfs(d, 'item', continue_type = dict):
        # skip non-empty dict
        if type(value) == dict and len(value) > 0: continue
        sub_cfg, sub_key = consume_dots(config, full_key, create_default = True)
        sub_cfg[sub_key] = value

###############################################################
# main class
###############################################################

class Config(dict):

    def __init__(self, *args, **kwargs):
        super(Config, self).__init__()
        for arg in args:
            if isinstance(arg, str):
                jd = json5.load(open(arg))
                init_assign(self, jd, traverse = True)
            elif isinstance(arg, dict):
                init_assign(self, arg, traverse = True)
            else:
                raise TypeError('arg should be an instance of <str> or <dict>')
        if kwargs:
            init_assign(self, kwargs, traverse = False)

    def __call__(self, *args, **kwargs):
        return Config(self, *args, **kwargs)

    ###########################################################
    # support for pickle
    ###########################################################

    def __setstate__(self, state):
        init_assign(self, state, traverse = True)

    def __getstate__(self):
        d = dict()
        for key, value in self.items():
            if type(value) is Config:
                value = value.__getstate__()
            d[key] = value
        return d

    ###########################################################
    # access by '.' -> access by '[]'
    ###########################################################

    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        del self[key]

    ###########################################################
    # access by '[]'
    ###########################################################

    def __getitem__(self, key):
        sub_cfg, sub_key = consume_dots(self, key, create_default = False)
        return dict.__getitem__(sub_cfg, sub_key)

    def __setitem__(self, key, value):
        sub_cfg, sub_key = consume_dots(self, key, create_default = True)
        dict.__setitem__(sub_cfg, sub_key, value)

    def __delitem__(self, key):
        sub_cfg, sub_key = consume_dots(self, key, create_default = False)
        dict.__delitem__(sub_cfg, sub_key)
        #del self.__dict__[key]

    ###########################################################
    # access by 'in'
    ###########################################################

    def __contains__(self, key):
        try:
            sub_cfg, sub_key = consume_dots(self, key, create_default = False)
        except KeyError:
            return False
        return dict.__contains__(sub_cfg, sub_key)

    ###########################################################
    # traverse keys / values/ items
    ###########################################################

    def all_keys(self, order = 'dfs'):
        traverse = { 'dfs': traverse_dfs, 'bfs': traverse_bfs }[order]
        for key in traverse(self, 'key', continue_type = Config):
            yield key

    def all_values(self, order = 'dfs'):
        traverse = { 'dfs': traverse_dfs, 'bfs': traverse_bfs }[order]
        for value in traverse(self, 'value', continue_type = Config):
            yield value

    def all_items(self, order = 'dfs'):
        traverse = { 'dfs': traverse_dfs, 'bfs': traverse_bfs }[order]
        for key, value in traverse(self, 'item', continue_type = Config):
            yield key, value

    ###########################################################
    # for command line arguments
    ###########################################################

    def parse_args(self, cmd_args = None):
        if cmd_args is None:
            import sys
            cmd_args = sys.argv[1:]
        index = 0
        while index < len(cmd_args):
            arg = cmd_args[index]
            err_msg = 'invalid command line argument pattern: %s' % arg
            assert arg.startswith('--'), err_msg
            assert len(arg) > 2, err_msg
            assert arg[2] != '-', err_msg

            arg = arg[2:]
            if '=' in arg:
                key, value = arg.split('=')
                index += 1
            else:
                assert len(cmd_args) > index + 1, \
                        'incomplete command line arguments'
                key = arg
                value = cmd_args[index + 1]
                index += 2
            if ':' in value:
                value, value_type_str = value.split(':')
                value_type = eval(value_type_str)
            else:
                value_type = None

            assert key in self, '%s not exists in config' % key
            if value_type is None:
                value_type = type(self[key])

            if value_type is bool:
                self[key] = {
                    'true' : True,
                    'True' : True,
                    '1'    : True,
                    'false': False,
                    'False': False,
                    '0'    : False,
                }[value]
            else:
                self[key] = value_type(value)
