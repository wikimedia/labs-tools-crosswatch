# -*- coding: utf-8 -*-
# ISC License
# Copyright (C) 2015 Jan Lebert
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import sys

from .server import run

if len(sys.argv) < 2:
    print("ERROR: no port number as first argument given. Quitting",
          file=sys.stderr)
    sys.exit(1)
else:
    port = int(sys.argv[1])
    run(port)