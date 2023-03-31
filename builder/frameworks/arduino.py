# WizIO 2021 Georgi Angelov
#   http://www.wizio.eu/
#   https://github.com/ec-solutions/ez-pico

from __future__ import print_function
from SCons.Script import DefaultEnvironment

env = DefaultEnvironment()
platform = "arduino"
module = platform + "-" + env.BoardConfig().get("build.core")
m = __import__(module)
globals()[module] = m
m.dev_init(env, platform)
#print( env.Dump() )
